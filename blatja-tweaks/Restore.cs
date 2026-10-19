using System.Text;
using System.Text.Json;

namespace BlatjaTweaks;

public sealed class RestoreEntry
{
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string Color { get; set; } = "#FF3B52";
    public DateTime When { get; set; }
}

/// <summary>Points de restauration Windows, exigés avant toute modification.</summary>
internal static class Restore
{
    private static readonly string Dir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks");
    private static string HistoryFile => Path.Combine(Dir, "restore-history.json");

    public static List<RestoreEntry> History()
    {
        try { return JsonSerializer.Deserialize<List<RestoreEntry>>(File.ReadAllText(HistoryFile)) ?? new(); }
        catch { return new(); }
    }

    /// <summary>Date du dernier point créé par l'application, s'il date de moins de 24 h.</summary>
    public static DateTime? Recent() =>
        History().OrderByDescending(h => h.When).FirstOrDefault() is { } h && DateTime.Now - h.When < TimeSpan.FromHours(24) ? h.When : null;

    public static (bool Ok, string Message) Create(string name, string description, string color)
    {
        string safe = name.Replace("'", "").Replace("\"", "");
        string script = $@"
$ErrorActionPreference = 'Stop'
try {{ New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null }} catch {{}}
try {{ Enable-ComputerRestore -Drive ""$env:SystemDrive\"" }} catch {{}}
Checkpoint-Computer -Description 'Blatja - {safe}' -RestorePointType MODIFY_SETTINGS
";
        try
        {
            string enc = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
            var r = Sh.Run("powershell", $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc}", 120000);
            if (r.Code != 0)
            {
                string why = r.Output.Split('\n').FirstOrDefault(l => l.Trim().Length > 0)?.Trim() ?? "erreur inconnue";
                return (false, why.Length > 160 ? why[..160] + "…" : why);
            }
            var list = History();
            list.Add(new RestoreEntry { Name = name, Description = description, Color = color, When = DateTime.Now });
            Directory.CreateDirectory(Dir);
            File.WriteAllText(HistoryFile, JsonSerializer.Serialize(list));
            return (true, "Point de restauration créé.");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
