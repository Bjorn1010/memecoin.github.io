using System.Windows;
using System.Windows.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public partial class UtilitiesView : PageBase
{
    private sealed record Row(Utility U) { public string Name => U.Name; public string Description => U.Description; public bool NeedsConfirm => U.Warning is not null; public bool RequiresAdmin => U.RequiresAdmin; }

    public UtilitiesView() { InitializeComponent(); List.ItemsSource = Utilities.Build().Select(u => new Row(u)).ToList(); }

    private async void Run_Click(object sender, RoutedEventArgs e)
    {
        if (((Button)sender).Tag is not Row row || OperationFlow.IsBusy) return;
        var u = row.U; var w = MainWindow.Current;
        if (u.RequiresAdmin && !Svc.IsAdmin) { w.ShowToast("Cet utilitaire nécessite les droits administrateur : relance Blatja en administrateur.", Kind.Warning); return; }
        if (u.Warning is not null)
        {
            int c = await w.ShowDialogAsync(u.Name, u.Warning, null, ("Lancer", "primary"), ("Annuler", "secondary"));
            if (c != 0) return;
        }
        w.SetStatus($"{u.Name}…", StatusKind.Busy);
        try
        {
            string result;
            using (w.ShowBusy(u.Name + "…")) result = await Task.Run(u.Run);
            Svc.Journal.Append(new JournalEntry(DateTime.Now, "utility:" + u.Name, u.Name, "Utility", JournalOutcome.Succeeded, result));
            w.ShowToast(result, Kind.Success);
        }
        catch (Exception ex)
        {
            Log.Write($"Utilitaire {u.Name} : {ex.Message}");
            Svc.Journal.Append(new JournalEntry(DateTime.Now, "utility:" + u.Name, u.Name, "Utility", JournalOutcome.Failed, ex.Message));
            w.ShowToast($"{u.Name} : {ex.Message}", Kind.Danger);
        }
        finally { w.SetStatus("Prêt", StatusKind.Ready); }
    }
}
