// Owner-built fixed launcher; no shell and no user-selected executable/arguments.
using System;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
class FreightDeskAscendHost {
    static bool pythonStarted = false;
    static readonly object logLock = new object();
    static void Diagnostic(string stage, string code, Exception error = null) {
        string exceptionType = "NONE";
        if(error != null) {
            exceptionType = error is System.ComponentModel.Win32Exception ? "Win32Exception" :
                error is UnauthorizedAccessException ? "UnauthorizedAccessException" :
                error is IOException ? "IOException" : "Exception";
        }
        string line = "{\"timestamp\":\"" + DateTime.UtcNow.ToString("O") + "\",\"startup_stage\":\"" + stage +
            "\",\"safe_error_code\":\"" + code + "\",\"exception_type\":\"" + exceptionType +
            "\",\"launcher_started\":true,\"python_started\":" + (pythonStarted ? "true" : "false") +
            ",\"host_initialized\":false,\"first_message_received\":false}";
        try {
            string directory = @"C:\FreightDeskRuntime\Data\booking-logistics\ascend-native";
            string file = Path.Combine(directory, "startup-launcher.jsonl");
            for(string current = file; current != null; current = Path.GetDirectoryName(current)) {
                if((Directory.Exists(current) || File.Exists(current)) &&
                    (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0) throw new IOException();
            }
            Directory.CreateDirectory(directory);
            lock(logLock) File.AppendAllText(file, line + Environment.NewLine);
        } catch { Console.Error.WriteLine("STARTUP_DIAGNOSTIC_UNAVAILABLE"); }
    }
    static void Relay(Stream input, Stream output) {
        var buffer = new byte[8192];
        int count;
        while((count = input.Read(buffer, 0, buffer.Length)) > 0) {
            output.Write(buffer, 0, count);
            output.Flush(); // Native messages must not wait for a full buffer or pipe EOF.
        }
    }
    static int Main(string[] args) {
        Diagnostic("LAUNCHER_START", "OK");
        try {
            if(args.Length < 1 || args.Length > 2 || !Regex.IsMatch(args[0], @"\Achrome-extension://[a-p]{32}/\z")) {
                Diagnostic("ARGUMENT_VALIDATION", "INVALID_ORIGIN"); return 2;
            }
            bool selfTest = args.Length == 2 && args[1] == "--self-test";
            if(args.Length == 2 && !selfTest && !Regex.IsMatch(args[1], @"\A--parent-window=\d+\z")) {
                Diagnostic("ARGUMENT_VALIDATION", "INVALID_ARGUMENTS"); return 2;
            }
            var start = new ProcessStartInfo(@"__PYTHON__", "-B -m scripts.ascend_native_host " + args[0]);
            if(selfTest) start.Arguments += " --self-test";
            start.WorkingDirectory = @"__SOURCE__";
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardInput = true;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.EnvironmentVariables["FREIGHTDESK_RUNTIME_ROOT"] = @"C:\FreightDeskRuntime";
            start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            start.EnvironmentVariables["TEMP"] = @"C:\FreightDeskRuntime\Data\booking-logistics\ascend-native";
            start.EnvironmentVariables["TMP"] = start.EnvironmentVariables["TEMP"];
            using(var child = Process.Start(start)) {
                pythonStarted = true;
                Diagnostic("PYTHON_LAUNCH", "OK");
                Task.Factory.StartNew(() => { try { Relay(Console.OpenStandardInput(), child.StandardInput.BaseStream); child.StandardInput.Close(); }
                    catch(Exception error) { Diagnostic("STDIN_RELAY", "STDIO_RELAY_FAILED", error); } });
                Task.Factory.StartNew(() => { try { child.StandardError.BaseStream.CopyTo(Stream.Null); } catch {} });
                Relay(child.StandardOutput.BaseStream, Console.OpenStandardOutput());
                child.WaitForExit();
                Diagnostic("PYTHON_EXIT", child.ExitCode == 0 ? "OK" : "PYTHON_EXIT_NONZERO");
                return child.ExitCode;
            }
        } catch(Exception error) { Diagnostic("STARTUP_FAILED", "LAUNCHER_START_FAILED", error); return 1; }
    }
}
