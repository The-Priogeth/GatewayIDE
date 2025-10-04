using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading;
using Avalonia.Threading;
using System.Threading.Tasks;
using System.Windows.Input;
using GatewayIDE.App.Services.Processes;
using GatewayIDE.App.Services.AI;

namespace GatewayIDE.App.ViewModels;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    // === UI State ===
    private void Ui(Action action) => Dispatcher.UIThread.Post(action);
    private double _leftPaneWidth = 260;
    public double LeftPaneWidth { get => _leftPaneWidth; set { _leftPaneWidth = value; Raise(); } }

    private string _activeTab = "Dashboard";
    public string ActiveTab
    {
        get => _activeTab;
        set { _activeTab = value; Raise(); Raise(nameof(IsDashboard)); Raise(nameof(IsDocker)); }
    }
    public bool IsDashboard => ActiveTab == "Dashboard";
    public bool IsDocker => ActiveTab == "Docker";

    // === Chat (nur KI-Dialog) ===
    private readonly StringBuilder _chat = new();
    public string ChatBuffer => _chat.ToString();
    private void ChatAppend(string line) => Ui(() => { _chat.AppendLine(line); Raise(nameof(ChatBuffer)); });

    private string _chatInput = string.Empty;
    public string ChatInput { get => _chatInput; set { _chatInput = value; Raise(); } }

    // === Terminals ===
    private readonly StringBuilder _terminal = new();
    public string TerminalBuffer => _terminal.ToString();
    private void TermAppend(string line) => Ui(() => { _terminal.AppendLine(line); Raise(nameof(TerminalBuffer)); });

    private readonly StringBuilder _dockerOut = new();
    public string DockerOutBuffer => _dockerOut.ToString();
    private void DockerOutAppend(string line) => Ui(() => { _dockerOut.AppendLine(line); Raise(nameof(DockerOutBuffer)); });

    private readonly StringBuilder _dockerErr = new();
    public string DockerErrBuffer => _dockerErr.ToString();
    private void DockerErrAppend(string line) => Ui(() => { _dockerErr.AppendLine(line); Raise(nameof(DockerErrBuffer)); });

    // === gRPC (Echo als Platzhalter) ===
    private readonly AIClientService _aiClient = new("http://localhost:50051");

    // === Log-Prozesse ===
    private Process? _aiLogsProc;
    private Process? _meganodeLogsProc;

    // === Commands ===
    public ICommand ToggleChatCommand { get; }
    public ICommand SelectTabCommand { get; }
    public ICommand SendChatCommand { get; }
    public ICommand RebuildGatewayCommand { get; }
    public ICommand StartGatewayCommand { get; }
    public ICommand StopGatewayCommand { get; }
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
            TermAppend($"[TAB] {ActiveTab}");
        });

        SendChatCommand = new DelegateCommand(async _ => await SendChatAsync());

        RebuildGatewayCommand = new DelegateCommand(_ => RebuildGateway());
        StartGatewayCommand   = new DelegateCommand(_ => StartGateway());
        StopGatewayCommand    = new DelegateCommand(_ => StopGateway());

        StartMeganodeCommand = new DelegateCommand(_ => StartMeganode());
    }

    // === Chat to KI (Echo als Stub) ===
    private async Task SendChatAsync()
    {
        if (string.IsNullOrWhiteSpace(ChatInput)) return;
        var user = ChatInput.Trim();
        ChatInput = string.Empty;
        ChatAppend($"[User] {user}");
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            var reply = await _aiClient.EchoAsync(user, cts.Token);
            ChatAppend($"[KI] {reply}");
        }
        catch (Exception ex)
        {
            ChatAppend($"[KI-ERR] {ex.Message}");
        }
    }

    // === Helpers ===
    private static string PathCombine(params string[] parts)
        => System.IO.Path.GetFullPath(System.IO.Path.Combine(parts));

    private static void HookProcessToBuffers(
        Process proc,
        Action<string> onOut,
        Action<string> onErr)
    {
        proc.OutputDataReceived += (_, e) => { if (e.Data != null) onOut(e.Data); };
        proc.ErrorDataReceived  += (_, e) => { if (e.Data != null) onErr(e.Data); };
        proc.BeginOutputReadLine();
        proc.BeginErrorReadLine();
    }

    private void AttachProcToDockerTerminals(Process p, string tag)
    {
        p.OutputDataReceived += (_, e) => { if (e.Data != null) { TermAppend($"{tag} {e.Data}"); DockerOutAppend($"{tag} {e.Data}"); } };
        p.ErrorDataReceived  += (_, e) => { if (e.Data != null) { TermAppend($"{tag} ERR: {e.Data}"); DockerErrAppend($"{tag} {e.Data}"); } };
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
    }

    private void RebuildGateway()
    {
        TermAppend("[GATEWAY] Full Rebuild (wipe + build --no-cache + up -d) …");
        var (wipe, build, up) = DockerService.FullRebuild();
        AttachProcToDockerTerminals(wipe,  "[WIPE]");
        if (build != null) AttachProcToDockerTerminals(build, "[BUILD]");
        if (up != null)
        {
            AttachProcToDockerTerminals(up,    "[UP]");
            // live logs im Anschluss
            var logs = DockerService.TailGatewayLogs();
            AttachProcToDockerTerminals(logs,  "[LOG]");
        }
    }

    private void StartGateway()
    {
        TermAppend("[GATEWAY] Start …");
        var up = DockerService.StartGateway();
        AttachProcToDockerTerminals(up, "[UP]");
        var logs = DockerService.TailGatewayLogs();
        AttachProcToDockerTerminals(logs, "[LOG]");
    }

    private void StopGateway()
    {
        TermAppend("[GATEWAY] Stop …");
        var stop = DockerService.StopGateway();
        AttachProcToDockerTerminals(stop, "[STOP]");
    }


    private void StartMeganode()
    {
        try
        {
            TermAppend("Starte Mega-Node …");
            var cwd = PathCombine(AppContext.BaseDirectory, "..", "..", "..", "deploy");
            if (!Directory.Exists(cwd)) { TermAppend($"[ERR] deploy Pfad fehlt: {cwd}"); return; }

            ProcessManager.StartProcess("docker", "compose up meganode -d", cwd);

            try { _meganodeLogsProc?.Kill(entireProcessTree: true); } catch { /* ignore */ }
            _meganodeLogsProc = ProcessManager.StartProcess("docker", "compose logs -f meganode", cwd);

            _meganodeLogsProc.OutputDataReceived += (_, e) => { if (e.Data != null) { TermAppend("[MEGA] " + e.Data); DockerOutAppend("[MEGA] " + e.Data); } };
            _meganodeLogsProc.ErrorDataReceived  += (_, e) => { if (e.Data != null) { TermAppend("[MEGA] ERR: " + e.Data); DockerErrAppend("[MEGA] " + e.Data); } };
            _meganodeLogsProc.BeginOutputReadLine();
            _meganodeLogsProc.BeginErrorReadLine();
        }
        catch (Exception ex)
        {
            TermAppend("[StartMeganode-EX] " + ex.Message);
        }
    }
}
