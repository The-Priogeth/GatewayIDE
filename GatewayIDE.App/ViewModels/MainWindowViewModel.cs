// === MainWindowViewModel — Refactor Pass 1/3 (reorder + comments only, no renames/logic changes) ===
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Collections.ObjectModel;
using System.Windows.Input;
using System.Net.Http.Json;
using System.Text.Json;
using Avalonia.Media;
using Avalonia.Controls;

namespace GatewayIDE.App.ViewModels;

public sealed class MainWindowViewModel : INotifyPropertyChanged
{
    #region ===== INotifyPropertyChanged =====
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Tabs & Sichtbarkeiten
    // ---------------------------------------------------------------------------------------------
    #region ===== Tabs & Sichtbarkeit =====
    private string _activeTab = "Dashboard";
    public string ActiveTab
    {
        get => _activeTab;
        set
        {
            _activeTab = value;
            Raise();
            Raise(nameof(IsDashboard));
            Raise(nameof(IsDocker));
            Raise(nameof(IsKiSystem));
        }
    }

    private const string TAB_DASH = "Dashboard";
    private const string TAB_DOCK = "Docker";
    private const string TAB_KI   = "KI System";

    public bool IsDashboard => ActiveTab == TAB_DASH;
    public bool IsDocker    => ActiveTab == TAB_DOCK;
    public bool IsKiSystem  => ActiveTab == TAB_KI;
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Chat-Bereich (linke Seitenleiste)
    // ---------------------------------------------------------------------------------------------
    #region ===== Chat (Sidebar) =====
    public ObservableCollection<ChatLine> ChatLines { get; } = new();

    private double _leftPaneWidth = 260;
    public double LeftPaneWidth
    {
        get => _leftPaneWidth;
        set { _leftPaneWidth = value; Raise(); }
    }

    private readonly StringBuilder _chat = new();
    public string ChatBuffer => _chat.ToString();

    private string _chatInput = string.Empty;
    public string ChatInput
    {
        get => _chatInput;
        set { _chatInput = value; Raise(); }
    }

    public int ChatSelectedIndex
    {
        get => _chatSelectedIndex;
        set { _chatSelectedIndex = value; Raise(); }
    }
    private int _chatSelectedIndex = -1;

    public sealed class ChatLine
    {
        public string Text { get; }
        public IBrush Brush { get; }
        public ChatLine(string text, IBrush brush) { Text = text; Brush = brush; }
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  HTTP-Client + Chat-API Contracts
    // ---------------------------------------------------------------------------------------------
    #region ===== HTTP Client / Contracts =====
    private static readonly HttpClient _http = new()
    {
        BaseAddress = new Uri("http://localhost:8080/")
    };

