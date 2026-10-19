namespace Blatja.Core;

/// <summary>Désactivation de services Windows non essentiels. Le type de démarrage d'origine est capturé et restauré.</summary>
public sealed class ServiceOperation : Operation
{
    private const string Root = @"HKLM\SYSTEM\CurrentControlSet\Services";
    private readonly string[] _services;
    private readonly string _defaultStart;   // utilisé sans capture : auto | delayed-auto | demand

    public ServiceOperation(string defaultStart, params string[] services)
    {
        _services = services;
        _defaultStart = defaultStart;
    }

    private IEnumerable<string> Installed(SystemContext c) => _services.Where(s => c.Registry.Get($@"{Root}\{s}", "Start") is not null);

    public override Applicability CheckApplicable(SystemContext c)
    {
        var b = base.CheckApplicable(c);
        if (!b.Ok) return b;
        return Installed(c).Any() ? Applicability.Yes : Applicability.No("Ce service n'est pas présent sur cette installation de Windows.");
    }

    public override IEnumerable<string> Targets(SystemContext c) => _services.Select(s => $"svc:{s}");

    public override OpState Detect(SystemContext c)
    {
        var present = Installed(c).ToList();
        if (present.Count == 0) return OpState.NotApplicable;
        foreach (var s in present)
        {
            var v = c.Registry.Get($@"{Root}\{s}", "Start");
            if (v is null || Convert.ToInt64(v.Value.Data) != 4) return OpState.Disabled;
        }
        return OpState.Enabled;
    }

    public override void Capture(SystemContext c, BackupRecord b)
    {
        foreach (var s in Installed(c))
        {
            long start = Convert.ToInt64(c.Registry.Get($@"{Root}\{s}", "Start")!.Value.Data);
            long delayed = c.Registry.Get($@"{Root}\{s}", "DelayedAutostart") is { } d ? Convert.ToInt64(d.Data) : 0;
            b.Extra[$"svc:{s}"] = $"{start};{delayed}";
        }
    }

    public override void Apply(SystemContext c)
    {
        foreach (var s in Installed(c))
        {
            var r = c.Runner.Run("sc", $"config {s} start= disabled");
            if (!r.Ok && r.ExitCode != 1060) throw new InvalidOperationException($"sc config {s} : {FirstLine(r.Output)}");
            c.Runner.Run("sc", $"stop {s}");   // peut échouer si déjà arrêté : sans importance
        }
    }

    public override void Revert(SystemContext c, BackupRecord? backup)
    {
        foreach (var s in Installed(c))
        {
            string mode = _defaultStart;
            if (backup is not null && backup.Extra.TryGetValue($"svc:{s}", out var raw))
            {
                var parts = raw.Split(';');
                long start = long.Parse(parts[0]);
                bool delayed = parts.Length > 1 && parts[1] == "1";
                mode = start switch { 2 when delayed => "delayed-auto", 2 => "auto", 3 => "demand", 4 => "disabled", 0 => "boot", _ => "system" };
            }
            var r = c.Runner.Run("sc", $"config {s} start= {mode}");
            if (!r.Ok && r.ExitCode != 1060) throw new InvalidOperationException($"sc config {s} : {FirstLine(r.Output)}");
        }
    }

    private static string FirstLine(string s) => s.Split('\n').FirstOrDefault(l => l.Trim().Length > 0)?.Trim() ?? "erreur inconnue";
}
