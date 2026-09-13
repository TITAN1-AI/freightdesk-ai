"""Dependency-light startup checkpoints; no request/body/credential data accepted."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r'C:\FreightDeskRuntime')
STAGES = {'PYTHON_START','BINARY_STDIO','IMPORT_MODULES','HOST_INITIALIZED','FIRST_MESSAGE_RECEIVED',
    'RESPONSE_GENERATED','RESPONSE_FLUSHED','HOST_EXIT','STARTUP_FAILED'}
CODES = {'OK','IMPORT_OUTPUT_SUPPRESSED','MODULE_IMPORT_FAILED','BINARY_STDIO_FAILED','HOST_START_FAILED',
    'FRAME_READ_FAILED','HOST_REQUEST_REJECTED','STDOUT_WRITE_FAILED','HOST_INPUT_CLOSED','SELF_TEST_OK'}
EXCEPTIONS = {'ImportError','ModuleNotFoundError','SyntaxError','PermissionError','FileNotFoundError',
    'OSError','RuntimeError','ValueError','TimeoutError','EOFError','TypeError'}


class StartupRecorder:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.initialized = False
        self.received = False

    def record(self, stage: str, code: str = 'OK', error: Exception | None = None) -> None:
        if stage not in STAGES or code not in CODES:
            raise ValueError('startup_diagnostic_invalid')
        if stage == 'HOST_INITIALIZED':
            self.initialized = True
        if stage == 'FIRST_MESSAGE_RECEIVED':
            self.received = True
        value = {'timestamp':datetime.now(timezone.utc).isoformat(), 'startup_stage':stage, 'safe_error_code':code,
            'exception_type':type(error).__name__ if error and type(error).__name__ in EXCEPTIONS else 'Exception' if error else 'NONE',
            'launcher_started':True,'python_started':True,'host_initialized':self.initialized,
            'first_message_received':self.received}
        try:
            current = self.root
            for part in (None,'Data','booking-logistics','ascend-native','startup-python.jsonl'):
                if part:
                    current = current / part
                if current.is_symlink() or current.is_junction():
                    raise ValueError('startup_path_rejected')
            current.parent.mkdir(parents=True, exist_ok=True)
            with current.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(value, separators=(',',':')) + '\n')
        except Exception:
            # No raw exception. The launcher also has its own independent early-start checkpoint.
            sys.stderr.write('STARTUP_DIAGNOSTIC_UNAVAILABLE\n')
