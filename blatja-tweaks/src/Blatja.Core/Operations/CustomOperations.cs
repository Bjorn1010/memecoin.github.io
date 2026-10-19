using System.Text.RegularExpressions;

namespace Blatja.Core;

/// <summary>Plan d'alimentation « Performances ultimes » : copie dédiée, jamais de modification des plans d'origine.</summary>
public sealed class PowerPlanOperation : Operation
{
    public const string UltimateScheme = "e9a42b02-d5df-448d-aa00-03f14749eb61";
    public const string BalancedScheme = "381b4222-f694-41f0-9685-ff5bb260df2e";
    public const string HighPerfScheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c";
    public const string BlatjaScheme = "b1a71a00-0000-4000-8000-000000000001";

    private static readonly Regex Guid = new(@"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", RegexOptions.Compiled);

    public override IEnumerable<string> Targets(SystemContext c) => new[] { "cmd:powercfg" };

    private static string? ActiveScheme(SystemContext c)
    {
        var r = c.Runner.Run("powercfg", "/getactivescheme");
        return r.Ok && Guid.Match(r.Output) is { Success: true } m ? m.Value.ToLowerInvariant() : null;
    }

    public override OpState Detect(SystemContext c)
    {
        string? g = ActiveScheme(c);
        if (g is null) return OpState.Unknown;
        return g is BlatjaScheme or UltimateScheme or HighPerfScheme ? OpState.Enabled : OpState.Disabled;
    }

    public override void Capture(SystemContext c, BackupRecord b)
    {
        b.Extra["scheme"] = ActiveScheme(c) ?? BalancedScheme;
    }

    public override void Apply(SystemContext c)
    {
        var dup = c.Runner.Run("powercfg", $"-duplicatescheme {UltimateScheme} {BlatjaScheme}");
        string target = BlatjaScheme;
        if (dup.Ok)
        {
            // réglages appliqués uniquement à notre copie
            c.Runner.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PROCESSOR PROCTHROTTLEMIN 100");
            c.Runner.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PROCESSOR CPMINCORES 100");
            c.Runner.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PCIEXPRESS ASPM 0");
        }
        else target = HighPerfScheme;   // « Performances ultimes » indisponible sur cette édition : plan Performances élevées existant
        var set = c.Runner.Run("powercfg", $"-setactive {target}");
        if (!set.Ok) throw new InvalidOperationException("powercfg -setactive a échoué : " + set.Output.Trim());
    }

    public override void Revert(SystemContext c, BackupRecord? backup)
    {
        string original = backup is not null && backup.Extra.TryGetValue("scheme", out var s) ? s : BalancedScheme;
        var r = c.Runner.Run("powercfg", $"-setactive {original}");
        if (!r.Ok) throw new InvalidOperationException("Impossible de rétablir le plan d'alimentation : " + r.Output.Trim());
        c.Runner.Run("powercfg", $"-delete {BlatjaScheme}");
    }
}

/// <summary>Désactive l'horodatage du dernier accès aux fichiers NTFS (fsutil).</summary>
public sealed class LastAccessOperation : Operation
{
    private static readonly Regex Value = new(@"=\s*(\d)", RegexOptions.Compiled);

    public override IEnumerable<string> Targets(SystemContext c) => new[] { "cmd:fsutil" };

    private static int? Current(SystemContext c)
    {
        var r = c.Runner.Run("fsutil", "behavior query disablelastaccess");
        return r.Ok && Value.Match(r.Output) is { Success: true } m ? int.Parse(m.Groups[1].Value) : null;
    }

    public override OpState Detect(SystemContext c) => Current(c) switch
    {
        null => OpState.Unknown,
        1 or 3 => OpState.Enabled,   // 1 = désactivé par l'utilisateur, 3 = désactivé par le système
        _ => OpState.Disabled,
    };

    public override void Capture(SystemContext c, BackupRecord b) => b.Extra["value"] = (Current(c) ?? 2).ToString();

