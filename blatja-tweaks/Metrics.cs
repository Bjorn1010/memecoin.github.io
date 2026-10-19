using System.Globalization;
using System.Runtime.InteropServices;

namespace BlatjaTweaks;

public sealed record GpuLive(double Usage, double Temp, double Power, double MemUsedMb, double MemTotalMb, int Clock);

/// <summary>Mesures système en direct : CPU, RAM, GPU (NVIDIA), disque. Historique d'une minute.</summary>
internal sealed class Metrics
{
    public const int History = 61;

    public readonly List<double> Cpu = new(), Gpu = new(), Ram = new(), Temp = new();
    public double CpuNow, RamNow, GpuNow, TempNow;
    public double RamUsedGb, RamTotalGb;
    public GpuLive? GpuInfo;
    public bool HasGpu;
    public string CpuName = ReadCpuName();

    private ulong _idle, _kernel, _user;
    private readonly Random _rng = new();
    private double _demoPhase;

    [StructLayout(LayoutKind.Sequential)]
    private struct FILETIME { public uint Low, High; public ulong Value => ((ulong)High << 32) | Low; }

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORYSTATUSEX
    {
        public uint Length, MemoryLoad;
        public ulong TotalPhys, AvailPhys, TotalPageFile, AvailPageFile, TotalVirtual, AvailVirtual, AvailExtendedVirtual;
    }

    [DllImport("kernel32.dll")] private static extern bool GetSystemTimes(out FILETIME idle, out FILETIME kernel, out FILETIME user);
    [DllImport("kernel32.dll")] private static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX s);

    private static string ReadCpuName()
    {
        var n = Reg.Get(@"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString") as string;
        if (string.IsNullOrWhiteSpace(n)) return "Processeur";
        n = System.Text.RegularExpressions.Regex.Replace(n, @"\((R|TM|tm|r)\)|\sCPU\b|\s@.*$|\d+-Core Processor|\s+Processor$", "");
        return string.Join(' ', n.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    public void Sample(GpuLive? gpu, bool demo)
    {
        if (GetSystemTimes(out var i, out var k, out var u))
        {
            ulong dIdle = i.Value - _idle, dKernel = k.Value - _kernel, dUser = u.Value - _user;
            ulong total = dKernel + dUser;
            if (_idle != 0 && total > 0) CpuNow = Math.Clamp((1.0 - (double)dIdle / total) * 100, 0, 100);
            _idle = i.Value; _kernel = k.Value; _user = u.Value;
        }

        var m = new MEMORYSTATUSEX { Length = (uint)Marshal.SizeOf<MEMORYSTATUSEX>() };
        if (GlobalMemoryStatusEx(ref m))
        {
            RamTotalGb = m.TotalPhys / 1073741824.0;
            RamUsedGb = (m.TotalPhys - m.AvailPhys) / 1073741824.0;
            RamNow = m.TotalPhys == 0 ? 0 : (1.0 - (double)m.AvailPhys / m.TotalPhys) * 100;
        }

        if (demo)   // données synthétiques, uniquement pour les captures de développement
        {
            _demoPhase += 0.35;
            CpuNow = 28 + 18 * Math.Sin(_demoPhase) + _rng.NextDouble() * 8;
            RamNow = 52 + 5 * Math.Sin(_demoPhase / 3) + _rng.NextDouble() * 2;
            RamTotalGb = 32; RamUsedGb = RamNow / 100 * 32;
            gpu = new GpuLive(46 + 30 * Math.Sin(_demoPhase * 0.7) + _rng.NextDouble() * 6, 58 + 9 * Math.Sin(_demoPhase * 0.4) + _rng.NextDouble() * 2, 210, 6200, 8192, 1950);
        }

        GpuInfo = gpu;
        HasGpu = gpu is not null;
        GpuNow = gpu?.Usage ?? 0;
        TempNow = gpu?.Temp ?? 0;

        Push(Cpu, CpuNow); Push(Ram, RamNow); Push(Gpu, GpuNow); Push(Temp, TempNow);
    }

    private static void Push(List<double> list, double v)
    {
        list.Add(v);
        if (list.Count > History) list.RemoveAt(0);
    }

    /// <summary>Interroge nvidia-smi (hors thread UI).</summary>
    public static GpuLive? PollNvidia(string? smi)
    {
        if (smi is null) return null;
        try
        {
            var r = Sh.Run(smi, "--query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total,clocks.gr --format=csv,noheader,nounits", 4000);
            var p = r.Output.Split('\n')[0].Split(',');
            if (r.Code != 0 || p.Length < 6) return null;
            double D(string s) => double.TryParse(s.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : 0;
            return new GpuLive(D(p[0]), D(p[1]), D(p[2]), D(p[3]), D(p[4]), (int)D(p[5]));
        }
        catch { return null; }
    }

    public static (double UsedGb, double TotalGb) Disk()
    {
        try
        {
            var d = new DriveInfo(Path.GetPathRoot(Environment.SystemDirectory) ?? "C:\\");
            return ((d.TotalSize - d.TotalFreeSpace) / 1073741824.0, d.TotalSize / 1073741824.0);
        }
        catch { return (0, 0); }
    }
}
