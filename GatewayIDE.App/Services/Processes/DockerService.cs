using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace GatewayIDE.App.Services.Processes
{
    public enum DesktopStatus { Open, Closed, NotInstalled, Unknown }
    public enum ContainerStatus { NotFound, Running, Exited, Unknown }

    public static class DockerService
    {
        private const string ComposeFile = "gateway-compose.yml";
        private const string GatewayImage = "deploy-gateway:latest"; 

        private static string FindRepoRoot()
        {
            // 1) Kandidaten: BaseDirectory und CurrentDirectory
            var candidates = new[] { AppContext.BaseDirectory, Environment.CurrentDirectory };

            foreach (var start in candidates)
            {
                var dir = Path.GetFullPath(start);
                while (!string.IsNullOrEmpty(dir))
                {
                    var hasDeploy = Directory.Exists(Path.Combine(dir, "deploy"));
                    var hasSln    = File.Exists(Path.Combine(dir, "GatewayIDE.sln"));
                    if (hasDeploy || hasSln)
                        return dir;

                    var parent = Directory.GetParent(dir);
                    if (parent == null) break;
                    dir = parent.FullName;
                }
            }

            // Fallback
            return Directory.GetCurrentDirectory();
        }

        private static string _cachedDeployDir = string.Empty;

        // >>> diese Methode ERSETZEN:
        private static string DeployDir()
        {
            if (!string.IsNullOrEmpty(_cachedDeployDir) && Directory.Exists(_cachedDeployDir))
                return _cachedDeployDir;

            var root = FindRepoRoot();
            var deploy = Path.Combine(root, "deploy");

            if (!Directory.Exists(deploy))
                throw new DirectoryNotFoundException($"deploy-Verzeichnis nicht gefunden. Start: '{AppContext.BaseDirectory}', Root erkannt: '{root}'.");

            _cachedDeployDir = deploy;
            return _cachedDeployDir;
        }
        // ---- low-level runner (streamt stdout/err, wartet auf Exit) ----
        private static async Task<int> RunAsync(
            string file, string args,
            Action<string>? onOut = null,
            Action<string>? onErr = null,
            CancellationToken ct = default
            )
        {
            var psi = new ProcessStartInfo(file, args)
            {
                WorkingDirectory = DeployDir(),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
                CreateNoWindow = true
            };

            using var p = new Process { StartInfo = psi, EnableRaisingEvents = true };

            p.OutputDataReceived += (_, e) => { if (!string.IsNullOrEmpty(e.Data)) onOut?.Invoke(e.Data + Environment.NewLine); };
            p.ErrorDataReceived  += (_, e) => { if (!string.IsNullOrEmpty(e.Data)) onErr?.Invoke(e.Data + Environment.NewLine); };

            if (!p.Start()) throw new InvalidOperationException($"Prozessstart fehlgeschlagen: {file} {args}");
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();

            // Cancellation: kill process if requested
            await Task.Run(() => {
                while (!p.HasExited)
                {
                    if (ct.IsCancellationRequested)
                    {
                        try { p.Kill(entireProcessTree: true); } catch { /* ignore */ }
                        break;
                    }
                    Thread.Sleep(50);
                }
            }, ct).ConfigureAwait(false);

            await p.WaitForExitAsync(ct).ConfigureAwait(false);
            return p.ExitCode;
        }

        public static async Task<DesktopStatus> GetDockerDesktopStatusAsync(
            Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
        {
            // 1) Schnelltest: docker info
            var rc = await RunAsync("docker", "info", o, e, ct);
            if (rc == 0) return DesktopStatus.Open;

            // 2) Windows-Service checken (Docker Desktop Backend)
            if (OperatingSystem.IsWindows())
            {
                var sb = new StringBuilder();
                var rc2 = await RunAsync("sc", "query com.docker.service",
                                        s => sb.AppendLine(s), e, ct);

                if (rc2 == 0)
                {
                    var txt = sb.ToString();
                    if (txt.IndexOf("RUNNING", StringComparison.OrdinalIgnoreCase) >= 0)
                        return DesktopStatus.Open;
                    if (txt.IndexOf("STOPPED", StringComparison.OrdinalIgnoreCase) >= 0)
                        return DesktopStatus.Closed;

                    return DesktopStatus.Closed; // konservativ
                }

                return DesktopStatus.NotInstalled;
            }

            return DesktopStatus.Unknown;
        }


        // Hilfsfunktion für docker compose
        private static Task<int> ComposeAsync(string args, Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
            => RunAsync("docker", $"compose -f \"{ComposeFile}\" {args}", o, e, ct);

        // ---- Einzeloperationen ------------------------------------------------

        public static Task<int> StartGatewayAsync(Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
            => ComposeAsync("up -d gateway", o, e, ct);

        public static Task<int> StopGatewayAsync(Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
            => ComposeAsync("stop gateway", o, e, ct);

        public static Task<int> BuildNoCacheAsync(
            Action<string>? o = null,
            Action<string>? e = null,
            CancellationToken ct = default)
            => ComposeAsync("build --no-cache gateway", o, e, ct);

        public static Task<int> TailGatewayLogsAsync(Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
            => ComposeAsync("logs -f gateway", o, e, ct);

        // ---- Wipe (sequenziell & robust) -------------------------------------
        public static async Task WipeAllAsync(Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
        {
            // 1) down inkl. Images/Volumes/Orphans
            o?.Invoke("🧹 down --rmi all -v --remove-orphans\n");
            var rc = await ComposeAsync("down --rmi all -v --remove-orphans", o, e, ct);
            if (rc != 0) throw new Exception($"docker compose down fehlgeschlagen (rc={rc}).");

            // 2) Netzwerke räumen (best effort)
            await RunAsync("docker", "network rm gateway_default", o, e, ct);
            await RunAsync("docker", "network rm gateway-net",   o, e, ct);

            // 3) System prune (aggressiv)
            o?.Invoke("🧽 docker system prune -af\n");
            rc = await RunAsync("docker", "system prune -af", o, e, ct);
            if (rc != 0) throw new Exception($"docker system prune fehlgeschlagen (rc={rc}).");
        }

        // ---- Orchestrierung: Full Rebuild (wipe -> build) --------------
        public static async Task<bool> IsImageAvailableAsync(
            Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
        {
            // Robust: direkter Inspect auf das Image, unabhängig von compose state
            var rc = await RunAsync("docker", $"image inspect {GatewayImage}", o, e, ct);
            return rc == 0;
        }


        public static async Task<ContainerStatus> GetGatewayStatusAsync(
            Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)

        {
            var sb = new StringBuilder();
            int rc = await RunAsync("docker", "inspect -f \"{{.State.Status}}\" gateway-container",
                s => sb.Append(s), _ => { }, ct);

            if (rc != 0) return ContainerStatus.NotFound;

            var status = sb.ToString().Trim().ToLowerInvariant();
            return status switch
            {
                "running" => ContainerStatus.Running,
                "exited"  => ContainerStatus.Exited,
                "created" => ContainerStatus.Exited,
                "dead"    => ContainerStatus.Exited,
                _         => ContainerStatus.Unknown
            };
        }

        // ORCHESTRATION: wipe -> build  (KEIN up hier)
        public static async Task FullRebuildAsync(Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
        {
            await WipeAllAsync(o, e, ct);
            o?.Invoke("🏗️  build --no-cache gateway\n");
            var rc = await BuildNoCacheAsync(o, e, ct);
            if (rc != 0) throw new Exception($"docker compose build fehlgeschlagen (rc={rc}).");
        }

        public static Task<int> RemoveGatewayContainerAsync(
            Action<string>? o = null, Action<string>? e = null, CancellationToken ct = default)
        {
            // Entfernt NUR den Container (nicht das Image/Volumes)
            // Variante über compose (bevorzugt, da Name aus compose): 
            return ComposeAsync("rm -f gateway", o, e, ct);

            // Alternativ direkt über Container-Namen:
            // return RunAsync("docker", "rm -f gateway-container", o, e, ct);
        }

        public static Task<int> ExecInGatewayAsync(
            string command,
            Action<string>? o = null,
            Action<string>? e = null,
            CancellationToken ct = default)
        {
            // Container-Name muss zu compose passen:
            const string container = "gateway-container";
            var escaped = command.Replace("\"", "\\\"");
            // bash -lc erlaubt Pipes, &&, Aliases etc.
            return RunAsync("docker", $"exec {container} bash -lc \"{escaped}\"", o, e, ct);
        }





    }
}