    private sealed class ChatResponse
    {
        public List<ResponseItem>? Responses { get; set; }
    }
    private sealed class ResponseItem
    {
        public string? agent { get; set; }
        public string? content { get; set; }
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Chat-Senden → Antwortverteilung auf Threads
    // ---------------------------------------------------------------------------------------------
    #region ===== Prompt Senden =====
    private async Task SendPromptAsync(string prompt)
    {
        try
        {
            var req = new { prompt };
            using var resp = await _http.PostAsJsonAsync("chat", req);
            resp.EnsureSuccessStatusCode();

            var json = await resp.Content.ReadAsStringAsync();
            var obj  = JsonSerializer.Deserialize<ChatResponse>(
                json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            var items = obj?.Responses ?? new List<ResponseItem>();
            if (items.Count == 0)
            {
                AppendThreadMessage(ThreadId.T3, "⚠️ Backend lieferte keine Antworten.");
            }
            else
            {
                foreach (var it in items)
                    AppendAgentReply(it.agent, it.content);
            }
        }
        catch (Exception ex)
        {
            AppendThreadMessage(ThreadId.T3, $"❌ Chat-Fehler: {ex.Message}");
        }
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Dashboard: Terminal-Ausgabe
    // ---------------------------------------------------------------------------------------------
    #region ===== Dashboard Terminal =====
    private readonly StringBuilder _term = new();
    public string TerminalBuffer => _term.ToString();

    private void AppendTerm(string line)
    {
        _term.AppendLine(line);
        Raise(nameof(TerminalBuffer));
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  System-Status (Docker Desktop / Image / Container) + Farbbindungen
    // ---------------------------------------------------------------------------------------------
    #region ===== System Status + Brushes =====
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
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Docker/Gateway-Logbuffer (oben links/rechts + mitte + IO)
    // ---------------------------------------------------------------------------------------------
    #region ===== Log-Buffer (Docker/Gateway) =====
    private readonly StringBuilder _dockerOut = new();
    private readonly StringBuilder _dockerErr = new();
    private readonly StringBuilder _gatewayLog = new();
    private readonly StringBuilder _containerIO = new();

    public string GatewayLogBuffer => _gatewayLog.ToString();
    public string DockerOutBuffer  => _dockerOut.ToString();
    public string DockerErrBuffer  => _dockerErr.ToString();
    public string ContainerIOBuffer => _containerIO.ToString();

    private void AppendGateway(string s)
    {
        _gatewayLog.Append(s);
        Raise(nameof(GatewayLogBuffer));
        Raise(nameof(GatewayLogCaret));
    }
    private void AppendDockerOut(string s)
    {
        _dockerOut.Append(s);
        Raise(nameof(DockerOutBuffer));
        Raise(nameof(DockerOutCaret));
    }

    private void AppendDockerErr(string s)
    {
        _dockerErr.Append(s);
        Raise(nameof(DockerErrBuffer));
        Raise(nameof(DockerErrCaret));
    }

    #endregion

    // ---------------------------------------------------------------------------------------------
    //  KI-System Thread-Buffer (T2/T4/T5/T6) + Carets (AutoScroll)
    // ---------------------------------------------------------------------------------------------
    #region ===== KI-System Threads + Carets =====
    private readonly StringBuilder _t2 = new(), _t4 = new(), _t5 = new(), _t6 = new();
    public string T2Buffer => _t2.ToString();
    public string T4Buffer => _t4.ToString();
    public string T5Buffer => _t5.ToString();
    public string T6Buffer => _t6.ToString();

    public int GatewayLogCaret  => _gatewayLog.Length;
    public int DockerOutCaret   => _dockerOut.Length;
    public int DockerErrCaret   => _dockerErr.Length;
    public int ContainerIOCaret => _containerIO.Length;

    public int T2Caret => _t2.Length;
    public int T4Caret => _t4.Length;
    public int T5Caret => _t5.Length;
    public int T6Caret => _t6.Length;
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Thread-Message-Routing (Chat / KI-System)
    // ---------------------------------------------------------------------------------------------
    #region ===== Thread Message Handling =====

    public enum ThreadId { T1 = 1, T2 = 2, T3 = 3, T4 = 4, T5 = 5, T6 = 6 }

    public void AppendThreadMessage(ThreadId id, string text)
    {
        switch (id)
        {
            case ThreadId.T1:
                ChatLines.Add(new ChatLine(text, Brushes.DodgerBlue));
                ChatSelectedIndex = ChatLines.Count - 1; // autoscroll
                break;

            case ThreadId.T3:
                ChatLines.Add(new ChatLine(text, Brushes.OrangeRed));
                ChatSelectedIndex = ChatLines.Count - 1;
                break;

            case ThreadId.T2: _t2.AppendLine(text); Raise(nameof(T2Buffer)); Raise(nameof(T2Caret)); break;
            case ThreadId.T4: _t4.AppendLine(text); Raise(nameof(T4Buffer)); Raise(nameof(T4Caret)); break;
            case ThreadId.T5: _t5.AppendLine(text); Raise(nameof(T5Buffer)); Raise(nameof(T5Caret)); break;
            case ThreadId.T6: _t6.AppendLine(text); Raise(nameof(T6Buffer)); Raise(nameof(T6Caret)); break;
        }
    }

    private void AppendAgentReply(string? agent, string? content)
    {
        if (string.IsNullOrWhiteSpace(content)) return;
        var a = (agent ?? "").Trim().ToUpperInvariant();

        switch (a)
        {
            case "SOM":
                // Sichtbar im Chat-Thread (T1)
                AppendThreadMessage(ThreadId.T1, $"[SOM]\n{content}");
                break;

            case "SOM:INNER":
                AppendThreadMessage(ThreadId.T2, content!);
                break;

            case "TASKMANAGER":
                AppendThreadMessage(ThreadId.T4, $"[TaskManager]\n{content}");
                break;

            case "LIBRARIAN":
                AppendThreadMessage(ThreadId.T5, $"[Librarian]\n{content}");
                break;

            case "TRAINER":
                AppendThreadMessage(ThreadId.T6, $"[Trainer]\n{content}");
                break;

            case "RETURN":
                AppendThreadMessage(ThreadId.T3, content);
                break;

            default:
                // Unbekannter Agent → zur Sicherheit in T1 sichtbar machen
                AppendThreadMessage(ThreadId.T1, $"[{(agent ?? "HMA")}]\n{content}");
                break;
        }
    }

    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Command-Deklarationen (public Properties für XAML-Bindings)
    // ---------------------------------------------------------------------------------------------
    #region ===== Command Properties =====

    // Docker-UI-Layout
    public ICommand ExpandGatewayOnlyCommand { get; }


    // UI-Navigation / Chat
    public ICommand ToggleChatCommand { get; }
    public ICommand SelectTabCommand { get; }
    public ICommand SendChatCommand { get; }

    // Docker-Aktionen
    public ICommand StartMeganodeCommand { get; }
    public ICommand RebuildGatewayCommand { get; }
    public ICommand StartGatewayCommand { get; }
    public ICommand StopGatewayCommand { get; }
    public ICommand RemoveGatewayContainerCommand { get; }
    public ICommand ClearAllLogsCommand { get; }
    public ICommand ExecuteInContainerCommand { get; }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Docker-Layout-Properties (Grid-Bindings)
    // ---------------------------------------------------------------------------------------------
    #region ===== Layout-Bindings (Docker-Split) =====
    // OBERES GRID – innere Zeile & Spalten
    // 50/50 im oberen Grid: Zeile 0 = Star, Zeile 1 = Star
    private GridLength _topSmallRowHeight = GridLength.Star;
    public GridLength TopSmallRowHeight
    {
        get => _topSmallRowHeight;
        set { _topSmallRowHeight = value; Raise(); }
    }

    private GridLength _topLeftColWidth = GridLength.Star;
    public GridLength TopLeftColWidth
    {
        get => _topLeftColWidth;
        set { _topLeftColWidth = value; Raise(); }
    }

    private GridLength _topRightColWidth = GridLength.Star;
    public GridLength TopRightColWidth
    {
        get => _topRightColWidth;
        set { _topRightColWidth = value; Raise(); }
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Konstruktor — Command-Registrierung
    // ---------------------------------------------------------------------------------------------
    #region ===== Konstruktor =====
    // Toggle-Status nur EINMAL definieren
    private bool _gatewayExpanded = false;

    // Button-Label nur EINMAL definieren
    private string _expandLabel = "⤢ Expand Gateway";
    public string ExpandLabel
    {
        get => _expandLabel;
        private set { _expandLabel = value; Raise(); }
    }

    public MainWindowViewModel()
    {
        // --- Layout-Commands ---
        ExpandGatewayOnlyCommand = new DelegateCommand(_ =>
        {
            _gatewayExpanded = !_gatewayExpanded;
            ExpandLabel      = _gatewayExpanded ? "⤡ Restore Layout" : "⤢ Expand Gateway";

            // einziges Toggle-Kriterium: die kleine obere Zeile
            TopSmallRowHeight = _gatewayExpanded
                ? new GridLength(0)    // Out/Err aus
                : GridLength.Star;     // Out/Err = 50% (oben)

            // Sicherheit: Spalten oben bleiben 50/50
            TopLeftColWidth  = GridLength.Star;
            TopRightColWidth = GridLength.Star;
        });


        // --- UI-Navigation + Chat ---
        ToggleChatCommand = new DelegateCommand(_ =>
            LeftPaneWidth = LeftPaneWidth > 0 ? 0 : 260);

        SelectTabCommand = new DelegateCommand(async p =>
        {
            ActiveTab = p?.ToString() ?? "Dashboard";
            AppendTerm($"[TAB] {ActiveTab}");
            if (IsDashboard) await RefreshSystemStatusAsync();
        });

        SendChatCommand = new DelegateCommand(async _ =>
        {
            var text = (ChatInput ?? "").Trim();
            if (string.IsNullOrWhiteSpace(text)) return;

            AppendThreadMessage(ThreadId.T1, $"[YOU] {text}");
            _chat.AppendLine($"[YOU] {text}");
            Raise(nameof(ChatBuffer));

            var sendText = text;
            ChatInput = string.Empty;
            await SendPromptAsync(sendText);
        });

        // --- Docker Commands ---
        RebuildGatewayCommand         = new DelegateCommand(async _ => await FullRebuildAsync());
        StartGatewayCommand           = new DelegateCommand(async _ => await StartGatewayAsync());
        StopGatewayCommand            = new DelegateCommand(async _ => await StopGatewayAsync());
        RemoveGatewayContainerCommand = new DelegateCommand(async _ => await RemoveGatewayContainerAsync());
        StartMeganodeCommand          = new DelegateCommand(_ => StartMeganode());
        ClearAllLogsCommand           = new DelegateCommand(_ => ClearAllLogs());
        ExecuteInContainerCommand     = new DelegateCommand(async p => await ExecuteInContainerAsync(p as string));

        // Initialstatus laden
        _ = RefreshSystemStatusAsync();
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Kleine Hilfsroutinen (ClearAllLogs, Kill, StartMeganode)
    // ---------------------------------------------------------------------------------------------
    #region ===== Kleine Utilities =====
    private void ClearAllLogs()
    {
        _dockerOut.Clear();   Raise(nameof(DockerOutBuffer));   Raise(nameof(DockerOutCaret));
        _dockerErr.Clear();   Raise(nameof(DockerErrBuffer));   Raise(nameof(DockerErrCaret));
        _gatewayLog.Clear();  Raise(nameof(GatewayLogBuffer));  Raise(nameof(GatewayLogCaret));
        _containerIO.Clear(); Raise(nameof(ContainerIOBuffer)); Raise(nameof(ContainerIOCaret));
    }

    private void Kill(ref Process? proc)
    {
        try
        {
            if (proc != null && !proc.HasExited)
                proc.Kill(entireProcessTree: true);
        }
        catch { /* ignore */ }
        proc = null;
    }

    private void StartMeganode()
    {
        AppendTerm("Starte Mega-Node …");
        var start = RunDocker("compose up meganode -d");
        AttachToDocker(start, "[MEGA-UP]");

        Kill(ref _meganodeLogsProc);
        _meganodeLogsProc = RunDocker("compose logs -f meganode");
        AttachToDocker(_meganodeLogsProc, "[MEGA]");
    }
    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Verbleibende Felder (Prozesse, CTS) + ContainerCommand Property
    // ---------------------------------------------------------------------------------------------
    #region ===== Prozesse / CTS / Eingabe =====

    // Docker log processes
    private Process? _meganodeLogsProc;

    // Tail-Guard für Gateway-Runtime-Logs (nur EIN logs -f)
    private CancellationTokenSource? _gatewayTailCts;

    // Eingabe unten (UNTERES GRID)
    private string _containerCommand = string.Empty;
    public string ContainerCommand
    {
        get => _containerCommand;
        set { _containerCommand = value; Raise(); }
    }

    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Repo-/Pfad-Ermittlung für docker compose (deploy-Ordner)
    // ---------------------------------------------------------------------------------------------
    #region ===== Repository-Pfad-Helper =====

    private static string FindRepoRoot()
    {
        // Lauf nach oben, bis wir eine valide Repo-Wurzel finden
        var dir = AppContext.BaseDirectory;
        while (!string.IsNullOrEmpty(dir))
        {
            var hasSln   = File.Exists(Path.Combine(dir, "GatewayIDE.sln"));
            var hasDeploy= Directory.Exists(Path.Combine(dir, "deploy"));
            if (hasSln || hasDeploy) return dir;

            var parent = Directory.GetParent(dir);
            if (parent == null) break;
            dir = parent.FullName;
        }

        // Fallback: aktuelles Arbeitsverzeichnis
        return Directory.GetCurrentDirectory();
    }

    private static string RepoDeployDir()
    {
        var root   = FindRepoRoot();
        var deploy = Path.Combine(root, "deploy");
        return Directory.Exists(deploy) ? deploy : root;
    }

    #endregion

    // ---------------------------------------------------------------------------------------------
    //  Prozess-Helfer (Start + Attach für Docker/Gateway)
    // ---------------------------------------------------------------------------------------------
    #region ===== Prozess-Helfer =====

    private Process RunDocker(string args)
        => GatewayIDE.App.Services.Processes.ProcessManager.StartProcess("docker", args, RepoDeployDir());

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

        p.OutputDataReceived += (_, e) =>
        {
            if (!string.IsNullOrEmpty(e.Data))
                AppendGateway(e.Data + Environment.NewLine);
        };
        p.ErrorDataReceived += (_, e) =>
        {
            if (!string.IsNullOrEmpty(e.Data))
                AppendGateway(e.Data + Environment.NewLine);
        };

        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
    }

    #endregion

    // ---------------------------------------------------------------------------------------------
    //  DockerService-Bridges (Build/Start/Stop/Remove/Status/Exec)
    // ---------------------------------------------------------------------------------------------
    #region ===== DockerService-Bridges =====

    private async Task FullRebuildAsync()
    {
        try
        {
            _dockerOut.Clear();  Raise(nameof(DockerOutBuffer));
            _dockerErr.Clear();  Raise(nameof(DockerErrBuffer));
            _gatewayLog.Clear(); Raise(nameof(GatewayLogBuffer));

            await GatewayIDE.App.Services.Processes.DockerService.FullRebuildAsync(
                AppendDockerOut, AppendDockerErr);

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
        await GatewayIDE.App.Services.Processes.DockerService.StartGatewayAsync(
            AppendDockerOut, AppendDockerErr);

        _gatewayTailCts?.Cancel();
        _gatewayTailCts = new CancellationTokenSource();
        _ = GatewayIDE.App.Services.Processes.DockerService.TailGatewayLogsAsync(
            AppendGateway, AppendGateway, _gatewayTailCts.Token);

        await RefreshSystemStatusAsync();
    }

    private async Task StopGatewayAsync()
    {
        _gatewayTailCts?.Cancel();
        _gatewayTailCts = null;

        await GatewayIDE.App.Services.Processes.DockerService.StopGatewayAsync(
            AppendDockerOut, AppendDockerErr);

        await RefreshSystemStatusAsync();
    }

    private async Task RemoveGatewayContainerAsync()
    {
        try
        {
            AppendDockerOut("[REMOVE] Entferne gateway-container …" + Environment.NewLine);

            await GatewayIDE.App.Services.Processes.DockerService.RemoveGatewayContainerAsync(
                AppendDockerOut, AppendDockerErr);

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
            var desktop = await GatewayIDE.App.Services.Processes.DockerService.GetDockerDesktopStatusAsync();
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

            DockerImageStatus = await GatewayIDE.App.Services.Processes.DockerService.IsImageAvailableAsync()
                ? "Available" : "None";

            var st = await GatewayIDE.App.Services.Processes.DockerService.GetGatewayStatusAsync();
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

    private async Task ExecuteInContainerAsync(string? paramText = null)
    {
        var cmd = (paramText ?? ContainerCommand ?? string.Empty).Trim();
        if (string.IsNullOrEmpty(cmd)) return;

        _containerIO.AppendLine($"> {cmd}");
        Raise(nameof(ContainerIOBuffer));
        Raise(nameof(ContainerIOCaret));

        await GatewayIDE.App.Services.Processes.DockerService.ExecInGatewayAsync(
            cmd,
            o => {
                _containerIO.Append(o);
                Raise(nameof(ContainerIOBuffer));
                Raise(nameof(ContainerIOCaret));
            },
            e => {
                _containerIO.Append(e);
                Raise(nameof(ContainerIOBuffer));
                Raise(nameof(ContainerIOCaret));
            }
        );

        ContainerCommand = string.Empty;
        Raise(nameof(ContainerCommand));
    }

    #endregion
}