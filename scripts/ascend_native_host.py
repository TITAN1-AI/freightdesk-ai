"""Native Messaging process entry point. stdout is exclusively framed protocol messages."""
import os
import sys
import contextlib
import io
import warnings

def run(argv, stdin, stdout, *, recorder=None, loader=None):
    from executors.ascend_extension.startup import StartupRecorder
    recorder = recorder or StartupRecorder()
    recorder.record('PYTHON_START')
    stage = 'BINARY_STDIO'
    try:
        if os.name == 'nt' and stdin is sys.stdin:
            import msvcrt
            msvcrt.setmode(stdin.fileno(),os.O_BINARY)
            msvcrt.setmode(stdout.fileno(),os.O_BINARY)
        recorder.record('BINARY_STDIO')
        stage = 'IMPORT_MODULES'
        class Discard(io.TextIOBase):
            used = False
            def write(self, value):
                self.used = self.used or bool(value)
                return len(value)
        discarded = Discard()
        with contextlib.redirect_stdout(discarded), contextlib.redirect_stderr(discarded), warnings.catch_warnings(record=True) as caught:
            if loader:
                main = loader()
            else:
                from executors.ascend_extension.host import main
        discarded.used = discarded.used or bool(caught)
        recorder.record('IMPORT_MODULES','IMPORT_OUTPUT_SUPPRESSED' if discarded.used else 'OK')
        stage = 'HOST_INITIALIZED'
        main(argv, getattr(stdin,'buffer',stdin), getattr(stdout,'buffer',stdout), startup=recorder)
        recorder.record('HOST_EXIT')
        return 0
    except Exception as error:
        code = {'BINARY_STDIO':'BINARY_STDIO_FAILED','IMPORT_MODULES':'MODULE_IMPORT_FAILED'}.get(stage,'HOST_START_FAILED')
        recorder.record('STARTUP_FAILED',code,error)
        return 1


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:],sys.stdin,sys.stdout))
