using System.Diagnostics;
using System.Reflection;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public partial class SettingsView : PageBase
{
    private bool _init;

    public SettingsView()
    {
        InitializeComponent();
        foreach (var (rb, sec) in new[] { (R1, 1), (R2, 2), (R5, 5), (R10, 10) })
        {
            rb.IsChecked = Svc.Settings.RefreshSeconds == sec;
            int s = sec;
            rb.Checked += (_, _) =>
            {
                if (!_init) return;
                Svc.Settings = Svc.Settings with { RefreshSeconds = s };
                try { Svc.Settings.Save(AppPaths.Settings); } catch (Exception ex) { Log.Write("Paramètres : " + ex.Message); }
                Svc.Metrics.SetInterval(s);
                MainWindow.Current.ShowToast($"Actualisation toutes les {s} s.", Kind.Info);
            };
        }
        _init = true;

        BtnElevate.Click += (_, _) => { if (Elevation.Relaunch()) System.Windows.Application.Current.Shutdown(); else MainWindow.Current.ShowToast("Relance annulée.", Kind.Warning); };
        BtnFolder.Click += (_, _) => OpenFolder(AppPaths.Root);
        BtnLogs.Click += (_, _) => OpenFolder(AppPaths.Logs);
        BtnClear.Click += async (_, _) =>
        {
            int c = await MainWindow.Current.ShowDialogAsync("Effacer l'historique ?", "Le journal des modifications sera supprimé définitivement. Les valeurs d'origine sauvegardées ne sont pas touchées.", null, ("Effacer", "danger"), ("Annuler", "secondary"));
            if (c != 0) return;
            try { File.Delete(AppPaths.Journal); MainWindow.Current.ShowToast("Historique effacé.", Kind.Success); } catch (Exception ex) { MainWindow.Current.ShowToast("Impossible : " + ex.Message, Kind.Danger); }
        };
    }

    public override void OnShow()
    {
        bool admin = Svc.IsAdmin;
        AdminText.Text = admin ? "Blatja s'exécute avec les droits administrateur : il peut appliquer des modifications." : "Blatja s'exécute sans droits administrateur : analyse et monitoring uniquement. Les droits ne sont demandés que pour modifier le système.";
        BtnElevate.Visibility = admin ? System.Windows.Visibility.Collapsed : System.Windows.Visibility.Visible;
        Paths.Text = $"Données   {AppPaths.Root}\nJournal   {AppPaths.Journal}\nSauvegardes   {AppPaths.Backups}\nJournaux techniques   {AppPaths.Logs}";
        string v = Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "2.0.0";
        About.Text = $"Blatja Tweaks {v}\n{Svc.Ctx.Info.Description}\n{Svc.Catalog.Count} optimisations documentées, détection de l'état réel, sauvegarde et vérification de chaque modification.";
    }

    private static void OpenFolder(string path)
    {
        try { Directory.CreateDirectory(path); Process.Start(new ProcessStartInfo(path) { UseShellExecute = true }); } catch { }
    }
}
