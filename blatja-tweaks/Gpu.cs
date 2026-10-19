using System.Globalization;
using Microsoft.Win32;

namespace BlatjaTweaks;

public sealed record GpuInfo(
    string Name, string Vendor, string? Driver,
    double? PowerLimit, double? PowerDefault, double? PowerMax,
    int? MaxClock, int? Temp, string? SmiPath);

internal static class Gpu
{
    private const string ClassKey = @"HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}";

    internal static string? FindSmi()
    {
        foreach (var p in new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "nvidia-smi.exe"),
            @"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        })
            if (File.Exists(p)) return p;
        return null;
    }

    private static string VendorOf(string name) =>
        name.Contains("NVIDIA", StringComparison.OrdinalIgnoreCase) || name.Contains("GeForce", StringComparison.OrdinalIgnoreCase) ? "NVIDIA" :
        name.Contains("AMD", StringComparison.OrdinalIgnoreCase) || name.Contains("Radeon", StringComparison.OrdinalIgnoreCase) ? "AMD" :
        name.Contains("Intel", StringComparison.OrdinalIgnoreCase) ? "Intel" : "Inconnu";

    private static double? D(string s) =>
        double.TryParse(s.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : null;

    public static GpuInfo Query()
    {
        string name = "Aucune carte détectée";
        foreach (var sub in Reg.SubKeys(ClassKey).Where(s => s.Length == 4 && char.IsDigit(s[0])))
        {
            var desc = Reg.Get($@"{ClassKey}\{sub}", "DriverDesc") as string;
            if (string.IsNullOrWhiteSpace(desc) || desc.Contains("Basic", StringComparison.OrdinalIgnoreCase) ||
                desc.Contains("Remote", StringComparison.OrdinalIgnoreCase) || desc.Contains("Virtual", StringComparison.OrdinalIgnoreCase)) continue;
            // on préfère la carte dédiée à l'iGPU Intel
            if (name.StartsWith("Aucune") || VendorOf(name) == "Intel") name = desc;
        }

        string vendor = VendorOf(name);
        string? smi = vendor == "NVIDIA" ? FindSmi() : null;
        if (smi is null) return new GpuInfo(name, vendor, null, null, null, null, null, null, null);

        try
        {
            var r = Sh.Run(smi, "--query-gpu=name,driver_version,power.limit,power.default_limit,power.max_limit,clocks.max.graphics,temperature.gpu --format=csv,noheader,nounits");
            var p = r.Output.Split('\n')[0].Split(',');
            if (r.Code == 0 && p.Length >= 7)
                return new GpuInfo(p[0].Trim(), vendor, p[1].Trim(), D(p[2]), D(p[3]), D(p[4]), (int?)D(p[5]), (int?)D(p[6]), smi);
        }
        catch { }
        return new GpuInfo(name, vendor, null, null, null, null, null, null, smi);
    }

    /// <summary>Limite de puissance au maximum + fréquence minimale verrouillée à 90 % du boost max.</summary>
    public static string Boost(GpuInfo g)
    {
        if (g.SmiPath is null) throw new InvalidOperationException("nvidia-smi introuvable : installe le pilote NVIDIA officiel.");
        var log = new List<string>();
        if (g.PowerMax is double pm)
        {
            var r = Sh.Run(g.SmiPath, $"-pl {Math.Floor(pm).ToString(CultureInfo.InvariantCulture)}");
            log.Add(r.Code == 0 ? $"Limite de puissance → {pm:0} W" : "Limite de puissance refusée par la carte : " + FirstLine(r.Output));
        }
        if (g.MaxClock is int mc)
        {
            int lo = (int)(mc * 0.9);
            var r = Sh.Run(g.SmiPath, $"-lgc {lo},{mc}");
            log.Add(r.Code == 0 ? $"Fréquence verrouillée {lo}–{mc} MHz" : "Verrouillage de fréquence non supporté : " + FirstLine(r.Output));
        }
        return string.Join(" · ", log);
    }

    public static string Reset(GpuInfo g)
    {
        if (g.SmiPath is null) throw new InvalidOperationException("nvidia-smi introuvable.");
        Sh.Run(g.SmiPath, "-rgc");
        if (g.PowerDefault is double pd) Sh.Run(g.SmiPath, $"-pl {Math.Floor(pd).ToString(CultureInfo.InvariantCulture)}");
        return "Réglages GPU d'origine rétablis";
    }

    private static string FirstLine(string s) => s.Split('\n')[0].Trim();
}
