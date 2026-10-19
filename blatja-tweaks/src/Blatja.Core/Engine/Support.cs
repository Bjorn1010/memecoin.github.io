namespace Blatja.Core;

public sealed record AppSettings
{
    public int RefreshSeconds { get; init; } = 2;

    public static AppSettings Load(string path)
    {
        try { return System.Text.Json.JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(path)) is { } s ? Normalize(s) : new AppSettings(); }
        catch { return new AppSettings(); }
    }

    public void Save(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, System.Text.Json.JsonSerializer.Serialize(this));
    }

    private static AppSettings Normalize(AppSettings s) => s with { RefreshSeconds = s.RefreshSeconds is 1 or 2 or 5 or 10 ? s.RefreshSeconds : 2 };
}

/// <summary>Série temporelle bornée. Une valeur absente est enregistrée comme NaN pour que le graphique montre un trou, pas un zéro inventé.</summary>
public sealed class TimeSeries
{
    private readonly List<(DateTime T, double V)> _points = new();
    private readonly TimeSpan _retention;

    public TimeSeries(TimeSpan retention) { _retention = retention; }

    public int Count => _points.Count;

    public void Add(DateTime t, double? value)
    {
        _points.Add((t, value ?? double.NaN));
        int cut = _points.FindIndex(p => t - p.T <= _retention);
        if (cut > 0) _points.RemoveRange(0, cut);
    }

    /// <summary>Points des dernières <paramref name="window"/>, relativement à <paramref name="now"/>.</summary>
    public IReadOnlyList<(DateTime T, double V)> Window(DateTime now, TimeSpan window) =>
        _points.Where(p => now - p.T <= window).ToList();

    public bool HasData(DateTime now, TimeSpan window) => Window(now, window).Any(p => !double.IsNaN(p.V));
    public double? Last => _points.Count == 0 || double.IsNaN(_points[^1].V) ? null : _points[^1].V;
}

public sealed record PingStats(int Sent, int Received, double? AvgMs, double? MinMs, double? MaxMs, double? JitterMs)
{
    public double LossPercent => Sent == 0 ? 0 : (Sent - Received) * 100.0 / Sent;

    /// <summary>Calcule les statistiques à partir de temps de réponse (null = paquet perdu). Gigue = écart moyen entre mesures consécutives.</summary>
    public static PingStats From(IReadOnlyList<long?> rtts)
    {
        var ok = rtts.Where(r => r.HasValue).Select(r => (double)r!.Value).ToList();
        if (ok.Count == 0) return new PingStats(rtts.Count, 0, null, null, null, null);
        double jitter = ok.Count < 2 ? 0 : Enumerable.Range(1, ok.Count - 1).Average(i => Math.Abs(ok[i] - ok[i - 1]));
        return new PingStats(rtts.Count, ok.Count, ok.Average(), ok.Min(), ok.Max(), jitter);
    }
}

/// <summary>Mesures instantanées prises avant et après une optimisation. Ce ne sont pas des benchmarks : elles varient d'une seconde à l'autre.</summary>
public sealed record SystemSnapshot(
    DateTime Time, double? CpuPercent, double? RamPercent, int? ProcessCount, int? StartupEnabledCount, PingStats? Ping, double? DiskFreePercent);

public sealed record ComparisonRow(string Label, string Before, string After, string Delta, string Note);

public static class SnapshotComparison
{
    public static IReadOnlyList<ComparisonRow> Compare(SystemSnapshot before, SystemSnapshot after)
    {
        var rows = new List<ComparisonRow>();
        void Add(string label, double? b, double? a, string unit, string note, string fmt = "0.#")
        {
            if (b is null || a is null) { rows.Add(new(label, Fmt(b, fmt, unit), Fmt(a, fmt, unit), "Indisponible", "Une des deux mesures n'a pas pu être prise.")); return; }
            double d = a.Value - b.Value;
            rows.Add(new(label, Fmt(b, fmt, unit), Fmt(a, fmt, unit), (d > 0 ? "+" : "") + d.ToString(fmt) + (unit.Length > 0 ? " " + unit : ""), note));
        }
        Add("Utilisation CPU", before.CpuPercent, after.CpuPercent, "%", "Mesure instantanée : dépend de ce qui tourne à cet instant.");
        Add("Mémoire utilisée", before.RamPercent, after.RamPercent, "%", "Mesure instantanée.");
        Add("Processus en cours", before.ProcessCount, after.ProcessCount, "", "Nombre de processus au moment de la mesure.", "0");
        Add("Programmes au démarrage actifs", before.StartupEnabledCount, after.StartupEnabledCount, "", "Effet visible au prochain démarrage.", "0");
        Add("Latence réseau moyenne", before.Ping?.AvgMs, after.Ping?.AvgMs, "ms", "Dépend du réseau et du moment : plusieurs mesures seraient nécessaires pour conclure.");
        Add("Gigue réseau", before.Ping?.JitterMs, after.Ping?.JitterMs, "ms", "Écart moyen entre deux mesures consécutives.");
        Add("Espace disque libre", before.DiskFreePercent, after.DiskFreePercent, "%", "");
        return rows;
    }

    private static string Fmt(double? v, string fmt, string unit) => v is null ? "Indisponible" : v.Value.ToString(fmt) + (unit.Length > 0 ? " " + unit : "");
}
