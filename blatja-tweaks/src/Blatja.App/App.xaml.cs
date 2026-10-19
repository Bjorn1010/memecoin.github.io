using System.Windows;
using Blatja.App.Services;

namespace Blatja.App;

public partial class App : Application
{
    public App()
    {
        DispatcherUnhandledException += (_, e) =>
        {
            Log.Write("Exception non gérée : " + e.Exception);
            Program.Report(e.Exception);
            e.Handled = true;
        };
    }
}
