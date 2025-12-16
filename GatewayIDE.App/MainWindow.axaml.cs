using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;

namespace GatewayIDE.App;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        // Event auch manuell verbinden, falls XAML-Bindung zickt
        AddHandler(DoubleTappedEvent, TitleDragZone_DoubleTapped!, handledEventsToo: true);
    }

    private void TitleDragZone_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
            BeginMoveDrag(e);
    }

    private void TitleDragZone_DoubleTapped(object? sender, RoutedEventArgs e)
    {
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
    }
}
