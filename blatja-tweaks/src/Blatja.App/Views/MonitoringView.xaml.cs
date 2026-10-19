using System.Windows;
using System.Windows.Media;
using Blatja.App.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;

namespace Blatja.App.Views;

public partial class MonitoringView : PageBase
{
    public MonitoringView()
    {
        InitializeComponent();
        var body = new Typeface((FontFamily)FindResource("Font.Body"), FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);
        var mono = new Typeface((FontFamily)FindResource("Font.Mono"), FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);
        foreach (var c in new[] { ChCpu, ChRam, ChGpu, ChTemp, ChNet }) { c.Face = body; c.FaceMono = mono; }
        ChTemp.Unit = "°C"; ChTemp.FixedMax = 100; ChTemp.EmptyHint = "La température n'est lue que sur les cartes NVIDIA. Windows n'expose pas celle du processeur sans pilote tiers.";
        ChGpu.EmptyHint = "Disponible avec une carte NVIDIA (nvidia-smi).";
        ChNet.Unit = "Mb/s"; ChNet.FixedMax = 0; ChNet.Decimals = 1; ChNet.EmptyHint = "Aucune connexion active détectée.";
        foreach (var r in new[] { Per1, Per5, Per15 }) r.Checked += (_, _) => OnMetrics();
    }

    private TimeSpan Window => Per15.IsChecked == true ? TimeSpan.FromMinutes(15) : Per5.IsChecked == true ? TimeSpan.FromMinutes(5) : TimeSpan.FromMinutes(1);

    public override void OnShow() => OnMetrics();

    public override void OnMetrics()
    {
        var m = Svc.Metrics; var now = DateTime.Now; var w = Window;
        Sub.Text = $"Une mesure toutes les {Svc.Settings.RefreshSeconds} s · historique conservé 15 minutes · survole un graphique pour lire une valeur";

        ChCpu.SetData(m.Cpu.Window(now, w), now, w); VCpu.Text = m.Cpu.Last is { } c ? $"{c:0} %" : "Indisponible"; NCpu.Text = m.CpuName;
        ChRam.SetData(m.Ram.Window(now, w), now, w); VRam.Text = m.Ram.Last is { } r ? $"{r:0} %" : "Indisponible"; NRam.Text = $"{m.RamUsedGb:0.0} Go utilisés sur {m.RamTotalGb:0.#} Go";
        ChGpu.SetData(m.Gpu.Window(now, w), now, w); VGpu.Text = m.Gpu.Last is { } g ? $"{g:0} %" : "Indisponible"; NGpu.Text = m.GpuName ?? (Svc.Gpu.IsAvailable ? "GPU NVIDIA" : "GPU non NVIDIA : mesure non disponible");
        ChTemp.SetData(m.GpuTemp.Window(now, w), now, w); VTemp.Text = m.GpuTemp.Last is { } t && !double.IsNaN(t) ? $"{t:0} °C" : "Indisponible"; NTemp.Text = "Carte graphique · température du processeur non exposée par Windows";
        ChNet.SetData(m.NetDown.Window(now, w), now, w); VNet.Text = m.NetDown.Last is { } n ? $"{n:0.0} Mb/s" : "Indisponible"; NNet.Text = m.NetworkUp ? $"{m.NetworkName}" + (m.NetworkLinkMbps is { } l ? $" · liaison {l:0} Mb/s" : "") : "Aucune connexion active";
    }
}
