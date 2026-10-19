using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Blatja.Core;

namespace Blatja.App.Services;

public sealed class RestoreEntry
{
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string Color { get; set; } = "#FF5C50";
    public DateTime When { get; set; }
}

/// <summary>Points de restauration Windows (administrateur requis) et historique des points créés par Blatja.</summary>
public static class RestorePoints
{
    private static string HistoryFile => Path.Combine(AppPaths.Root, "restore-history.json");

    public static List<RestoreEntry> History()
    {
        try { return JsonSerializer.Deserialize<List<RestoreEntry>>(File.ReadAllText(HistoryFile)) ?? new(); }
        catch { return new(); }
    }

    public static DateTime? Recent() =>
        History().OrderByDescending(h => h.When).FirstOrDefault() is { } h && DateTime.Now - h.When < TimeSpan.FromHours(24) ? h.When : null;

    public static (bool Ok, string Message) Create(string name, string description, string color)
    {
        if (!Svc.IsAdmin) return (false, "Les droits administrateur sont nécessaires pour créer un point de restauration.");
        // le nom n'est utilisé que comme étiquette : caractères de contrôle, guillemets et apostrophes retirés
        string safe = new string(name.Where(c => !char.IsControl(c) && c is not ('\'' or '"' or '`' or '$' or ';' or '&' or '|')).ToArray()).Trim();
        if (safe.Length == 0) safe = "Point Blatja";
        if (safe.Length > 60) safe = safe[..60];
        string script = $@"
$ErrorActionPreference = 'Stop'
try {{ New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null }} catch {{}}
try {{ Enable-ComputerRestore -Drive ""$env:SystemDrive\"" }} catch {{}}
Checkpoint-Computer -Description 'Blatja - {safe}' -RestorePointType MODIFY_SETTINGS
";
        string enc = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        var r = Svc.Ctx.Runner.Run("powershell", $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc}", 120000);
        if (!r.Ok)
        {
            string why = r.Output.Split('\n').FirstOrDefault(l => l.Trim().Length > 0)?.Trim() ?? "erreur inconnue";
            Log.Write("Point de restauration : " + why);
            return (false, why.Length > 180 ? why[..180] + "…" : why);
        }
        var list = History();
        list.Add(new RestoreEntry { Name = safe, Description = description, Color = color, When = DateTime.Now });
        Directory.CreateDirectory(AppPaths.Root);
        File.WriteAllText(HistoryFile, JsonSerializer.Serialize(list));
        Svc.Journal.Append(new JournalEntry(DateTime.Now, "restorepoint", "Point de restauration", "Apply", JournalOutcome.Succeeded, safe));
        return (true, "Point de restauration créé.");
    }
}

/// <summary>Utilitaires de dépannage : actions ponctuelles, non réversibles, toujours précédées d'une confirmation.</summary>
public sealed class Utility
{
    public required string Name { get; init; }
    public required string Description { get; init; }
    public required string Icon { get; init; }
    public string? Warning { get; init; }          // si renseigné : confirmation obligatoire
    public bool RequiresAdmin { get; init; }
    public required Func<string> Run { get; init; }
}

public static class Utilities
{
    private static int Cmd(string file, string args, int timeout = 60000)
    {
        var r = Svc.Ctx.Runner.Run(file, args, timeout);
        return r.ExitCode;
    }

    private static long Purge(string dir)
    {
        long bytes = 0;
        if (!Directory.Exists(dir)) return 0;
        foreach (var f in Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories))
            try { bytes += new FileInfo(f).Length; File.Delete(f); } catch { /* fichier en cours d'utilisation */ }
        return bytes / 1048576;
    }

    public static IReadOnlyList<Utility> Build() => new Utility[]
    {
        new() { Name = "Vider le cache DNS", Icon = "IconRefresh", Description = "Corrige les sites qui ne s'ouvrent pas ou les adresses périmées.",
            Run = () => Cmd("ipconfig", "/flushdns") == 0 ? "Cache DNS vidé" : throw new InvalidOperationException("ipconfig a échoué") },
        new() { Name = "Réinitialiser la pile réseau", Icon = "IconNetwork", RequiresAdmin = true,
            Description = "Réinitialise Winsock et la pile IP pour résoudre des problèmes de connexion persistants.",
            Warning = "Les réglages réseau avancés (VPN, proxy, pare-feu personnalisé) peuvent être réinitialisés. Un redémarrage est nécessaire.",
            Run = () =>
            {
                int a = Cmd("netsh", "winsock reset"), b = Cmd("netsh", "int ip reset");
                if (a != 0 || b != 0) throw new InvalidOperationException("netsh a échoué (droits administrateur requis ?)");
                return "Pile réseau réinitialisée — redémarre le PC";
            } },
        new() { Name = "Vider le cache des shaders", Icon = "IconTrash",
            Description = "Supprime les caches DirectX et NVIDIA pour corriger micro-saccades et artefacts. Ils se reconstruisent seuls.",
            Warning = "Les premiers lancements de jeux seront un peu plus lents le temps que le cache se reconstruise.",
            Run = () =>
            {
                string l = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                long mb = Purge(Path.Combine(l, "D3DSCache")) + Purge(Path.Combine(l, "NVIDIA", "DXCache")) + Purge(Path.Combine(l, "NVIDIA", "GLCache"));
                return $"Cache des shaders vidé ({mb} Mo)";
            } },
        new() { Name = "Redémarrer l'explorateur", Icon = "IconRefresh",
            Description = "Relance la barre des tâches et le bureau sans redémarrer le PC.",
            Warning = "Les fenêtres de l'Explorateur de fichiers ouvertes seront fermées.",
            Run = () =>
            {
                Cmd("taskkill", "/f /im explorer.exe");
                Process.Start(new ProcessStartInfo("explorer.exe") { UseShellExecute = true });
                return "Explorateur relancé";
            } },
        new() { Name = "Vérifier les fichiers système", Icon = "IconShield", RequiresAdmin = true,
            Description = "Lance SFC /scannow pour réparer les fichiers Windows corrompus. Peut durer 10 à 20 minutes.",
            Warning = "L'opération est longue et ne peut pas être interrompue proprement.",
            Run = () =>
            {
                int c = Cmd("sfc", "/scannow", 1_800_000);
                return c == 0 ? "Analyse terminée : aucun problème bloquant" : $"Analyse terminée (code {c}) — consulte CBS.log";
            } },
        new() { Name = "Nettoyer les fichiers temporaires", Icon = "IconStorage",
            Description = "Vide les dossiers Temp de l'utilisateur et de Windows (fichiers en cours d'utilisation ignorés).",
            Warning = "Les fichiers supprimés ne vont pas dans la corbeille.",
            Run = () => $"{Purge(Path.GetTempPath()) + Purge(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp"))} Mo libérés" },
        new() { Name = "Ouvrir l'activation de Windows", Icon = "IconKey",
            Description = "Ouvre la page officielle pour saisir ta clé de produit ou activer ta licence numérique.",
            Run = () => { Process.Start(new ProcessStartInfo("ms-settings:activation") { UseShellExecute = true }); return "Page d'activation ouverte"; } },
    };
}

public static class Elevation
{
    /// <summary>Relance l'application avec les droits administrateur (invite UAC) puis ferme l'instance actuelle.</summary>
    public static bool Relaunch()
    {
        try
        {
            string? exe = Environment.ProcessPath;
            if (exe is null) return false;
            Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true, Verb = "runas" });
            return true;
        }
        catch (System.ComponentModel.Win32Exception) { return false; }   // l'utilisateur a refusé l'invite UAC
    }
}
