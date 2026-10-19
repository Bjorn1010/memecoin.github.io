using System.Diagnostics;
using System.Windows;
using System.Windows.Threading;
using Blatja.App.Services;
using Blatja.App.Shell;

namespace Blatja.App.Views;

public partial class ProcessPanel : PageBase
{
    private readonly DispatcherTimer _timer = new() { Interval = TimeSpan.FromSeconds(5) };
    private bool _busy;

    public ProcessPanel()
    {
        InitializeComponent();
        BtnTaskMgr.Click += (_, _) => { try { Process.Start(new ProcessStartInfo("taskmgr.exe") { UseShellExecute = true }); } catch { } };
        _timer.Tick += async (_, _) => await SampleAsync();
    }

    public override void OnShow() { _timer.Start(); _ = SampleAsync(); }
    public override void OnHide() => _timer.Stop();

    private async Task SampleAsync()
    {
        if (_busy) return;
        _busy = true;
        try
        {
            var list = await Task.Run(Svc.Processes.Sample);
            Rows.ItemsSource = list.Take(12).Select(p => new ProcRow(p.Name, p.MemoryMb >= 1024 ? $"{p.MemoryMb / 1024:0.0} Go" : $"{p.MemoryMb:0} Mo", p.CpuPercent is { } c ? $"{c:0.#} %" : "—")).ToList();
            Empty.Visibility = list.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            Empty.Text = "Aucun processus lisible.";
        }
        catch (Exception ex) { Log.Write("Processus : " + ex.Message); }
        finally { _busy = false; }
    }
}
