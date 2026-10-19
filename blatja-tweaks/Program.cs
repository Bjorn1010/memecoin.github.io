using System.Runtime.InteropServices;

namespace BlatjaTweaks;

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
            var app = new App();
            app.InitializeComponent();
            return app.Run();
        }
        catch (Exception ex)
        {
            Report(ex);
            return 1;
        }
    }

    internal static void Report(Exception? ex)
    {
        string text = ex?.ToString() ?? "Erreur inconnue";
        try
        {
            File.WriteAllText(Path.Combine(Path.GetTempPath(), "BlatjaTweaks-erreur.txt"), text);
        }
        catch { }
        MessageBoxW(IntPtr.Zero, "Blatja Tweaks n'a pas pu démarrer :\n\n" + text, "Blatja Tweaks", 0x10);
    }
}
