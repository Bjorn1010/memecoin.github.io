using System.Windows;
using System.Windows.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public partial class StartupPanel : PageBase
{
    public StartupPanel()
    {
        InitializeComponent();
        BtnReload.Click += (_, _) => Load();
    }

    public override void OnShow() => Load();

    private void Load()
    {
        try
        {
            var list = Svc.Startup.List();
            Rows.ItemsSource = list;
            Empty.Visibility = list.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            int on = list.Count(e => e.Enabled);
            Sub.Text = $"{on} actif(s) sur {list.Count} détecté(s) · clés Run et dossiers Démarrage";
        }
        catch (Exception ex) { Log.Write("Démarrage : " + ex.Message); Sub.Text = "Lecture impossible : " + ex.Message; }
    }

    private void Toggle_Click(object sender, RoutedEventArgs e)
    {
        var box = (CheckBox)sender;
        if (box.Tag is not StartupEntry entry) return;
        bool want = box.IsChecked == true;
        try
        {
            Svc.Startup.SetEnabled(entry, want);
            Svc.Journal.Append(new JournalEntry(DateTime.Now, "startup:" + entry.Name, $"Démarrage : {entry.Name}", want ? "Revert" : "Apply", JournalOutcome.Succeeded,
                want ? "Réactivé au démarrage" : "Désactivé au démarrage (entrée conservée)"));
            MainWindow.Current.ShowToast(want ? $"« {entry.Name} » se lancera au démarrage." : $"« {entry.Name} » ne se lancera plus au démarrage.", Kind.Success);
        }
        catch (Exception ex)
        {
            box.IsChecked = !want;   // l'état réel n'a pas changé : l'interface le reflète
            Log.Write($"Démarrage {entry.Name} : {ex.Message}");
            MainWindow.Current.ShowToast(ex is UnauthorizedAccessException ? "Droits administrateur requis pour cette entrée." : "Changement impossible : " + ex.Message, Kind.Warning);
        }
        Load();
    }
}
