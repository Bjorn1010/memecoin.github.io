namespace Blatja.Core;

public enum FindingKind { Problem, Improvement, Info }

public sealed record Finding(FindingKind Kind, string Title, string Detail, string Evidence, IReadOnlyList<string> OpIds);

public sealed record ProcessUsage(string Name, double MemoryMb, double? CpuPercent);

public sealed record DiagnosticInput(
    double? DiskUsedGb, double? DiskTotalGb, double? RamPercent, double? RamTotalGb,
    IReadOnlyList<ProcessUsage> TopProcesses, int? StartupEnabled, double? GpuTemp,
    IReadOnlyList<OpStatus> Ops, bool IsAdmin);

/// <summary>
/// Règles de diagnostic. Principe : un constat n'est émis que si une mesure le démontre ;
/// une donnée absente ne produit aucun constat (jamais de problème supposé).
/// </summary>
public static class DiagnosticRules
{
    public static IReadOnlyList<Finding> Evaluate(DiagnosticInput d)
    {
        var f = new List<Finding>();

        if (d.DiskUsedGb is { } used && d.DiskTotalGb is { } total && total > 0)
        {
            double free = (total - used) / total * 100;
            string ev = $"{total - used:0} Go libres sur {total:0} Go ({free:0} %).";
            if (free < 10) f.Add(new(FindingKind.Problem, "Espace disque presque saturé", "Windows a besoin d'espace libre pour la mémoire virtuelle, les mises à jour et les caches de jeux.", ev, Array.Empty<string>()));
            else if (free < 20) f.Add(new(FindingKind.Improvement, "Espace disque limité", "Libérer de l'espace évite les ralentissements lorsque le disque se remplit.", ev, Array.Empty<string>()));
        }

        if (d.RamPercent is { } ram)
        {
            string ev = $"{ram:0} % de la mémoire utilisée.";
            if (ram >= 90) f.Add(new(FindingKind.Problem, "Mémoire vive presque saturée", "Windows utilise le disque comme mémoire de secours, ce qui ralentit nettement le PC.", ev, Array.Empty<string>()));
            else if (ram >= 80) f.Add(new(FindingKind.Improvement, "Mémoire vive très sollicitée", "Fermer des applications ou en réduire le fonctionnement en arrière-plan libérerait de la marge.", ev, Array.Empty<string>()));
        }

        foreach (var p in d.TopProcesses.Where(p => p.MemoryMb >= 2048).Take(3))
            f.Add(new(FindingKind.Info, $"{p.Name} utilise beaucoup de mémoire", "Si tu ne t'en sers pas, le fermer libère de la mémoire.", $"{p.MemoryMb / 1024:0.0} Go de mémoire de travail.", Array.Empty<string>()));

        if (d.StartupEnabled is { } n && n >= 12)
            f.Add(new(FindingKind.Improvement, "Beaucoup de programmes au démarrage", "Chaque programme lancé au démarrage ralentit l'ouverture de session.", $"{n} programmes actifs au démarrage.", Array.Empty<string>()));

        if (d.GpuTemp is { } t)
        {
            string ev = $"{t:0} °C mesurés sur la carte graphique.";
            if (t >= 85) f.Add(new(FindingKind.Problem, "Carte graphique très chaude", "À cette température, la carte réduit sa fréquence pour se protéger. Vérifie la ventilation et la poussière.", ev, Array.Empty<string>()));
            else if (t >= 80) f.Add(new(FindingKind.Improvement, "Carte graphique chaude", "Une courbe de ventilation plus agressive ou un meilleur flux d'air peut éviter la baisse de fréquence.", ev, Array.Empty<string>()));
        }

        var pending = d.Ops.Where(o => o.State == OpState.Disabled && o.Op.Recommended).ToList();
        foreach (var o in pending.Where(o => o.Op.Impact >= Impact.Medium))
            f.Add(new(FindingKind.Improvement, o.Op.Name, o.Op.Description, "Non appliquée actuellement sur ce système.", new[] { o.Op.Id }));
        var low = pending.Where(o => o.Op.Impact < Impact.Medium).ToList();
        if (low.Count > 0)
            f.Add(new(FindingKind.Improvement, $"{low.Count} autre(s) optimisation(s) recommandée(s)", "Réglages à faible impact, tous réversibles : " + string.Join(", ", low.Select(o => o.Op.Name)) + ".",
                "Non appliquées actuellement sur ce système.", low.Select(o => o.Op.Id).ToList()));

        foreach (var o in d.Ops.Where(o => o.State == OpState.Error))
            f.Add(new(FindingKind.Info, $"État de « {o.Op.Name} » illisible", "L'état n'a pas pu être détecté ; cette optimisation ne sera pas proposée.", o.Detail ?? "Erreur de détection.", Array.Empty<string>()));

        if (!d.IsAdmin)
            f.Add(new(FindingKind.Info, "Mode lecture seule", "Blatja n'a pas les droits administrateur : l'analyse fonctionne, mais aucune modification ne peut être appliquée.", "Relance l'application en administrateur pour modifier le système.", Array.Empty<string>()));

        return f.OrderBy(x => x.Kind).ToList();
    }
}
