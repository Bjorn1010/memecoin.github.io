using System.Globalization;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Windows.Threading;
using Blatja.Core;

namespace Blatja.App.Services;

public sealed record GpuLive(double Usage, double Temp, double PowerW, double MemUsedMb, double MemTotalMb, int ClockMhz);

/// <summary>
/// Mesures système réelles avec historique de 15 minutes. Une mesure impossible à obtenir est enregistrée comme absente
/// (jamais remplacée par une valeur inventée). La fréquence est réglable ; le GPU n'est interrogé qu'en arrière-plan.
/// </summary>
public sealed class MetricsService
{
    public static readonly TimeSpan Retention = TimeSpan.FromMinutes(15);

    public TimeSeries Cpu { get; } = new(Retention);
    public TimeSeries Ram { get; } = new(Retention);
    public TimeSeries Gpu { get; } = new(Retention);
    public TimeSeries GpuTemp { get; } = new(Retention);
    public TimeSeries NetDown { get; } = new(Retention);

    public DateTime? LastUpdate { get; private set; }
    public double RamTotalGb { get; private set; }
    public double RamUsedGb { get; private set; }
    public double? DiskUsedGb { get; private set; }
    public double? DiskTotalGb { get; private set; }
    public string NetworkName { get; private set; } = "";
    public bool NetworkUp { get; private set; }
    public double? NetworkLinkMbps { get; private set; }
    public GpuLive? GpuNow { get; private set; }
    public string CpuName { get; } = ReadCpuName();
    public string? GpuName { get; set; }
    public event Action? Updated;

    private readonly GpuService _gpu;
    private readonly DispatcherTimer _timer = new(DispatcherPriority.Background);
    private bool _polling;
    private ulong _idle, _kernel, _user;
    private DateTime _lastDisk = DateTime.MinValue, _lastNicList = DateTime.MinValue, _lastNetSample = DateTime.MinValue;
    private long _lastRx;
    private List<NetworkInterface> _nics = new();