    public override void Apply(SystemContext c)
    {
        var r = c.Runner.Run("fsutil", "behavior set disablelastaccess 1");
        if (!r.Ok) throw new InvalidOperationException("fsutil a échoué : " + r.Output.Trim());
    }

    public override void Revert(SystemContext c, BackupRecord? backup)
    {
        string v = backup is not null && backup.Extra.TryGetValue("value", out var s) ? s : "2";
        var r = c.Runner.Run("fsutil", $"behavior set disablelastaccess {v}");
        if (!r.Ok) throw new InvalidOperationException("fsutil a échoué : " + r.Output.Trim());
    }
}

/// <summary>
/// Réglages graphiques d'un jeu dans son fichier utilisateur (GameUserSettings.ini).
/// Ne touche à aucun fichier du jeu ni à l'anti-triche ; seules les clés déjà présentes sont modifiées.
/// </summary>
public sealed class GameIniOperation : Operation
{
    private readonly Func<string?> _iniPath;
    private readonly (string Key, string Value)[] _settings;
    private readonly Func<bool> _gameRunning;

    public GameIniOperation(Func<string?> iniPath, Func<bool> gameRunning, params (string Key, string Value)[] settings)
    {
        _iniPath = iniPath; _settings = settings; _gameRunning = gameRunning;
    }

    private string BackupPath(string ini) => ini + ".blatja.bak";

    public override Applicability CheckApplicable(SystemContext c)
    {
        var b = base.CheckApplicable(c);
        if (!b.Ok) return b;
        string? p = _iniPath();
        return p is not null && c.Files.FileExists(p) ? Applicability.Yes : Applicability.No("Fichier de réglages introuvable : lance le jeu une première fois.");
    }

    public override IEnumerable<string> Targets(SystemContext c) => new[] { "file:" + (_iniPath() ?? "GameUserSettings.ini") };

    private static string? Read(string text, string key)
    {
        var m = Regex.Match(text, $@"^{Regex.Escape(key)}=([^\r\n]*)", RegexOptions.Multiline);
        return m.Success ? m.Groups[1].Value : null;
    }

    public override OpState Detect(SystemContext c)
    {
        string? p = _iniPath();
        if (p is null || !c.Files.FileExists(p)) return OpState.NotApplicable;
        string text = c.Files.ReadAllText(p);
        var present = _settings.Where(s => Read(text, s.Key) is not null).ToList();
        if (present.Count == 0) return OpState.NotApplicable;
        return present.All(s => string.Equals(Read(text, s.Key), s.Value, StringComparison.OrdinalIgnoreCase)) ? OpState.Enabled : OpState.Disabled;
    }

    public override void Capture(SystemContext c, BackupRecord b)
    {
        string p = _iniPath()!;
        b.Extra["ini"] = p;
        if (!c.Files.FileExists(BackupPath(p))) c.Files.Copy(p, BackupPath(p), overwrite: false);
    }

    public override void Apply(SystemContext c)
    {
        if (_gameRunning()) throw new InvalidOperationException("Ferme le jeu avant d'appliquer ce réglage : il réécrit son fichier à la fermeture.");
        string p = _iniPath()!;
        string text = c.Files.ReadAllText(p);
        foreach (var (key, value) in _settings)
            text = Regex.Replace(text, $@"^{Regex.Escape(key)}=[^\r\n]*", $"{key}={value}", RegexOptions.Multiline);
        c.Files.WriteAllText(p, text);
    }

    public override void Revert(SystemContext c, BackupRecord? backup)
    {
        if (_gameRunning()) throw new InvalidOperationException("Ferme le jeu avant de restaurer ses réglages.");
        string? p = backup is not null && backup.Extra.TryGetValue("ini", out var s) ? s : _iniPath();
        if (p is null || !c.Files.FileExists(BackupPath(p))) throw new InvalidOperationException("Aucune sauvegarde des réglages d'origine n'a été trouvée.");
        c.Files.Copy(BackupPath(p), p, overwrite: true);
    }
}
