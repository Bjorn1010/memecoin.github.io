using System.Windows;
using System.Windows.Threading;
using Blatja.App.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public sealed record FindingRow(string KindText, Style BadgeStyle, string Title, string Evidence);
public sealed record ProcRow(string Name, string Memory, string Cpu);

public partial class DashboardView : PageBase
{
    private readonly DispatcherTimer _procTimer = new() { Interval = TimeSpan.FromSeconds(5) };
    private IReadOnlyList<ProcessUsage> _procs = Array.Empty<ProcessUsage>();
    private bool _sampling;

    public DashboardView()
    {
        InitializeComponent();
        Welcome.Text = $"Bonjour {Environment.UserName}";
        CardCpu.Label = "PROCESSEUR"; CardCpu.Icon = (System.Windows.Media.Geometry)FindResource("IconCpu");
        CardGpu.Label = "CARTE GRAPHIQUE"; CardGpu.Icon = (System.Windows.Media.Geometry)FindResource("IconGpu");
        CardRam.Label = "MÉMOIRE"; CardRam.Icon = (System.Windows.Media.Geometry)FindResource("IconRam");
        CardTemp.Label = "TEMPÉRATURES"; CardTemp.Icon = (System.Windows.Media.Geometry)FindResource("IconThermo");
        CardDisk.Label = "STOCKAGE"; CardDisk.Icon = (System.Windows.Media.Geometry)FindResource("IconStorage");
        CardNet.Label = "RÉSEAU"; CardNet.Icon = (System.Windows.Media.Geometry)FindResource("IconNetwork");
        Chart.Face = (System.Windows.Media.Typeface?)null ?? new System.Windows.Media.Typeface((System.Windows.Media.FontFamily)FindResource("Font.Body"), FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);
        Chart.FaceMono = new System.Windows.Media.Typeface((System.Windows.Media.FontFamily)FindResource("Font.Mono"), FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);

        BtnScan.Click += (_, _) => MainWindow.Current.Navigate("auto");
        BtnAllFindings.Click += (_, _) => MainWindow.Current.Navigate("auto");
        foreach (var r in new[] { SerCpu, SerGpu, SerRam, SerNet, Per1, Per5, Per15 }) r.Checked += (_, _) => UpdateChart();
        _procTimer.Tick += async (_, _) => await SampleProcessesAsync();
        OpStore.Changed += () => { if (IsVisible) UpdateFindings(); };
    }

    public override void OnShow()
    {
        OnMetrics();
        Anim.Reveal(Cards.Children.Cast<UIElement>().Prepend((UIElement)DashRoot.Children[0]).Concat(DashRoot.Children.Cast<UIElement>().Skip(2)), 55);
        _procTimer.Start();
        _ = SampleProcessesAsync();
        RefreshRecent();
    }

    public override void OnHide() => _procTimer.Stop();

    private TimeSpan Window => Per15.IsChecked == true ? TimeSpan.FromMinutes(15) : Per5.IsChecked == true ? TimeSpan.FromMinutes(5) : TimeSpan.FromMinutes(1);

    public override void OnMetrics()
    {
        var m = Svc.Metrics;
        if (m.Cpu.Last is { } cpu) CardCpu.SetNumber(cpu, " %", m.CpuName, cpu); else CardCpu.SetUnavailable("La mesure du processeur n'est pas encore disponible.");
        if (m.Ram.Last is { } ram) CardRam.SetNumber(ram, " %", $"{m.RamUsedGb:0.0} Go utilisés sur {m.RamTotalGb:0.#} Go · {m.RamTotalGb - m.RamUsedGb:0.0} Go disponibles", ram);
        else CardRam.SetUnavailable("Mesure de la mémoire indisponible.");

        if (m.GpuNow is { } g)
        {
            CardGpu.SetNumber(g.Usage, " %", $"{m.GpuName ?? "GPU"} · {g.MemUsedMb / 1024:0.0} / {g.MemTotalMb / 1024:0.#} Go de VRAM", g.Usage);
            if (!double.IsNaN(g.Temp)) CardTemp.SetNumber(g.Temp, " °C", "GPU · CPU : indisponible (Windows ne l'expose pas sans pilote tiers)", Math.Min(100, g.Temp));
            else CardTemp.SetUnavailable("Le pilote ne transmet pas la température.");
        }
        else
        {
            CardGpu.SetUnavailable(Svc.Gpu.IsAvailable ? "Mesure GPU en attente." : "Utilisation GPU disponible uniquement avec une carte NVIDIA (nvidia-smi).");
            CardTemp.SetUnavailable("Aucune sonde de température accessible : GPU non NVIDIA et CPU non exposé par Windows.");
        }

        if (m.DiskTotalGb is { } t && m.DiskUsedGb is { } u && t > 0)
            CardDisk.SetNumber(t - u, " Go libres", $"{u:0} Go utilisés sur {t:0} Go", u / t * 100);
        else CardDisk.SetUnavailable("Taille du disque système illisible.");

        if (!m.NetworkUp) CardNet.SetUnavailable("Aucune connexion réseau active détectée.");
        else
        {
            string speed = m.NetworkLinkMbps is { } l ? $"liaison {l:0} Mb/s" : "débit de liaison inconnu";
            if (m.NetDown.Last is { } d) CardNet.SetNumber(d, " Mb/s", $"{m.NetworkName} · {speed}", null, 1); else CardNet.SetValue("Connecté", $"{m.NetworkName} · {speed}");
        }

        UpdateChart();
        UpdateFindings();
    }

