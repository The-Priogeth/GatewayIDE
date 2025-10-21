using System;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using GatewayIDE.App.ViewModels;

namespace GatewayIDE.App;

public partial class App : Application
{
    public App()
    {
        // Globale Crash-Logger nur EINMAL im Konstruktor registrieren
        AppDomain.CurrentDomain.UnhandledException += CurrentDomain_UnhandledException;
        TaskScheduler.UnobservedTaskException += TaskScheduler_UnobservedTaskException;
    }

    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new MainWindow
            {
                DataContext = new MainWindowViewModel(),
            };
        }
        base.OnFrameworkInitializationCompleted();
    }

    private static void CurrentDomain_UnhandledException(object? sender, UnhandledExceptionEventArgs e)
    {
        try
        {
            var msg = "[UNHANDLED] " + (e.ExceptionObject?.ToString() ?? "unknown");
            System.IO.File.AppendAllText("GatewayIDE-crash.log", msg + Environment.NewLine);
        }
        catch { /* ignore */ }
    }

    private static void TaskScheduler_UnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        try
        {
            var msg = "[UNOBSERVED] " + e.Exception;
            System.IO.File.AppendAllText("GatewayIDE-crash.log", msg + Environment.NewLine);
        }
        catch { /* ignore */ }
    }
}
