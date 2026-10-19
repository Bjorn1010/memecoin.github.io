using System.Windows;

namespace BlatjaTweaks;

public partial class App : Application
{
    public App()
    {
        DispatcherUnhandledException += (_, e) =>
        {
            Program.Report(e.Exception);
            e.Handled = true;
        };
    }
}
