namespace Blatja.Core;

public sealed record StartupEntry(string Name, string Command, string Source, bool Enabled, bool NeedsAdmin)
{
    internal string ApprovedKey { get; init; } = "";
    internal string ApprovedHive { get; init; } = "";
}

/// <summary>Applications lancées au démarrage de Windows. Activation/désactivation via StartupApproved : réversible, rien n'est supprimé.</summary>
public sealed class StartupManager
{
    private const string Run = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string Approved = @"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved";
    private readonly SystemContext _c;
    private readonly string _userStartup, _commonStartup;

    public StartupManager(SystemContext c, string userStartupFolder = "", string commonStartupFolder = "")
    {
        _c = c; _userStartup = userStartupFolder; _commonStartup = commonStartupFolder;
    }

    public IReadOnlyList<StartupEntry> List()
    {
        var list = new List<StartupEntry>();
        AddRegistry(list, "HKCU", Run, "Run", "Session (utilisateur)", false);
        AddRegistry(list, "HKLM", Run, "Run", "Tous les utilisateurs", true);
        AddRegistry(list, "HKLM", @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32", "Tous les utilisateurs (32 bits)", true);
        AddFolder(list, _userStartup, "HKCU", "Dossier Démarrage (utilisateur)", false);
        AddFolder(list, _commonStartup, "HKLM", "Dossier Démarrage (commun)", true);
        return list.OrderBy(e => e.Name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    private void AddRegistry(List<StartupEntry> list, string hive, string path, string approvedSub, string source, bool admin)
    {
        string full = $@"{hive}\{path}";
        foreach (var name in _c.Registry.ValueNames(full))
        {
            string cmd = _c.Registry.Get(full, name)?.Data as string ?? "";
            list.Add(new StartupEntry(name, cmd, source, IsEnabled(hive, approvedSub, name), admin) { ApprovedKey = approvedSub, ApprovedHive = hive });
        }
    }

    private void AddFolder(List<StartupEntry> list, string folder, string hive, string source, bool admin)
    {
        if (folder.Length == 0 || !_c.Files.DirectoryExists(folder)) return;
        foreach (var f in _c.Files.EnumerateFiles(folder, "*"))
        {
            string name = f[(f.LastIndexOfAny(new[] { '\\', '/' }) + 1)..];
            if (name.Equals("desktop.ini", StringComparison.OrdinalIgnoreCase)) continue;
            list.Add(new StartupEntry(name, f, source, IsEnabled(hive, "StartupFolder", name), admin) { ApprovedKey = "StartupFolder", ApprovedHive = hive });
        }
    }

    private bool IsEnabled(string hive, string sub, string name)
    {
        var v = _c.Registry.Get($@"{hive}\{Approved}\{sub}", name);
        if (v is null || v.Value.Kind != RegKind.Binary) return true;
        var b = (byte[])v.Value.Data;
        return b.Length == 0 || (b[0] & 1) == 0;   // 02/06 = actif ; 03/07 = désactivé
    }

    public void SetEnabled(StartupEntry e, bool enabled)
    {
        if (e.NeedsAdmin && !_c.Info.IsAdmin) throw new UnauthorizedAccessException("Droits administrateur requis pour cette entrée.");
        var data = new byte[12];
        data[0] = enabled ? (byte)2 : (byte)3;
        if (!enabled) BitConverter.GetBytes(DateTime.UtcNow.ToFileTimeUtc()).CopyTo(data, 4);
        string path = $@"{e.ApprovedHive}\{Approved}\{e.ApprovedKey}";
        _c.Registry.Set(path, e.Name, RegValue.Bin(data));
        if (IsEnabled(e.ApprovedHive, e.ApprovedKey, e.Name) != enabled)
            throw new InvalidOperationException("Le changement n'a pas pu être vérifié.");
    }
}
