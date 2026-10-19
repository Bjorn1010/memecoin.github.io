using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;
using Microsoft.Win32;

namespace Blatja.App.Views;

public partial class HistoryView : PageBase
{
    private sealed record JRow(DateTime Time, string OpName, string Message, string ActionText, string OutcomeText, Style BadgeStyle);
    private sealed record BRow(string OpId, string Name, string Info, string ButtonText, bool Active);

    public HistoryView()
    {
        InitializeComponent();
        FAll.Checked += (_, _) => Load(); FBad.Checked += (_, _) => Load();
        BtnFolder.Click += (_, _) => { try { Directory.CreateDirectory(AppPaths.Root); Process.Start(new ProcessStartInfo(AppPaths.Root) { UseShellExecute = true }); } catch { } };
        BtnExport.Click += (_, _) => Export();
        OpStore.Changed += () => { if (IsVisible) Load(); };
    }

    public override void OnShow() => Load();

    private static string Action(string a) => a switch { "Apply" => "Application", "Revert" => "Restauration", "Scan" => "Analyse", "Utility" => "Utilitaire", _ => a };

    private void Load()
    {
        var all = Svc.Journal.Recent(300);
        var shown = FBad.IsChecked == true ? all.Where(e => e.Outcome is JournalOutcome.Failed or JournalOutcome.VerificationFailed or JournalOutcome.Refused).ToList() : all.ToList();
        Journal.ItemsSource = shown.Select(e => new JRow(e.Time, e.OpName, e.Message, Action(e.Action), DashboardView.OutcomeText(e.Outcome),
            (Style)FindResource(e.Outcome switch { JournalOutcome.Succeeded => "Badge.Success", JournalOutcome.Failed or JournalOutcome.VerificationFailed or JournalOutcome.Refused => "Badge.Danger", _ => "Badge" }))).ToList();
        JournalEmpty.Visibility = shown.Count == 0 ? Visibility.Visible : Visibility.Collapsed;

        var rows = new List<BRow>();
        foreach (var b in Svc.Backups.All().OrderByDescending(b => b.CreatedAt))
        {
            var vm = OpStore.Find(b.OpId);
            if (vm is null) continue;
            bool active = vm.State == OpState.Enabled;
            rows.Add(new BRow(b.OpId, vm.Name, $"Sauvegarde du {b.CreatedAt:dd/MM/yy HH:mm} · optimisation actuellement : {vm.StateText.ToLowerInvariant()}" + (active ? "" : " — opération interrompue ou déjà annulée"),
                active ? "Restaurer" : "Supprimer la sauvegarde", active));
        }
        Backups.ItemsSource = rows;
        BackupsEmpty.Visibility = rows.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    private async void Backup_Click(object sender, RoutedEventArgs e)
    {
        if (((Button)sender).Tag is not BRow row) return;
        var vm = OpStore.Find(row.OpId); if (vm is null) return;
        if (row.Active) await OperationFlow.RunAsync(new[] { (vm.Op, OpAction.Revert) }, $"Restaurer « {vm.Name} »");
        else { Svc.Backups.Remove(row.OpId); MainWindow.Current.ShowToast("Sauvegarde supprimée.", Kind.Info); }
        Load();
    }

    private void Export()
    {
        var dlg = new SaveFileDialog { FileName = $"blatja-journal-{DateTime.Now:yyyyMMdd}.txt", Filter = "Texte (*.txt)|*.txt" };
        if (dlg.ShowDialog() != true) return;
        try
        {
            File.WriteAllLines(dlg.FileName, Svc.Journal.Recent(5000).Reverse().Select(j => $"{j.Time:yyyy-MM-dd HH:mm:ss}\t{j.Action}\t{j.Outcome}\t{j.OpName}\t{j.Message}"));
            MainWindow.Current.ShowToast("Journal exporté.", Kind.Success);
        }
        catch (Exception ex) { MainWindow.Current.ShowToast("Export impossible : " + ex.Message, Kind.Danger); }
    }
}
