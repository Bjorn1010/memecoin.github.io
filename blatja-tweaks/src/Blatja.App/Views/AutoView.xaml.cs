using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public sealed class PlanRow : INotifyPropertyChanged
{
    private bool _sel = true;
    public required OpVm Vm { get; init; }
    public string Name => Vm.Name;
    public string Description => Vm.Description;
    public string Meta => $"Impact {Vm.ImpactText.ToLowerInvariant()} · risque {Vm.RiskText.ToLowerInvariant()}" + (Vm.HasRestart ? " · " + Vm.RestartText.ToLowerInvariant() : "");
    public bool Selected { get => _sel; set { _sel = value; PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Selected))); } }
    public event PropertyChangedEventHandler? PropertyChanged;
}

public sealed record FindingVm(string KindText, Style BadgeStyle, string Title, string Detail, string Evidence);

/// <summary>Parcours en 5 étapes. Les étapes 4 et 5 (exécution, rapport) sont portées par OperationFlow.</summary>
public partial class AutoView : PageBase
{
    private bool _scanning;
    private List<PlanRow> _plan = new();

    public AutoView()
    {
        InitializeComponent();
        BtnStart.Click += async (_, _) => await ScanAsync();
        BtnRescan.Click += async (_, _) => await ScanAsync();
        BtnRun.Click += async (_, _) => await RunPlanAsync();
        SetStep(0);
    }

    private void SetStep(int active, int done = 0)
    {
        var dots = new[] { D1, D2, D3, D4, D5 }; var labels = new[] { L1, L2, L3, L4, L5 };
        for (int i = 0; i < 5; i++)
        {
            bool isDone = i + 1 <= done, isActive = i + 1 == active;
            dots[i].Background = (Brush)FindResource(isActive ? "Accent" : isDone ? "SuccessSoft" : "SurfaceHi");
            ((TextBlock)dots[i].Child).Foreground = (Brush)FindResource(isActive ? "Bg" : isDone ? "Success" : "Text2");
            labels[i].Foreground = (Brush)FindResource(isActive ? "Text" : "Text2");
            labels[i].FontWeight = isActive ? FontWeights.SemiBold : FontWeights.Normal;
        }
    }

    private async Task ScanAsync()
    {
        if (_scanning || OperationFlow.IsBusy) return;
        _scanning = true;
        PanelIdle.Visibility = PanelResults.Visibility = Visibility.Collapsed; PanelScan.Visibility = Visibility.Visible;
        SetStep(1);
        MainWindow.Current.SetStatus("Analyse en cours…", StatusKind.Busy);
        int total = Svc.Catalog.Count + 4, done = 0;
        void Step(string label, string detail) { ScanLabel.Text = label; ScanDetail.Text = detail; ScanBar.Value = done * 100.0 / total; }

        try
        {
            Step("Lecture de l'état des optimisations Windows", "Aucune modification n'est effectuée.");
            var prog = new Progress<(int Done, int Total)>(p => { done = p.Done; Step("Lecture de l'état des optimisations Windows", $"{p.Done} / {p.Total} contrôlées"); });
            await OpStore.RefreshAsync(prog);

            done = Svc.Catalog.Count + 1; Step("Programmes lancés au démarrage", "Clés Run et dossiers Démarrage");
            int? startup = null; try { startup = await Task.Run(() => Svc.Startup.List().Count(e => e.Enabled)); } catch (Exception ex) { Log.Write("Scan démarrage : " + ex.Message); }

            done++; Step("Processus et mémoire", "Applications les plus consommatrices");
            IReadOnlyList<ProcessUsage> procs = Array.Empty<ProcessUsage>();
            try { procs = await Task.Run(Svc.Processes.Sample); } catch (Exception ex) { Log.Write("Scan processus : " + ex.Message); }

            done++; Step("Disque, mémoire et GPU", "Valeurs mesurées à l'instant");
            await Task.Delay(150);
            var m = Svc.Metrics;
            var input = new DiagnosticInput(m.DiskUsedGb, m.DiskTotalGb, m.Ram.Last, m.RamTotalGb, procs, startup, m.GpuNow is { } g && !double.IsNaN(g.Temp) ? g.Temp : null,
                OpStore.All.Select(v => new OpStatus(v.Op, v.State, v.Detail)).ToList(), Svc.IsAdmin);
            var found = DiagnosticRules.Evaluate(input);
            ScanBar.Value = 100;

            ShowResults(found);
            Svc.Journal.Append(new JournalEntry(DateTime.Now, "scan", "Analyse du système", "Scan", JournalOutcome.Succeeded, $"{found.Count} constat(s), aucune modification"));
        }
        catch (Exception ex)
        {
            Log.Write("Analyse : " + ex);
            PanelScan.Visibility = Visibility.Collapsed; PanelIdle.Visibility = Visibility.Visible; SetStep(0);
            MainWindow.Current.ShowToast("L'analyse a échoué : " + ex.Message, Kind.Danger);
        }
        finally { _scanning = false; MainWindow.Current.SetStatus("Prêt", StatusKind.Ready); }
    }

    private void ShowResults(IReadOnlyList<Finding> found)
    {
        PanelScan.Visibility = Visibility.Collapsed; PanelResults.Visibility = Visibility.Visible;

        Findings.ItemsSource = found.Select(f => new FindingVm(
            f.Kind switch { FindingKind.Problem => "Problème", FindingKind.Improvement => "Amélioration", _ => "Info" },
            (Style)FindResource(f.Kind switch { FindingKind.Problem => "Badge.Danger", FindingKind.Improvement => "Badge.Warning", _ => "Badge" }),
            f.Title, f.Detail, f.Evidence)).ToList();
        int problems = found.Count(f => f.Kind == FindingKind.Problem), improv = found.Count(f => f.Kind == FindingKind.Improvement);
        DiagSub.Text = $"{problems} problème(s) démontré(s) par les mesures · {improv} amélioration(s) possible(s)";
        DiagEmpty.Visibility = found.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        DiagEmpty.Text = "Aucun problème n'est démontré par les mesures. Rien à corriger.";

        _plan = OpStore.All.Where(v => v.State == OpState.Disabled && v.Recommended && (!v.NeedsAdmin || Svc.IsAdmin || true))
                           .Select(v => new PlanRow { Vm = v }).ToList();
        PlanList.ItemsSource = _plan;
        PlanSub.Text = _plan.Count == 0 ? "Aucune modification recommandée." : $"{_plan.Count} modification(s) recommandée(s), décochables une à une.";
        PlanEmpty.Visibility = _plan.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        PlanEmpty.Text = "Toutes les optimisations recommandées applicables à ce système sont déjà en place.";
        BtnRun.IsEnabled = _plan.Count > 0;
        SetStep(3, 2);
    }

    private async Task RunPlanAsync()
    {
        var chosen = _plan.Where(p => p.Selected).Select(p => (p.Vm.Op, OpAction.Apply)).ToList();
        if (chosen.Count == 0) { MainWindow.Current.ShowToast("Aucune modification n'est cochée.", Kind.Info); return; }
        SetStep(4, 3);
        var report = await OperationFlow.RunAsync(chosen, $"Appliquer le plan ({chosen.Count} modification(s))");
        SetStep(report is null ? 3 : 5, report is null ? 2 : 4);
        if (report is not null) await ScanAsync();
    }

    public override void OnShow() { if (OpStore.LastScan is not null && PanelResults.Visibility != Visibility.Visible && !_scanning && PanelScan.Visibility != Visibility.Visible) { } }
}
