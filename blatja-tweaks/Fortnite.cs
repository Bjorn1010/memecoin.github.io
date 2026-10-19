using System.Diagnostics;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace BlatjaTweaks;

internal static class Fortnite
{
    private const string ExeName = "FortniteClient-Win64-Shipping.exe";
    private static readonly string Rel = Path.Combine("FortniteGame", "Binaries", "Win64", ExeName);

    public static readonly string IniPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "FortniteGame", "Saved", "Config", "WindowsClient", "GameUserSettings.ini");

    public static string BackupPath => IniPath + ".blatja.bak";

    public static bool IsRunning() => Process.GetProcessesByName("FortniteClient-Win64-Shipping").Length > 0;

    /// <summary>Cherche l'exécutable via les manifestes Epic puis les dossiers usuels.</summary>
    public static string? FindExe()
    {
        try
        {
            string manifests = @"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests";
            if (Directory.Exists(manifests))
            {
                foreach (var f in Directory.EnumerateFiles(manifests, "*.item"))
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(f));
                    var r = doc.RootElement;
                    if (r.TryGetProperty("AppName", out var app) && app.GetString() == "Fortnite" &&
                        r.TryGetProperty("InstallLocation", out var loc))
                    {
                        var exe = Path.Combine(loc.GetString() ?? "", Rel);
                        if (File.Exists(exe)) return exe;
                    }
                }
            }
        }
        catch { }

        foreach (var drive in DriveInfo.GetDrives().Where(d => d.DriveType == DriveType.Fixed && d.IsReady))
        {
            foreach (var sub in new[] { @"Program Files\Epic Games\Fortnite", @"Epic Games\Fortnite", @"Games\Epic Games\Fortnite" })
            {
                var exe = Path.Combine(drive.RootDirectory.FullName, sub, Rel);
                if (File.Exists(exe)) return exe;
            }
        }
        return null;
    }

    private static readonly (string Key, string Value)[] LowSettings =
    {
        ("sg.ViewDistanceQuality", "0"), ("sg.ShadowQuality", "0"), ("sg.AntiAliasingQuality", "0"),
        ("sg.TextureQuality", "0"), ("sg.EffectsQuality", "0"), ("sg.PostProcessQuality", "0"),
        ("sg.FoliageQuality", "0"), ("sg.ResolutionQuality", "100.000000"),
        ("bUseVSync", "False"), ("bMotionBlur", "False"),
        ("FrameRateLimit", "0.000000"), ("MenuFrameRateLimit", "0.000000"),
    };

    public static void ApplyLowSettings()
    {
        if (!File.Exists(IniPath)) throw new FileNotFoundException("GameUserSettings.ini introuvable : lance Fortnite une fois.");
        if (IsRunning()) throw new InvalidOperationException("Ferme Fortnite avant d'appliquer ce réglage.");

        if (!File.Exists(BackupPath)) File.Copy(IniPath, BackupPath);

        var attrs = File.GetAttributes(IniPath);
        if (attrs.HasFlag(FileAttributes.ReadOnly)) File.SetAttributes(IniPath, attrs & ~FileAttributes.ReadOnly);

        string text = File.ReadAllText(IniPath);
        foreach (var (key, value) in LowSettings)
            text = Regex.Replace(text, $@"^{Regex.Escape(key)}=[^\r\n]*", $"{key}={value}", RegexOptions.Multiline);
        File.WriteAllText(IniPath, text);
    }

    public static void RestoreSettings()
    {
        if (IsRunning()) throw new InvalidOperationException("Ferme Fortnite avant de restaurer ce réglage.");
        if (File.Exists(BackupPath)) File.Copy(BackupPath, IniPath, overwrite: true);
    }
}
