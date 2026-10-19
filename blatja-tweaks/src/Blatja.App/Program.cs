using System.Runtime.InteropServices;
using Blatja.App.Services;

namespace Blatja.App;

internal static class Program
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    [STAThread]
    public static int Main()
    {
        AppDomain.CurrentDomain.UnhandledException += (_, e) => Report(e.ExceptionObject as Exception);
        try
        {
            Svc.Init();
            var app = new App();
            app.InitializeComponent();
            return app.Run(new Shell.MainWindow());
        }
        catch (Exception ex)
        {
            Report(ex);
            return 1;
        }
    }

    private static bool _reporting;

    /// <summary>Affiche l'erreur une seule fois et l'écrit dans le journal technique.</summary>
    internal static void Report(Exception? ex)
    {
        if (_reporting) return;
        _reporting = true;
        string text = ex?.ToString() ?? "Erreur inconnue";
        Log.Write("Erreur fatale : " + text);
        MessageBoxW(IntPtr.Zero, "Blatja Tweaks a rencontré une erreur :\n\n" + (ex?.Message ?? "Erreur inconnue") + $"\n\nDétails : {AppPaths.Logs}", "Blatja Tweaks", 0x10);
    }
}
