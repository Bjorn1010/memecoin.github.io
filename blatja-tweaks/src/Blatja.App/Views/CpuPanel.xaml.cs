using Blatja.App.Services;
using Blatja.App.Shell;

namespace Blatja.App.Views;

public partial class CpuPanel : PageBase
{
    public CpuPanel() { InitializeComponent(); CpuName.Text = Svc.Metrics.CpuName; Cores.Text = Environment.ProcessorCount.ToString(); }
    public override void OnShow() => OnMetrics();
    public override void OnMetrics() => Load.Text = Svc.Metrics.Cpu.Last is { } c ? $"{c:0} %" : "Indisponible";
}
