using System.Diagnostics;
using System.Net.NetworkInformation;
using Blatja.Core;

namespace Blatja.App.Services;

/// <summary>Processus les plus consommateurs, regroupés par nom (un navigateur = un seul total). Lecture seule.</summary>
public sealed class ProcessMonitor
{
    private readonly Dictionary<int, (TimeSpan Cpu, DateTime At)> _prev = new();

    public IReadOnlyList<ProcessUsage> Sample()
    {
        var now = DateTime.UtcNow;
        var byName = new Dictionary<string, (double Mem, double Cpu)>(StringComparer.OrdinalIgnoreCase);
        var seen = new HashSet<int>();
        foreach (var p in Process.GetProcesses())
        {
            try
            {
                using (p)
                {
                    if (p.Id <= 4) continue;
                    double mem = p.WorkingSet64 / 1048576.0, cpu = 0;
                    var total = p.TotalProcessorTime;
                    seen.Add(p.Id);
                    if (_prev.TryGetValue(p.Id, out var prev))
                    {
                        double wall = (now - prev.At).TotalSeconds;
                        if (wall > 0.2) cpu = Math.Max(0, (total - prev.Cpu).TotalSeconds / wall / Environment.ProcessorCount * 100);
                    }
                    _prev[p.Id] = (total, now);
                    byName[p.ProcessName] = byName.TryGetValue(p.ProcessName, out var a) ? (a.Mem + mem, a.Cpu + cpu) : (mem, cpu);
                }
            }
            catch { /* processus protégé ou terminé : ignoré */ }
        }
        foreach (var id in _prev.Keys.Where(id => !seen.Contains(id)).ToList()) _prev.Remove(id);
        return byName.Select(kv => new ProcessUsage(kv.Key, kv.Value.Mem, kv.Value.Cpu)).OrderByDescending(p => p.MemoryMb).ToList();
    }
}

public static class NetworkProbe
{
    public static readonly string[] Targets = { "1.1.1.1", "8.8.8.8" };

    /// <summary>Mesure ICMP réelle vers un serveur public. Une perte de paquet est comptée comme telle, jamais ignorée.</summary>
    public static async Task<PingStats> PingAsync(string host, int count, IProgress<int>? progress = null, CancellationToken ct = default)
    {
        var rtts = new List<long?>();
        using var ping = new Ping();
        for (int i = 0; i < count && !ct.IsCancellationRequested; i++)
        {
            try
            {
                var r = await ping.SendPingAsync(host, 1500);
                rtts.Add(r.Status == IPStatus.Success ? r.RoundtripTime : null);
            }
            catch (PingException) { rtts.Add(null); }
            progress?.Report(i + 1);
            if (i < count - 1) await Task.Delay(120, ct).ConfigureAwait(false);
        }
        return PingStats.From(rtts);
    }
}

/// <summary>Instantané avant/après : mesures simples, instantanées, signalées comme telles dans le rapport.</summary>
public static class SnapshotService
{
    public static async Task<SystemSnapshot> TakeAsync(bool includePing)
    {
        var cpuTask = Task.Run(async () =>
        {
            // CPU moyen sur 1 s, mesuré indépendamment de l'historique
            var a = Times(); await Task.Delay(1000); var b = Times();
            ulong total = (b.k - a.k) + (b.u - a.u);
            return total == 0 ? (double?)null : Math.Clamp((1.0 - (double)(b.i - a.i) / total) * 100, 0, 100);
        });
        var pingTask = includePing ? NetworkProbe.PingAsync(NetworkProbe.Targets[0], 4) : Task.FromResult<PingStats?>(null)!;

        double? ramPct = Svc.Metrics.Ram.Last;
        int? procs = null; try { procs = Process.GetProcesses().Length; } catch { }
        int? startup = null; try { startup = Svc.Startup.List().Count(e => e.Enabled); } catch { }
        double? free = Svc.Metrics.DiskTotalGb is { } t && t > 0 && Svc.Metrics.DiskUsedGb is { } u ? (t - u) / t * 100 : null;

        PingStats? ping = null;
        try { ping = await pingTask; } catch { }
        return new SystemSnapshot(DateTime.Now, await cpuTask, ramPct, procs, startup, ping is { Received: > 0 } ? ping : null, free);
    }

    private static (ulong i, ulong k, ulong u) Times()
    {
        GetSystemTimes(out var i, out var k, out var u);
        return (((ulong)i.dwHigh << 32) | i.dwLow, ((ulong)k.dwHigh << 32) | k.dwLow, ((ulong)u.dwHigh << 32) | u.dwLow);
    }

    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    private struct FT { public uint dwLow, dwHigh; }
    [System.Runtime.InteropServices.DllImport("kernel32.dll")] private static extern bool GetSystemTimes(out FT idle, out FT kernel, out FT user);
}
