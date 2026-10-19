using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public partial class RestoreView : PageBase
{
    private static readonly string[] Colors = { "#FF5C50", "#E8A33D", "#3DBE7A", "#4DA3FF", "#B06BFF" };
    private string _color = Colors[0];

    public RestoreView()
    {
        InitializeComponent();
        foreach (var col in Colors)
        {
            var rb = new RadioButton { Style = (Style)FindResource("Swatch"), Tag = col, GroupName = "Sw", IsChecked = col == _color };
            System.Windows.Automation.AutomationProperties.SetName(rb, "Couleur " + col);
            rb.Checked += (_, _) => _color = col;
            Swatches.Children.Add(rb);
        }
        BtnCreate.Click += async (_, _) => await CreateAsync();
        BtnOpenRestore.Click += (_, _) => Open();
        BtnRevertAll.Click += async (_, _) => await RevertAllAsync();
    }

    public override void OnShow() => Reload();

    private void Reload()
    {
        var h = RestorePoints.History().OrderByDescending(e => e.When).ToList();
        Catalog.ItemsSource = h;
        Empty.Visibility = h.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    private async Task CreateAsync()
    {
        if (!Svc.IsAdmin) { Status.Text = "Les droits administrateur sont nécessaires pour créer un point de restauration."; MainWindow.Current.ShowToast("Relance Blatja en administrateur pour créer un point de restauration.", Kind.Warning); return; }
        string name = string.IsNullOrWhiteSpace(RpName.Text) ? "Point Blatja" : RpName.Text.Trim();
        BtnCreate.IsEnabled = false; Spin.Visibility = Visibility.Visible; Status.Text = "Création en cours (jusqu'à une minute)…";
        var (ok, msg) = await Task.Run(() => RestorePoints.Create(name, RpDesc.Text.Trim(), _color));
        BtnCreate.IsEnabled = true; Spin.Visibility = Visibility.Collapsed;
        Status.Text = ok ? "" : "Échec : " + msg;
        MainWindow.Current.ShowToast(ok ? $"Point « {name} » créé." : "Création impossible : " + msg, ok ? Kind.Success : Kind.Danger);
        if (ok) Reload();
    }

    private void Restore_Click(object sender, RoutedEventArgs e) => Open();

    private async void Open()
    {
        int c = await MainWindow.Current.ShowDialogAsync("Restaurer le système", "L'assistant de restauration Windows va s'ouvrir. Tu y choisiras le point à restaurer ; le PC redémarrera pour appliquer la restauration. Enregistre ton travail avant.",
            null, ("Ouvrir l'assistant", "primary"), ("Annuler", "secondary"));
        if (c != 0) return;
        try { Process.Start(new ProcessStartInfo("rstrui.exe") { UseShellExecute = true }); }
        catch (Exception ex) { MainWindow.Current.ShowToast("Impossible d'ouvrir l'assistant : " + ex.Message, Kind.Danger); }
    }

    private async Task RevertAllAsync()
    {
        var active = OpStore.All.Where(v => v.CanRevert).Select(v => (v.Op, OpAction.Revert)).ToList();
        if (active.Count == 0) { MainWindow.Current.ShowToast("Aucune optimisation Blatja n'est appliquée.", Kind.Info); return; }
        await OperationFlow.RunAsync(active, $"Annuler {active.Count} optimisation(s)");
    }
}
