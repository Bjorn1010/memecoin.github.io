namespace Blatja.Core;

/// <param name="Default">Valeur rétablie si aucune capture n'existe ; null = supprimer la valeur.</param>
public sealed record RegTarget(string Path, string Name, RegValue Value, RegValue? Default = null);

/// <summary>Optimisation décrite par un ensemble de valeurs de registre.</summary>
public sealed class RegistryOperation : Operation
{
    private readonly Func<SystemContext, IReadOnlyList<RegTarget>> _targets;
    private readonly Func<SystemContext, Applicability>? _applicable;

    /// <summary>La valeur absente équivaut à l'optimisation (valeur par défaut de Windows déjà optimale).</summary>
    public bool AbsentMeansEnabled { get; init; }
    /// <summary>Supprime la clé parente si elle est vide après restauration.</summary>
    public bool CleanupEmptyKeys { get; init; }

    public override bool EnabledIsDefault => AbsentMeansEnabled;

    public RegistryOperation(IReadOnlyList<RegTarget> targets, Func<SystemContext, Applicability>? applicable = null)
        : this(_ => targets, applicable) { }

    public RegistryOperation(Func<SystemContext, IReadOnlyList<RegTarget>> targets, Func<SystemContext, Applicability>? applicable = null)
    {
        _targets = targets;
        _applicable = applicable;
    }

    public override Applicability CheckApplicable(SystemContext c)
    {
        var baseResult = base.CheckApplicable(c);
        if (!baseResult.Ok) return baseResult;
        if (_applicable is not null) { var r = _applicable(c); if (!r.Ok) return r; }
        return _targets(c).Count == 0 ? Applicability.No("Aucune cible détectée sur ce système.") : Applicability.Yes;
    }

    public override IEnumerable<string> Targets(SystemContext c) => _targets(c).Select(t => $"reg:{t.Path}|{t.Name}");

    public override OpState Detect(SystemContext c)
    {
        var ts = _targets(c);
        if (ts.Count == 0) return OpState.NotApplicable;
        bool all = true, none = true;
        foreach (var t in ts)
        {
            var cur = c.Registry.Get(t.Path, t.Name);
            if (cur is null) { all = false; continue; }
            none = false;
            if (!cur.Value.SameAs(t.Value)) all = false;
        }
        if (all) return OpState.Enabled;
        if (AbsentMeansEnabled && none) return OpState.Enabled;
        return OpState.Disabled;
    }

    public override void Capture(SystemContext c, BackupRecord b)
    {
        foreach (var t in _targets(c))
            b.Entries.Add(BackupEntry.From(t.Path, t.Name, c.Registry.Get(t.Path, t.Name)));
    }

    public override void Apply(SystemContext c)
    {
        foreach (var t in _targets(c)) c.Registry.Set(t.Path, t.Name, t.Value);
    }

    public override void Revert(SystemContext c, BackupRecord? backup)
    {
        if (backup is { Entries.Count: > 0 })
        {
            foreach (var e in backup.Entries)
            {
                var orig = e.ToValue();
                if (orig is { } v) c.Registry.Set(e.Path, e.Name, v);
                else c.Registry.DeleteValue(e.Path, e.Name);
                Cleanup(c, e.Path);
            }
            return;
        }
        foreach (var t in _targets(c))
        {
            if (t.Default is { } d) c.Registry.Set(t.Path, t.Name, d);
            else c.Registry.DeleteValue(t.Path, t.Name);
            Cleanup(c, t.Path);
        }
    }

    private void Cleanup(SystemContext c, string path)
    {
        if (!CleanupEmptyKeys || !c.Registry.KeyExists(path)) return;
        if (c.Registry.ValueNames(path).Count == 0 && c.Registry.SubKeys(path).Count == 0) c.Registry.DeleteKey(path);
    }
}
