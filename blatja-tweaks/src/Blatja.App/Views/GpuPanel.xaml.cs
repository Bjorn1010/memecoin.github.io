using System.Diagnostics;
using System.Windows;
using Blatja.App.Services;
using Blatja.App.Shell;

namespace Blatja.App.Views;

public partial class GpuPanel : PageBase
{
    private GpuService.Info? _info;

    public GpuPanel()
    {
        InitializeComponent();
        BtnBoost.Click += async (_, _) => await ChangeAsync(boost: true);
        BtnReset.Click += async (_, _) => await ChangeAsync(boost: false);
        BtnDrivers.Click += (_, _) => Process.Start(new ProcessStartInfo("https://www.nvidia.com/Download/index.aspx") { UseShellExecute = true });
        BoostNote.Text = "Règle la limite de puissance au maximum autorisé par le constructeur et verrouille la fréquence minimale à 90 % du boost. Ce n'est pas un overclock avec tension (pour cela : MSI Afterburner). Le réglage disparaît au redémarrage.";
    }

    public override async void OnShow()
    {
        OnMetrics();
        _info = await Task.Run(Svc.Gpu.Describe);
        Svc.Metrics.GpuName = _info.Name;
        GpuName.Text = _info.Name;
        Driver.Text = _info.Driver is null ? "Pilote : non lisible (la lecture détaillée n'est disponible que pour les cartes NVIDIA)." : $"Pilote {_info.Driver}";
        BtnDrivers.Visibility = _info.Driver is null ? Visibility.Collapsed : Visibility.Visible;
        if (_info.PowerLimit is double pl) { Power.Text = $"{pl:0} W"; PowerSub.Text = _info.PowerMax is double pm ? $"maximum {pm:0} W" : ""; }
        else { Power.Text = "Indisponible"; PowerSub.Text = ""; }
        bool nv = Svc.Gpu.IsNvidia(_info);
        BtnBoost.IsEnabled = BtnReset.IsEnabled = nv;
        if (!nv) BoostNote.Text = "Disponible uniquement pour les cartes NVIDIA avec leur pilote officiel (nvidia-smi). Pour AMD, utilise les réglages de performance d'AMD Adrenalin.";
    }

    public override void OnMetrics()
    {
        var g = Svc.Metrics.GpuNow;
        Use.Text = g is null ? "Indisponible" : $"{g.Usage:0} %";
        Temp.Text = g is null || double.IsNaN(g.Temp) ? "Indisponible" : $"{g.Temp:0} °C";
        Vram.Text = g is null || g.MemTotalMb <= 0 ? "Indisponible" : $"{g.MemUsedMb / 1024:0.0} / {g.MemTotalMb / 1024:0.#} Go";
        if (g is { } && !double.IsNaN(g.Temp) && g.Temp >= 80)
        {
            Advice.Text = $"La carte est à {g.Temp:0} °C : au-delà de 83–85 °C elle réduit sa fréquence. Vérifie la ventilation et la poussière.";
            Advice.Visibility = Visibility.Visible;
        }
        else Advice.Visibility = Visibility.Collapsed;
    }

    private async Task ChangeAsync(bool boost)
    {
        if (_info is null || OperationFlow.IsBusy) return;
        var w = MainWindow.Current;
        int c = await w.ShowDialogAsync(boost ? "Booster la carte graphique ?" : "Rétablir les réglages d'origine ?",
            boost ? "La limite de puissance passera au maximum du constructeur et la fréquence minimale sera verrouillée à 90 % du boost. La consommation et la chaleur augmenteront. Le réglage disparaît au redémarrage du PC."
                  : "La limite de puissance et les fréquences reviendront à leurs valeurs par défaut.",
            null, (boost ? "Booster" : "Rétablir", "primary"), ("Annuler", "secondary"));
        if (c != 0) return;
        if (!Svc.IsAdmin) { w.ShowToast("Les droits administrateur sont nécessaires : relance Blatja en administrateur.", Kind.Warning); return; }
        try
        {
            string r = await Task.Run(() => boost ? Svc.Gpu.Boost(_info) : Svc.Gpu.Reset(_info));
            w.ShowToast(r.Length > 0 ? char.ToUpper(r[0]) + r[1..] : "Terminé", Kind.Success);
            OnShow();
        }
        catch (Exception ex) { Log.Write("GPU : " + ex.Message); w.ShowToast(ex.Message, Kind.Danger); }
    }
}
