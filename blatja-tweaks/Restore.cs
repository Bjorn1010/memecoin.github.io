using System.Text;

namespace BlatjaTweaks;

/// <summary>Point de restauration Windows, exigé avant toute modification.</summary>
internal static class Restore
{
    private static readonly string StampFile = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks", "restore.txt");

    /// <summary>Date du dernier point créé par l'application, s'il date de moins de 24 h.</summary>
    public static DateTime? Recent()
    {
        try
        {
            if (DateTime.TryParse(File.ReadAllText(StampFile), out var d) && DateTime.Now - d < TimeSpan.FromHours(24)) return d;
        }
        catch { }
        return null;
    }

    public static (bool Ok, string Message) Create()
    {
        const string script = @"
$ErrorActionPreference = 'Stop'
try { New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -Name SystemRestorePointCreationFrequency -Value 0 -PropertyType DWord -Force | Out-Null } catch {}
try { Enable-ComputerRestore -Drive ""$env:SystemDrive\"" } catch {}
Checkpoint-Computer -Description 'Blatja Tweaks - avant optimisation' -RestorePointType MODIFY_SETTINGS
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
            Directory.CreateDirectory(Path.GetDirectoryName(StampFile)!);
            File.WriteAllText(StampFile, DateTime.Now.ToString("O"));
            return (true, "Point de restauration créé.");
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }
}
