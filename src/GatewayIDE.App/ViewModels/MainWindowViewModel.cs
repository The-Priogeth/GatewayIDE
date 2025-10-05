using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Input;
using GatewayIDE.App.Services.Processes;

namespace GatewayIDE.App.ViewModels;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
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
        set { _activeTab = value; Raise(); Raise(nameof(IsDashboard)); }
    }
    public bool IsDashboard => ActiveTab == "Dashboard";

    private string _chatInput = string.Empty;
    public string ChatInput
    {
        get => _chatInput;
        set { _chatInput = value; Raise(); }
    }

    // ===== Log Buffer =====
    private readonly StringBuilder _log = new();
    public string LogBuffer => _log.ToString();
    private void Append(string line)
    {
        _log.AppendLine(line);
        Raise(nameof(LogBuffer));
    }

    // ===== Docker-Prozesse (Logs folgen dem Container) =====
    private Process? _aiLogsProc;
    private Process? _meganodeLogsProc;

    // ===== Commands =====
    public ICommand ToggleChatCommand { get; }
    public ICommand SelectTabCommand { get; }
    public ICommand SendChatCommand { get; }
    public ICommand CheckDockerCommand { get; }
    public ICommand CheckAIStatusCommand { get; }
    public ICommand StartAiCommand { get; }
    public ICommand StopAiCommand { get; }
    public ICommand StartMeganodeCommand { get; }

    public MainWindowViewModel()
    {
        ToggleChatCommand = new DelegateCommand(_ =>
        {
            LeftPaneWidth = LeftPaneWidth > 0 ? 0 : 260;
        });

        SelectTabCommand = new DelegateCommand(p =>
        {
            ActiveTab = p?.ToString() ?? "Dashboard";
            Append($"[TAB] {ActiveTab}");
        });

        SendChatCommand = new DelegateCommand(_ =>
        {
            if (!string.IsNullOrWhiteSpace(ChatInput))
            {
                Append($"[CHAT] {ChatInput}");
                ChatInput = string.Empty;
            }
        });

        CheckDockerCommand = new DelegateCommand(_ =>
        {
            var (ok, msg) = DockerService.CheckDockerAvailable();
            Append(ok ? $"[DOCKER] {msg}" : $"[DOCKER-ERR] {msg}");
        });

        CheckAIStatusCommand = new DelegateCommand(_ =>
        {
            var (ok, msg) = DockerService.CheckAIContainer();
            Append($"[AI-STATUS] {msg}");
        });

        StartAiCommand = new DelegateCommand(_ => StartAi());
        StopAiCommand = new DelegateCommand(_ => StopAi());
        StartMeganodeCommand = new DelegateCommand(_ => StartMeganode());
    }

    private static string PathCombine(params string[] parts)
        => System.IO.Path.GetFullPath(System.IO.Path.Combine(parts));

    private void TerminalAttach(Process p, string tag)
    {
        p.OutputDataReceived += (_, e) => { if (e.Data != null) Append($"{tag} {e.Data}"); };
        p.ErrorDataReceived  += (_, e) => { if (e.Data != null) Append($"{tag} ERR: {e.Data}"); };
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
    }

    // ---- AI: start detached, then stream logs ----
    private void StartAi()
    {
        Append("Starte KI (docker compose up ai --build -d) …");
        var cwd = PathCombine(AppContext.BaseDirectory, "..", "..", "..", "deploy");

        // 1) Detached starten
        var start = ProcessManager.StartProcess("docker", "compose up ai --build -d", cwd);

        // 2) Logs folgen (separater Prozess, liefert Output ins Terminal)
        _aiLogsProc?.Kill(entireProcessTree: true);
        _aiLogsProc = ProcessManager.StartProcess("docker", "compose logs -f ai", cwd);
        TerminalAttach(_aiLogsProc, "[AI]");
    }

    private void StopAi()
    {
        Append("Stoppe KI …");
        var cwd = PathCombine(AppContext.BaseDirectory, "..", "..", "..", "deploy");
        _aiLogsProc?.Kill(entireProcessTree: true);
        _aiLogsProc = null;
        var stop = ProcessManager.StartProcess("docker", "compose stop ai", cwd);
        TerminalAttach(stop, "[AI]");
    }

    // ---- Meganode: gleiches Muster ----
    private void StartMeganode()
    {
        Append("Starte Mega-Node …");
        var cwd = PathCombine(AppContext.BaseDirectory, "..", "..", "..", "deploy");

        var start = ProcessManager.StartProcess("docker", "compose up meganode -d", cwd);

        _meganodeLogsProc?.Kill(entireProcessTree: true);
        _meganodeLogsProc = ProcessManager.StartProcess("docker", "compose logs -f meganode", cwd);
        TerminalAttach(_meganodeLogsProc, "[MEGA]");
    }
}
