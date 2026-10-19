using System.Diagnostics;
using Blatja.Core;

namespace Blatja.App.Services;

public static class AppPaths
{
    public static readonly string Root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks");
    public static string Backups => Path.Combine(Root, "backups");
    public static string Journal => Path.Combine(Root, "journal.jsonl");
    public static string Settings => Path.Combine(Root, "settings.json");
    public static string Logs => Path.Combine(Root, "logs");
}

/// <summary>Journal technique (fichiers texte rotatifs par jour). N'enregistre jamais de secret ni de donnée personnelle.</summary>
public static class Log
{
    private static readonly object Lock = new();

    public static void Write(string message)
    {
        try
        {
            lock (Lock)
            {
                Directory.CreateDirectory(AppPaths.Logs);
                File.AppendAllText(Path.Combine(AppPaths.Logs, $"blatja-{DateTime.Now:yyyy-MM-dd}.log"), $"{DateTime.Now:HH:mm:ss.fff} {message}{Environment.NewLine}");
                // conserve 14 jours
                foreach (var old in Directory.GetFiles(AppPaths.Logs, "blatja-*.log").Where(f => File.GetLastWriteTime(f) < DateTime.Now.AddDays(-14)))
                    File.Delete(old);
            }
        }
        catch { /* le journal ne doit jamais faire échouer l'application */ }
    }
}

/// <summary>Conteneur des services de l'application (assemblé une seule fois au démarrage).</summary>
public static class Svc
{
    public static SystemContext Ctx { get; private set; } = null!;
    public static OptimizationEngine Engine { get; private set; } = null!;
    public static IReadOnlyList<Operation> Catalog { get; private set; } = Array.Empty<Operation>();
    public static GameDetector Games { get; private set; } = null!;
    public static StartupManager Startup { get; private set; } = null!;
    public static IBackupStore Backups { get; private set; } = null!;
    public static IJournal Journal { get; private set; } = null!;
    public static MetricsService Metrics { get; private set; } = null!;
    public static ProcessMonitor Processes { get; private set; } = new();
    public static GpuService Gpu { get; private set; } = new();
    public static AppSettings Settings { get; set; } = new();
    public static bool IsAdmin => Ctx.Info.IsAdmin;

    public static void Init()
    {
        Settings = AppSettings.Load(AppPaths.Settings);
        Ctx = new SystemContext(new WinRegistry(), new WinRunner(), new WinFiles(), new WinInfo());
        Backups = new JsonBackupStore(AppPaths.Backups);
        Journal = new FileJournal(AppPaths.Journal);
        Engine = new OptimizationEngine(Ctx, Backups, Journal, Log.Write);

        string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        Games = new GameDetector(Ctx, programData, appData);
        Catalog = OperationCatalog.Build(Games, local, name => Process.GetProcessesByName(name).Length > 0);
        Startup = new StartupManager(Ctx,
            Environment.GetFolderPath(Environment.SpecialFolder.Startup),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup));
        Metrics = new MetricsService(Gpu);
        Log.Write($"Démarrage — {Ctx.Info.Description}, administrateur : {Ctx.Info.IsAdmin}");
    }
}
