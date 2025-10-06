using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Input;
using GatewayIDE.App.Services.Processes;
using Avalonia.Media;

namespace GatewayIDE.App.ViewModels;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    // ===== constants =====
    private const string ComposeFile = "gateway-compose.yml";
    private const string SERVICE = "gateway";

    // ===== INotifyPropertyChanged =====
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    // ===== UI State =====
    private double _leftPaneWidth = 260;
    public double LeftPaneWidth
    {
        get => _leftPaneWidth;
        set { _leftPaneWidth = value; Raise(); }
    }

    private string _activeTab = "Dashboard";
    public string ActiveTab
    {
        get => _activeTab;
        set {
            _activeTab = value;
            Raise();
            Raise(nameof(IsDashboard));
            Raise(nameof(IsDocker));
        }
    }

    public bool IsDashboard => ActiveTab == "Dashboard";
    public bool IsDocker => ActiveTab == "Docker";

    // ===== Chat =====
    private readonly StringBuilder _chat = new();
    public string ChatBuffer => _chat.ToString();
    private string _chatInput = string.Empty;
    public string ChatInput
    {
        get => _chatInput;
        set { _chatInput = value; Raise(); }
    }

    // ===== Dashboard Terminal =====
    private readonly StringBuilder _term = new();
    public string TerminalBuffer => _term.ToString();

    // ===== System Status (Dashboard) =====
    private string _dockerImageStatus = "None";
    public string DockerImageStatus
    {
        get => _dockerImageStatus;
        private set { _dockerImageStatus = value; Raise(); Raise(nameof(DockerImageStatusBrush)); }
    }

    private string _dockerContainerStatus = "Offline";
    public string DockerContainerStatus
    {
        get => _dockerContainerStatus;
        private set { _dockerContainerStatus = value; Raise(); Raise(nameof(DockerContainerStatusBrush)); }
    }

    private string _dockerDesktopStatus = "Unknown";
    public string DockerDesktopStatus
    {
        get => _dockerDesktopStatus;
        private set { _dockerDesktopStatus = value; Raise(); Raise(nameof(DockerDesktopStatusBrush)); }
    }


    public IBrush DockerImageStatusBrush =>
        DockerImageStatus == "Available" ? Brushes.LimeGreen :
        DockerImageStatus == "None"      ? Brushes.Red :
                                        Brushes.Gray;

    public IBrush DockerContainerStatusBrush =>
        DockerContainerStatus == "Online"  ? Brushes.LimeGreen :
        DockerContainerStatus == "Stopped" ? Brushes.Yellow :
        DockerContainerStatus == "Offline" ? Brushes.Red :
                                            Brushes.Gray;

    public IBrush DockerDesktopStatusBrush =>
        DockerDesktopStatus == "Open"          ? Brushes.LimeGreen :
        DockerDesktopStatus == "Closed"        ? Brushes.Red :
        DockerDesktopStatus == "Not Installed" ? Brushes.Gray :
                                                Brushes.Gray;


    // ===== Docker Terminals (split stdout/err) =====
    private readonly StringBuilder _dockerOut = new();
    private readonly StringBuilder _dockerErr = new();
    private readonly StringBuilder _gatewayLog = new();
    public string GatewayLogBuffer => _gatewayLog.ToString();
    public string DockerOutBuffer => _dockerOut.ToString();
    public string DockerErrBuffer => _dockerErr.ToString();
    private void AppendGateway(string s) { _gatewayLog.Append(s); Raise(nameof(GatewayLogBuffer)); }
    private void AppendDockerOut(string s) { _dockerOut.Append(s); Raise(nameof(DockerOutBuffer)); }
    private void AppendDockerErr(string s) { _dockerErr.Append(s); Raise(nameof(DockerErrBuffer)); }

    // ===== Docker log processes =====
    private Process? _meganodeLogsProc;

    // >>> Tail-Guard für Gateway-Runtime-Logs (nur EIN logs -f)
    private CancellationTokenSource? _gatewayTailCts;

    // ===== Commands (match XAML) =====
    public ICommand ToggleChatCommand { get; }
    public ICommand SelectTabCommand { get; }
    public ICommand SendChatCommand { get; }
    public ICommand StartMeganodeCommand { get; }
    public ICommand RebuildGatewayCommand { get; }
    public ICommand StartGatewayCommand { get; }
    public ICommand StopGatewayCommand { get; }
    public ICommand RemoveGatewayContainerCommand { get; }

    // ===== Konstruktor =====
    public MainWindowViewModel()
    {
        // ctor: Commands registrieren
        ToggleChatCommand = new DelegateCommand(_ => {LeftPaneWidth = LeftPaneWidth > 0 ? 0 : 260;});
        SelectTabCommand = new DelegateCommand(async p =>{ActiveTab = p?.ToString() ?? "Dashboard";AppendTerm($"[TAB] {ActiveTab}");if (IsDashboard) await RefreshSystemStatusAsync();});
        SendChatCommand = new DelegateCommand(_ =>{if (!string.IsNullOrWhiteSpace(ChatInput)){_chat.AppendLine($"[YOU] {ChatInput}");Raise(nameof(ChatBuffer));ChatInput = string.Empty;}});
        RebuildGatewayCommand = new DelegateCommand(async _ => await FullRebuildAsync());
        StartGatewayCommand   = new DelegateCommand(async _ => await StartGatewayAsync());
        StopGatewayCommand    = new DelegateCommand(async _ => await StopGatewayAsync());
        RemoveGatewayContainerCommand = new DelegateCommand(async _ => await RemoveGatewayContainerAsync());
        StartMeganodeCommand = new DelegateCommand(_ => StartMeganode());

        _ = RefreshSystemStatusAsync();
    }

    // ===== helpers =====
    private static string FindRepoRoot()
    {
        // Lauf nach oben, bis wir eine valide Repo-Wurzel finden
        var dir = AppContext.BaseDirectory;
        while (!string.IsNullOrEmpty(dir))
        {
            var hasSln    = System.IO.File.Exists(System.IO.Path.Combine(dir, "GatewayIDE.sln"));
            var hasDeploy = System.IO.Directory.Exists(System.IO.Path.Combine(dir, "deploy"));
            if (hasSln || hasDeploy) return dir;

            var parent = System.IO.Directory.GetParent(dir);
            if (parent == null) break;
            dir = parent.FullName;
        }

        // Fallback: aktuelles Arbeitsverzeichnis
        return System.IO.Directory.GetCurrentDirectory();
    }

    private static string RepoDeployDir()
    {
        var root   = FindRepoRoot();
        var deploy = System.IO.Path.Combine(root, "deploy");
        return System.IO.Directory.Exists(deploy) ? deploy : root;
    }

    private Process RunDocker(string args)
        => ProcessManager.StartProcess("docker", args, RepoDeployDir());

    private void AttachToDocker(Process p, string tag, bool mirrorErrToOut = false)
    {
        try { p.EnableRaisingEvents = true; } catch { /* ignore */ }

        p.OutputDataReceived += (_, e) =>
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                _dockerOut.AppendLine(e.Data);
                Raise(nameof(DockerOutBuffer));
            }
        };
        p.ErrorDataReceived += (_, e) =>
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                if (mirrorErrToOut)
                {
                    _dockerOut.AppendLine(e.Data);
                    Raise(nameof(DockerOutBuffer));
                }
                else
                {
                    _dockerErr.AppendLine(e.Data);
                    Raise(nameof(DockerErrBuffer));
                }
            }
        };

        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        p.Exited += (_, __) => AppendTerm($"{tag} beendet.");
    }

    private void AttachToGateway(Process p)
    {
        try { p.EnableRaisingEvents = true; } catch { /* ignore */ }
        p.OutputDataReceived += (_, e) => { if (!string.IsNullOrEmpty(e.Data)) AppendGateway(e.Data + Environment.NewLine); };
        p.ErrorDataReceived  += (_, e) => { if (!string.IsNullOrEmpty(e.Data))  AppendGateway(e.Data + Environment.NewLine); };
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
    }


    private void AppendTerm(string line)
    {
        _term.AppendLine(line);
        Raise(nameof(TerminalBuffer));
    }

    private void Kill(ref Process? proc)
    {
        try { if (proc != null && !proc.HasExited) proc.Kill(entireProcessTree: true); } catch { /* ignore */ }
        proc = null;
    }

    // ===== Docker Orchestrierung =====
    private async Task FullRebuildAsync()
    {
        try
        {
            _dockerOut.Clear();  Raise(nameof(DockerOutBuffer));
            _dockerErr.Clear();  Raise(nameof(DockerErrBuffer));
            _gatewayLog.Clear(); Raise(nameof(GatewayLogBuffer));

            await DockerService.FullRebuildAsync(AppendDockerOut, AppendDockerErr);

            var banner =
                "################################" + Environment.NewLine +
                "######## Build Complete ########" + Environment.NewLine +
                "# You can start the Server now #" + Environment.NewLine +
                "################################" + Environment.NewLine + Environment.NewLine;
            AppendDockerOut(banner);

            await RefreshSystemStatusAsync();
        }
        catch (Exception ex)
        {
            AppendDockerErr("❌ " + ex.Message + Environment.NewLine);
        }
    }

    private async Task StartGatewayAsync()
    {
        _dockerOut.Clear();  Raise(nameof(DockerOutBuffer));
        _dockerErr.Clear();  Raise(nameof(DockerErrBuffer));
        _gatewayLog.Clear(); Raise(nameof(GatewayLogBuffer));

        await DockerService.StartGatewayAsync(AppendDockerOut, AppendDockerErr);

        _gatewayTailCts?.Cancel();
        _gatewayTailCts = new CancellationTokenSource();
        _ = DockerService.TailGatewayLogsAsync(AppendGateway, AppendGateway, _gatewayTailCts.Token);

        await RefreshSystemStatusAsync();
    }

    private async Task StopGatewayAsync()
    {
        _gatewayTailCts?.Cancel();
        _gatewayTailCts = null;

        await DockerService.StopGatewayAsync(AppendDockerOut, AppendDockerErr);
        await RefreshSystemStatusAsync();
    }

    private async Task RemoveGatewayContainerAsync()
    {
        try
        {
            AppendDockerOut("[REMOVE] Entferne gateway-container …" + Environment.NewLine);
            await DockerService.RemoveGatewayContainerAsync(AppendDockerOut, AppendDockerErr);
            await RefreshSystemStatusAsync();
            AppendDockerOut("[REMOVE] Fertig." + Environment.NewLine);
        }
        catch (Exception ex)
        {
            AppendDockerErr("❌ Remove fehlgeschlagen: " + ex.Message + Environment.NewLine);
        }
    }


    private async Task RefreshSystemStatusAsync()
    {
        try
        {
            var desktop = await DockerService.GetDockerDesktopStatusAsync();
            DockerDesktopStatus = desktop switch
            {
                GatewayIDE.App.Services.Processes.DesktopStatus.Open          => "Open",
                GatewayIDE.App.Services.Processes.DesktopStatus.Closed        => "Closed",
                GatewayIDE.App.Services.Processes.DesktopStatus.NotInstalled  => "Not Installed",
                _ => "Unknown"
            };

            // Wenn Desktop nicht offen ist, weitere Docker-Queries vermeiden
            if (desktop != GatewayIDE.App.Services.Processes.DesktopStatus.Open)
            {
                DockerImageStatus = "None";
                DockerContainerStatus = "Offline";
                return;
            }

            DockerImageStatus = await DockerService.IsImageAvailableAsync()
                ? "Available" : "None";

            var st = await DockerService.GetGatewayStatusAsync();
            DockerContainerStatus = st switch
            {
                GatewayIDE.App.Services.Processes.ContainerStatus.Running  => "Online",
                GatewayIDE.App.Services.Processes.ContainerStatus.Exited   => "Stopped",
                GatewayIDE.App.Services.Processes.ContainerStatus.NotFound => "Offline",
                _ => "Offline"
            };
        }
        catch
        {
            DockerDesktopStatus = "Unknown";
            DockerImageStatus = "Unknown";
            DockerContainerStatus = "Offline";
        }
    }





    // ===== Meganode =====
    private void StartMeganode()
    {
        AppendTerm("Starte Mega-Node …");
        var start = RunDocker("compose up meganode -d");
        AttachToDocker(start, "[MEGA-UP]");

        Kill(ref _meganodeLogsProc);
        _meganodeLogsProc = RunDocker("compose logs -f meganode");
        AttachToDocker(_meganodeLogsProc, "[MEGA]");
    }
}
