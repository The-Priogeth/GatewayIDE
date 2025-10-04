using System.Diagnostics;

namespace GatewayIDE.App.Services.Processes;

public static class ProcessManager
{
    public static Process StartProcess(string fileName, string args, string? cwd = null)
    {
        var psi = new ProcessStartInfo(fileName, args)
        {
            WorkingDirectory = cwd ?? Environment.CurrentDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        return Process.Start(psi)!;
    }
}
