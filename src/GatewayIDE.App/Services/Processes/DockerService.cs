using System.Diagnostics;
using System.IO;

namespace GatewayIDE.App.Services.Processes;

public static class DockerService
{
    private static string DeployDir()
        => Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..","..","..","deploy"));

    private static Process Run(string args)
    {
        var psi = new ProcessStartInfo("docker", args)
        {
            WorkingDirectory = DeployDir(),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        return Process.Start(psi)!;
    }

    // compose file name
    private const string ComposeFile = "gateway-compose.yml";

    // Start: erstellt Image falls nicht vorhanden
    public static Process StartGateway() => Run($"compose -f {ComposeFile} up -d gateway");

    public static Process StopGateway()  => Run($"compose -f {ComposeFile} stop gateway");

    public static Process BuildNoCache() => Run($"compose -f {ComposeFile} build --no-cache gateway");

    public static Process TailGatewayLogs() => Run($"compose -f {ComposeFile} logs -f gateway");

    // Voller Rebuild gemäß run.py: wipe -> build --no-cache -> up -d
    public static (Process wipe, Process? build, Process? up) FullRebuild()
    {
        // 1) down inkl Images/Volumes/Orphans
        var wipe1 = Run($"compose -f {ComposeFile} down --rmi all -v --remove-orphans");
        // 2) evtl. alte Netzwerke säubern
        var wipe2 = new ProcessStartInfo("docker", "network rm gateway_default") { UseShellExecute=false, RedirectStandardOutput=true, RedirectStandardError=true };
        var wipe3 = new ProcessStartInfo("docker", "network rm gateway-net")    { UseShellExecute=false, RedirectStandardOutput=true, RedirectStandardError=true };
        var wipe4 = new ProcessStartInfo("docker", "system prune -af")          { UseShellExecute=false, RedirectStandardOutput=true, RedirectStandardError=true };

        // wir führen die restlichen Schritte sequenziell aus (Caller hängt die Handler an)
        var p2 = Process.Start(wipe2)!;
        var p3 = Process.Start(wipe3)!;
        var p4 = Process.Start(wipe4)!;

        // Build & Up separat zurückgeben, damit der Caller sie attachen kann
        var build = Run($"compose -f {ComposeFile} build --no-cache gateway");
        var up    = Run($"compose -f {ComposeFile} up -d gateway");
        return (wipe1, build, up);
    }
}