    private void UpdateChart()
    {
        if (Chart is null) return;
        var m = Svc.Metrics; var now = DateTime.Now;
        (TimeSeries series, string unit, double max, string title, string empty, string hint, int dec) = true switch
        {
            _ when SerGpu.IsChecked == true => (m.Gpu, "%", 100, "Utilisation GPU", "Indisponible", "Disponible avec une carte NVIDIA (nvidia-smi).", 0),
            _ when SerRam.IsChecked == true => (m.Ram, "%", 100, "Mémoire utilisée", "Indisponible", "", 0),
            _ when SerNet.IsChecked == true => (m.NetDown, "Mb/s", 0, "Débit réseau reçu", "Indisponible", "Aucune connexion active détectée.", 1),
            _ => (m.Cpu, "%", 100, "Utilisation processeur", "Indisponible", "", 0),
        };
        Chart.Unit = unit; Chart.FixedMax = max; Chart.EmptyText = empty; Chart.EmptyHint = hint; Chart.Decimals = dec;
        Chart.SetData(series.Window(now, Window), now, Window);
        ChartSub.Text = $"{title} · {(Window.TotalMinutes >= 1 ? Window.TotalMinutes + " min" : "")} · une mesure toutes les {Svc.Settings.RefreshSeconds} s";
    }

    private async Task SampleProcessesAsync()
    {
        if (_sampling) return;
        _sampling = true;
        try
        {
            _procs = await Task.Run(Svc.Processes.Sample);
            TopProcs.ItemsSource = _procs.Take(6).Select(p => new ProcRow(p.Name, p.MemoryMb >= 1024 ? $"{p.MemoryMb / 1024:0.0} Go" : $"{p.MemoryMb:0} Mo", p.CpuPercent is { } c ? $"{c:0.#} %" : "—")).ToList();
            ProcsEmpty.Visibility = _procs.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            ProcsEmpty.Text = "Aucun processus lisible.";
            UpdateFindings();
        }
        catch (Exception ex) { Log.Write("Processus : " + ex.Message); }
        finally { _sampling = false; }
    }

    private void UpdateFindings()
    {
        var m = Svc.Metrics;
        var input = new DiagnosticInput(m.DiskUsedGb, m.DiskTotalGb, m.Ram.Last, m.RamTotalGb, _procs, null, m.GpuNow is { } g && !double.IsNaN(g.Temp) ? g.Temp : null,
            OpStore.All.Select(v => new OpStatus(v.Op, v.State, v.Detail)).ToList(), Svc.IsAdmin);
        var found = DiagnosticRules.Evaluate(input);
        Findings.ItemsSource = found.Take(5).Select(f => new FindingRow(
            f.Kind switch { FindingKind.Problem => "Problème", FindingKind.Improvement => "Amélioration", _ => "Info" },
            (Style)FindResource(f.Kind switch { FindingKind.Problem => "Badge.Danger", FindingKind.Improvement => "Badge.Warning", _ => "Badge" }),
            f.Title, f.Evidence)).ToList();

        bool dataReady = m.Cpu.Last is not null && !OpStore.Scanning && OpStore.LastScan is not null;
        FindingsEmpty.Visibility = found.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        FindingsEmpty.Text = !dataReady ? "Analyse en cours…" : "Aucun problème détecté par les mesures actuelles.";
        ActionSpin.Visibility = OpStore.Scanning ? Visibility.Visible : Visibility.Collapsed;
    }

    private void RefreshRecent()
    {
        var recent = Svc.Journal.Recent(5);
        Recent.ItemsSource = recent.Select(e => new { e.OpName, e.Time, e.Message, Outcome = OutcomeText(e.Outcome) }).ToList();
        RecentEmpty.Visibility = recent.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    public static string OutcomeText(JournalOutcome o) => o switch
    {
        JournalOutcome.Succeeded => "Réussie", JournalOutcome.Failed => "Échec", JournalOutcome.VerificationFailed => "Non vérifiée",
        JournalOutcome.Refused => "Refusée", JournalOutcome.Cancelled => "Annulée", _ => "Ignorée",
    };
}
