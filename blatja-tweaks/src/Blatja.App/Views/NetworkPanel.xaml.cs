using System.Windows;
using Blatja.App.Services;
using Blatja.App.Shell;

namespace Blatja.App.Views;

public partial class NetworkPanel : PageBase
{
    private const int Count = 10;
    private bool _running;

    public NetworkPanel()
    {
        InitializeComponent();
        Method.Text = $"{Count} paquets ICMP vers un serveur public, délai maximal 1,5 s. Une mesure isolée ne permet pas de conclure : refais-la à différents moments.";
        BtnPing.Click += async (_, _) => await MeasureAsync();
    }

    private async Task MeasureAsync()
    {
        if (_running) return;
        _running = true; BtnPing.IsEnabled = false; Spin.Visibility = Visibility.Visible;
        string host = T2.IsChecked == true ? NetworkProbe.Targets[1] : NetworkProbe.Targets[0];
        Verdict.Text = $"Mesure vers {host}…";
        try
        {
            var progress = new Progress<int>(n => Verdict.Text = $"Mesure vers {host} : {n} / {Count}");
            var s = await NetworkProbe.PingAsync(host, Count, progress);
            if (s.Received == 0)
            {
                Avg.Text = Min.Text = Max.Text = Jit.Text = "—"; Loss.Text = "100 %";
                Verdict.Text = "Aucune réponse : le réseau est indisponible, ou le serveur de test est bloqué par ton pare-feu ou ton routeur.";
            }
            else
            {
                Avg.Text = $"{s.AvgMs:0} ms"; Min.Text = $"{s.MinMs:0} ms"; Max.Text = $"{s.MaxMs:0} ms"; Jit.Text = $"{s.JitterMs:0.#} ms"; Loss.Text = $"{s.LossPercent:0} %";
                Verdict.Text = $"{s.Received} réponse(s) sur {s.Sent} vers {host} à {DateTime.Now:HH:mm:ss}. La gigue est l'écart moyen entre deux mesures consécutives.";
            }
        }
        catch (Exception ex) { Log.Write("Ping : " + ex.Message); Verdict.Text = "Mesure impossible : " + ex.Message; }
        finally { _running = false; BtnPing.IsEnabled = true; Spin.Visibility = Visibility.Collapsed; }
    }
}