    [StructLayout(LayoutKind.Sequential)] private struct FILETIME { public uint Low, High; public ulong Value => ((ulong)High << 32) | Low; }
    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORYSTATUSEX { public uint Length, MemoryLoad; public ulong TotalPhys, AvailPhys, TotalPageFile, AvailPageFile, TotalVirtual, AvailVirtual, AvailExtendedVirtual; }
    [DllImport("kernel32.dll")] private static extern bool GetSystemTimes(out FILETIME idle, out FILETIME kernel, out FILETIME user);
    [DllImport("kernel32.dll")] private static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX s);

    public MetricsService(GpuService gpu)
    {
        _gpu = gpu;
        _timer.Tick += (_, _) => Tick();
    }

    public void Start()
    {
        _timer.Interval = TimeSpan.FromSeconds(Svc.Settings.RefreshSeconds);
        _timer.Start();
        Tick();
    }

    public void SetInterval(int seconds) => _timer.Interval = TimeSpan.FromSeconds(seconds);

    /// <summary>Met l'échantillonnage en veille (fenêtre réduite) pour ne pas consommer de ressources inutilement.</summary>
    public void Pause(bool paused) { if (paused) _timer.Stop(); else _timer.Start(); }

    private static string ReadCpuName()
    {
        var n = Svc.Ctx?.Registry.Get(@"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")?.Data as string;
        if (string.IsNullOrWhiteSpace(n)) return "Processeur";
        n = System.Text.RegularExpressions.Regex.Replace(n, @"\((R|TM|tm|r)\)|\sCPU\b|\s@.*$|\d+-Core Processor|\s+Processor$", "");
        return string.Join(' ', n.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private void Tick()
    {
        var now = DateTime.Now;

        double? cpu = null;
        if (GetSystemTimes(out var i, out var k, out var u))
        {
            ulong dIdle = i.Value - _idle, dKernel = k.Value - _kernel, dUser = u.Value - _user;
            ulong total = dKernel + dUser;
            if (_idle != 0 && total > 0) cpu = Math.Clamp((1.0 - (double)dIdle / total) * 100, 0, 100);
            _idle = i.Value; _kernel = k.Value; _user = u.Value;
        }
        Cpu.Add(now, cpu);

        double? ram = null;
        var m = new MEMORYSTATUSEX { Length = (uint)Marshal.SizeOf<MEMORYSTATUSEX>() };
        if (GlobalMemoryStatusEx(ref m) && m.TotalPhys > 0)
        {
            RamTotalGb = m.TotalPhys / 1073741824.0;
            RamUsedGb = (m.TotalPhys - m.AvailPhys) / 1073741824.0;
            ram = (1.0 - (double)m.AvailPhys / m.TotalPhys) * 100;
        }
        Ram.Add(now, ram);

        Gpu.Add(now, GpuNow?.Usage);
        GpuTemp.Add(now, GpuNow?.Temp);
        if (_gpu.IsAvailable && !_polling)
        {
            _polling = true;
            _ = Task.Run(_gpu.Poll).ContinueWith(t => { GpuNow = t.IsCompletedSuccessfully ? t.Result : null; _polling = false; });
        }

        SampleNetwork(now);

        if (now - _lastDisk > TimeSpan.FromSeconds(30))
        {
            _lastDisk = now;
            try
            {
                var d = new DriveInfo(Path.GetPathRoot(Environment.SystemDirectory) ?? "C:\\");
                DiskTotalGb = d.TotalSize / 1073741824.0;
                DiskUsedGb = (d.TotalSize - d.TotalFreeSpace) / 1073741824.0;
            }
            catch { DiskTotalGb = DiskUsedGb = null; }
        }

        LastUpdate = now;
        Updated?.Invoke();
    }

    private void SampleNetwork(DateTime now)
    {
        try
        {
            if (now - _lastNicList > TimeSpan.FromSeconds(10))
            {
                _lastNicList = now;
                _nics = NetworkInterface.GetAllNetworkInterfaces()
                    .Where(n => n.OperationalStatus == OperationalStatus.Up && n.NetworkInterfaceType is not (NetworkInterfaceType.Loopback or NetworkInterfaceType.Tunnel)
                                && n.GetIPProperties().GatewayAddresses.Count > 0)
                    .ToList();
                var main = _nics.OrderByDescending(n => n.Speed).FirstOrDefault();
                NetworkUp = main is not null;
                NetworkName = main?.Name ?? "";
                NetworkLinkMbps = main is null || main.Speed <= 0 ? null : main.Speed / 1_000_000.0;
            }
            if (_nics.Count == 0) { NetDown.Add(now, null); return; }
            long rx = _nics.Sum(n => n.GetIPv4Statistics().BytesReceived);
            double? mbps = null;
            if (_lastNetSample != DateTime.MinValue && rx >= _lastRx)
                mbps = (rx - _lastRx) * 8 / 1_000_000.0 / Math.Max(0.1, (now - _lastNetSample).TotalSeconds);
            _lastRx = rx; _lastNetSample = now;
            NetDown.Add(now, mbps);
        }
        catch { NetDown.Add(now, null); }
    }

    public double? LastCpu => Cpu.Last;
}

/// <summary>Données GPU via nvidia-smi (cartes NVIDIA uniquement).</summary>
public sealed class GpuService
{
    public string? SmiPath { get; } = FindSmi();
    public bool IsAvailable => SmiPath is not null;

    private static string? FindSmi() => new[]
    {
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "nvidia-smi.exe"),
        @"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    }.FirstOrDefault(File.Exists);

    public sealed record Info(string Name, string? Driver, double? PowerLimit, double? PowerDefault, double? PowerMax, int? MaxClock);

    private static double? D(string s) => double.TryParse(s.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : null;

    public GpuLive? Poll()
    {
        if (SmiPath is null) return null;
        var r = Svc.Ctx.Runner.Run(SmiPath, "--query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total,clocks.gr --format=csv,noheader,nounits", 4000);
        var p = r.Output.Split('\n')[0].Split(',');
        if (!r.Ok || p.Length < 6) return null;
        if (D(p[0]) is not { } use) return null;
        return new GpuLive(use, D(p[1]) ?? double.NaN, D(p[2]) ?? 0, D(p[3]) ?? 0, D(p[4]) ?? 0, (int)(D(p[5]) ?? 0));
    }

    /// <summary>Nom de la carte graphique : nvidia-smi si disponible, sinon pilote d'affichage Windows.</summary>
    public Info Describe()
    {
        if (SmiPath is not null)
        {
            var r = Svc.Ctx.Runner.Run(SmiPath, "--query-gpu=name,driver_version,power.limit,power.default_limit,power.max_limit,clocks.max.graphics --format=csv,noheader,nounits", 4000);
            var p = r.Output.Split('\n')[0].Split(',');
            if (r.Ok && p.Length >= 6) return new Info(p[0].Trim(), p[1].Trim(), D(p[2]), D(p[3]), D(p[4]), (int?)D(p[5]));
        }
        string name = "Carte graphique non détectée";
        const string cls = @"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}";
        foreach (var sub in Svc.Ctx.Registry.SubKeys(cls).Where(s => s.Length == 4 && char.IsDigit(s[0])))
        {
            if (Svc.Ctx.Registry.Get($@"{cls}\{sub}", "DriverDesc")?.Data is not string d) continue;
            if (d.Contains("Basic", StringComparison.OrdinalIgnoreCase) || d.Contains("Remote", StringComparison.OrdinalIgnoreCase) || d.Contains("Virtual", StringComparison.OrdinalIgnoreCase)) continue;
            if (name.StartsWith("Carte graphique non") || name.Contains("Intel", StringComparison.OrdinalIgnoreCase)) name = d;
        }
        return new Info(name, null, null, null, null, null);
    }

    public bool IsNvidia(Info i) => SmiPath is not null && (i.Name.Contains("NVIDIA", StringComparison.OrdinalIgnoreCase) || i.Name.Contains("GeForce", StringComparison.OrdinalIgnoreCase));

    /// <summary>Limite de puissance au maximum constructeur et fréquence minimale verrouillée à 90 % du boost. Se rétablit au redémarrage.</summary>
    public string Boost(Info i)
    {
        if (SmiPath is null) throw new InvalidOperationException("nvidia-smi est introuvable : installe le pilote NVIDIA officiel.");
        var log = new List<string>();
        if (i.PowerMax is double pm)
        {
            var r = Svc.Ctx.Runner.Run(SmiPath, $"-pl {Math.Floor(pm).ToString(CultureInfo.InvariantCulture)}");
            log.Add(r.Ok ? $"limite de puissance {pm:0} W" : "limite de puissance refusée par la carte");
        }
        if (i.MaxClock is int mc)
        {
            var r = Svc.Ctx.Runner.Run(SmiPath, $"-lgc {(int)(mc * 0.9)},{mc}");
            log.Add(r.Ok ? $"fréquence verrouillée {(int)(mc * 0.9)}–{mc} MHz" : "verrouillage de fréquence non pris en charge");
        }
        Svc.Journal.Append(new JournalEntry(DateTime.Now, "gpuboost", "Boost GPU (nvidia-smi)", "Apply", JournalOutcome.Succeeded, string.Join(", ", log)));
        return string.Join(" · ", log);
    }

    public string Reset(Info i)
    {
        if (SmiPath is null) throw new InvalidOperationException("nvidia-smi est introuvable.");
        Svc.Ctx.Runner.Run(SmiPath, "-rgc");
        if (i.PowerDefault is double pd) Svc.Ctx.Runner.Run(SmiPath, $"-pl {Math.Floor(pd).ToString(CultureInfo.InvariantCulture)}");
        Svc.Journal.Append(new JournalEntry(DateTime.Now, "gpuboost", "Boost GPU (nvidia-smi)", "Revert", JournalOutcome.Succeeded, "Réglages d'origine rétablis"));
        return "Réglages d'origine rétablis";
    }
}
