using System.Diagnostics;

namespace BlatjaTweaks;

public sealed class Fix
{
    public required string Name { get; init; }
    public required string Description { get; init; }
    public required string IconPath { get; init; }
    public bool Long { get; init; }
    public required Func<string> Run { get; init; }
}

internal static class Fixes
{
    private static int Cmd(string file, string args, int timeout = 60000) => Sh.Run(file, args, timeout).Code;

    private static long DeleteContents(string dir)
    {
        long n = 0;
        if (!Directory.Exists(dir)) return 0;
        foreach (var f in Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories))
            try { n += new FileInfo(f).Length; File.Delete(f); } catch { }
        return n / (1024 * 1024);
    }

    public static List<Fix> Build() => new()
    {
        new()
        {
            Name = "Vider le cache DNS", IconPath = Icons.Refresh,
            Description = "Corrige les sites qui ne s'ouvrent pas ou les adresses périmées.",
            Run = () => Cmd("ipconfig", "/flushdns") == 0 ? "Cache DNS vidé" : throw new InvalidOperationException("ipconfig a échoué"),
        },
        new()
        {
            Name = "Réinitialiser le réseau", IconPath = Icons.Wifi,
            Description = "Réinitialise Winsock et la pile IP. Redémarrage conseillé ensuite.",
            Run = () =>
            {
                Cmd("netsh", "winsock reset"); Cmd("netsh", "int ip reset"); Cmd("ipconfig", "/flushdns");
                return "Réseau réinitialisé — redémarre le PC";
            },
        },
        new()
        {
            Name = "Réparer Windows Update", IconPath = Icons.Wrench, Long = true,
            Description = "Arrête les services de mise à jour, purge le cache de téléchargement et les relance.",
            Run = () =>
            {
                Cmd("net", "stop wuauserv"); Cmd("net", "stop bits");
                long mb = DeleteContents(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "SoftwareDistribution", "Download"));
                Cmd("net", "start bits"); Cmd("net", "start wuauserv");
                return $"Windows Update réparé ({mb} Mo purgés)";
            },
        },
        new()
        {
            Name = "Vider le cache des shaders", IconPath = Icons.Trash,
            Description = "Supprime le cache DirectX et NVIDIA : règle micro-saccades et artefacts. Se reconstruit tout seul.",
            Run = () =>
            {
                string l = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                long mb = DeleteContents(Path.Combine(l, "D3DSCache")) + DeleteContents(Path.Combine(l, "NVIDIA", "DXCache")) + DeleteContents(Path.Combine(l, "NVIDIA", "GLCache"));
                return $"Cache des shaders vidé ({mb} Mo)";
            },
        },
        new()
        {
            Name = "Redémarrer l'explorateur", IconPath = Icons.Refresh,
            Description = "Relance la barre des tâches et le bureau sans redémarrer le PC.",
            Run = () =>
            {
                Cmd("taskkill", "/f /im explorer.exe");
                Process.Start(new ProcessStartInfo("explorer.exe") { UseShellExecute = true });
                return "Explorateur relancé";
            },
        },
        new()
        {
            Name = "Vérifier les fichiers système", IconPath = Icons.Shield, Long = true,
            Description = "Lance SFC /scannow pour réparer les fichiers Windows corrompus. Peut durer 10 à 20 minutes.",
            Run = () =>
            {
                int c = Cmd("sfc", "/scannow", 1_800_000);
                return c == 0 ? "Analyse terminée : aucun problème bloquant" : $"Analyse terminée (code {c}) — voir CBS.log";
            },
        },
        new()
        {
            Name = "Nettoyer les fichiers temporaires", IconPath = Icons.Storage,
            Description = "Vide les dossiers Temp de l'utilisateur et de Windows.",
            Run = () => $"{Tweaks.CleanTemp()} Mo libérés",
        },
        new()
        {
            Name = "Activation de Windows", IconPath = Icons.Key,
            Description = "Ouvre la page officielle pour saisir ta clé ou activer ta licence numérique.",
            Run = () =>
            {
                Process.Start(new ProcessStartInfo("ms-settings:activation") { UseShellExecute = true });
                return "Page d'activation ouverte";
            },
        },
    };
}
