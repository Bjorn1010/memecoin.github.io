using System.ComponentModel;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Animation;
using Blatja.App.Controls;
using Blatja.App.Services;
using Blatja.Core;

namespace Blatja.App.Shell;

/// <summary>Ligne de la liste d'exécution. L'état affiché est celui du moteur, jamais simulé.</summary>
public sealed class StepVm : INotifyPropertyChanged
{
    private string _glyph = "·", _message = "En attente"; private Brush _brush = Brushes.Gray;
    public string Name { get; init; } = "";
    public string Glyph { get => _glyph; private set { _glyph = value; N(nameof(Glyph)); } }
    public string Message { get => _message; private set { _message = value; N(nameof(Message)); } }
    public Brush GlyphBrush { get => _brush; private set { _brush = value; N(nameof(GlyphBrush)); } }

    public void Set(string glyph, string message, string brushKey)
    {
        Glyph = glyph; Message = message;
        GlyphBrush = (Brush)Application.Current.FindResource(brushKey);
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void N(string p) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(p));
}

/// <summary>
/// Parcours complet d'une modification : droits → confirmation (résumé) → point de restauration →
/// mesure avant → exécution (progression réelle) → mesure après → rapport. Une seule opération à la fois.
/// </summary>
public static class OperationFlow
{
    private static bool _busy;
    private static bool _restoreHandled;     // point de restauration créé, déjà récent, ou refusé explicitement

    public static bool IsBusy => _busy;

    public static async Task<ExecutionReport?> RunAsync(IReadOnlyList<(Operation Op, OpAction Action)> requests, string title)
    {
        var w = MainWindow.Current;
        if (_busy) { w.ShowToast("Une opération est déjà en cours.", Kind.Warning); return null; }
        if (requests.Count == 0) return null;
        _busy = true;
        w.SetStatus("Préparation…", StatusKind.Busy);
        try
        {
            var plan = Svc.Engine.BuildPlan(requests);

            // ── 1. droits administrateur ──
            var needAdmin = plan.Items.Where(i => i.Status == PlanItemStatus.SkippedNeedsAdmin).ToList();
            if (needAdmin.Count > 0)
            {
                bool others = plan.Runnable.Any();
                var lines = needAdmin.Select(i => w.DialogLine(i.Op.Name, "Nécessite les droits administrateur.", Kind.Warning)).ToList();
                int c = await w.ShowDialogAsync("Droits administrateur nécessaires",
                    others ? "Certaines modifications exigent les droits administrateur. Tu peux relancer Blatja en administrateur, ou continuer avec les autres."
                           : "Ces modifications exigent les droits administrateur. Blatja fonctionne actuellement en lecture seule.",
                    lines, others ? new[] { ("Relancer en administrateur", "primary"), ("Continuer sans elles", "secondary"), ("Annuler", "ghost") }
                                  : new[] { ("Relancer en administrateur", "primary"), ("Annuler", "ghost") });
                if (c == 0)
                {
                    if (Elevation.Relaunch()) Application.Current.Shutdown();
                    else w.ShowToast("Relance annulée : l'invite Windows a été refusée.", Kind.Warning);
                    return null;
                }
                if (c != 1 || !others) return null;
            }

            var runnable = plan.Runnable.ToList();
            if (runnable.Count == 0)
            {
                var why = plan.Items.Select(i => w.DialogLine(i.Op.Name, i.Reason, i.Status == PlanItemStatus.Refused ? Kind.Danger : Kind.Info)).ToList();
                await w.ShowDialogAsync("Aucun changement à effectuer", "Rien ne sera modifié.", why, ("Fermer", "secondary"));
                return null;
            }

            // ── 2. résumé et confirmation ──
            bool anyApply = runnable.Any(i => i.Action == OpAction.Apply);
            var summary = new List<UIElement>();
            foreach (var i in runnable)
                summary.Add(w.DialogLine(i.Op.Name,
                    (i.Action == OpAction.Apply ? "Sera appliquée" : "Valeurs d'origine rétablies") + (i.Op.Restart == RestartKind.Reboot ? " · redémarrage requis" : i.Op.Restart == RestartKind.SignOut ? " · reconnexion requise" : ""),
                    i.Op.Risk == Risk.Medium ? Kind.Warning : Kind.Success, "Risque " + (i.Op.Risk == Risk.Low ? "faible" : "moyen")));
            foreach (var i in plan.Items.Where(i => !i.WillRun && i.Status != PlanItemStatus.SkippedNeedsAdmin))
                summary.Add(w.DialogLine(i.Op.Name + " — ignorée", i.Reason, i.Status == PlanItemStatus.Refused ? Kind.Danger : Kind.Info));

            int go = await w.ShowDialogAsync(title,
                anyApply ? "Voici les modifications qui vont être effectuées. Les valeurs d'origine sont sauvegardées avant chaque changement, et chaque résultat est vérifié."
                         : "Voici les restaurations qui vont être effectuées.",
                summary, (runnable.Count == 1 ? "Confirmer" : $"Confirmer {runnable.Count} changements", anyApply ? "primary" : "primary"), ("Annuler", "secondary"));
            if (go != 0) return null;

            // ── 3. point de restauration (avant la première modification) ──
            if (anyApply && !_restoreHandled && !await EnsureRestorePointAsync(w)) return null;

            // ── 4-7. exécution ──
            return await ExecuteAsync(w, plan, title);
        }
        finally
        {
            _busy = false;
            w.SetStatus("Prêt", StatusKind.Ready);
            _ = OpStore.RefreshAsync();
        }
    }

    private static async Task<bool> EnsureRestorePointAsync(MainWindow w)
    {
        if (RestorePoints.Recent() is { } when)
        {
            _restoreHandled = true; Log.Write($"Point de restauration récent trouvé ({when:g})");
            return true;
        }
        while (true)
        {
            int c = await w.ShowDialogAsync("Créer un point de restauration ?",
                "Avant de modifier Windows, Blatja recommande de créer un point de restauration. Il te permettra de revenir à l'état d'avant, même si une modification ne se comporte pas comme prévu.",
                null, ("Créer le point de restauration", "primary"), ("Continuer sans", "secondary"), ("Annuler", "ghost"));
            if (c == 0)
            {
                (bool ok, string msg) res;
                w.SetStatus("Création du point de restauration…", StatusKind.Busy);
                using (w.ShowBusy("Création du point de restauration… (jusqu'à une minute)"))
                    res = await Task.Run(() => RestorePoints.Create("Avant optimisation", "Point créé automatiquement avant des modifications", "#FF5C50"));
                if (res.ok) { _restoreHandled = true; w.ShowToast("Point de restauration créé.", Kind.Success); return true; }
                int r = await w.ShowDialogAsync("Le point de restauration n'a pas pu être créé", res.msg + "\n\nSur certaines installations (dont Tiny11), la protection du système est désactivée. Tu peux réessayer, continuer sans point, ou annuler.",
                    null, ("Réessayer", "primary"), ("Continuer sans point de restauration", "secondary"), ("Annuler", "ghost"));
                if (r == 0) continue;
                if (r != 1) return false;
            }
            else if (c != 1) return false;

            int sure = await w.ShowDialogAsync("Continuer sans point de restauration ?",
                "Tu pourras annuler les modifications Blatja une par une grâce aux valeurs d'origine sauvegardées, mais pas revenir à un état complet du système.",
                null, ("Continuer quand même", "danger"), ("Retour", "secondary"));
            if (sure == 0) { _restoreHandled = true; Log.Write("Point de restauration refusé par l'utilisateur"); return true; }
        }
    }

    private static async Task<ExecutionReport?> ExecuteAsync(MainWindow w, Plan plan, string title)
    {
        var items = plan.Items.ToList();
        var steps = new List<StepVm> { new() { Name = "Mesure avant modification" } };
        steps.AddRange(items.Select(i => new StepVm { Name = i.Op.Name }));
        steps.Add(new StepVm { Name = "Mesure après modification" });
        foreach (var s in steps) s.Set("·", "En attente", "Text3");

        w.RunTitle.Text = title; w.RunSubtitle.Text = "Ne ferme pas Blatja pendant l'opération.";
        w.RunSteps.ItemsSource = steps; w.RunBar.Value = 0; w.RunResult.Visibility = Visibility.Collapsed;
        w.RunSpinner.Visibility = Visibility.Visible; w.RunDone.Visibility = Visibility.Collapsed;
        w.RunCancel.Visibility = Visibility.Visible; w.RunCancel.IsEnabled = true;
        w.RunJournal.Visibility = Visibility.Collapsed; w.RunClose.Visibility = Visibility.Collapsed;
        w.RunLayer.Opacity = 0; w.RunLayer.Visibility = Visibility.Visible;
        w.RunLayer.BeginAnimation(UIElement.OpacityProperty, new DoubleAnimation(1, TimeSpan.FromMilliseconds(140)));
        w.SetStatus("Application des changements…", StatusKind.Busy);

        using var cts = new CancellationTokenSource();
        void OnCancel(object s, RoutedEventArgs e) { cts.Cancel(); w.RunCancel.IsEnabled = false; w.RunSubtitle.Text = "Arrêt demandé : l'opération en cours va se terminer."; }
        w.RunCancel.Click += OnCancel;

        int total = items.Count + 2;
        void Progress(int done, string label) { Anim.Smooth(w.RunBar, done * 100.0 / total, 300); }

        // mesure avant
        steps[0].Set("…", "Mesure du processeur, de la mémoire et du réseau (quelques secondes)", "Accent");
        SystemSnapshot? before = null, after = null;
        try { before = await SnapshotService.TakeAsync(includePing: true); steps[0].Set("✓", "Mesure instantanée enregistrée", "Success"); }
        catch (Exception ex) { Log.Write("Mesure avant : " + ex.Message); steps[0].Set("–", "Mesure indisponible", "Text3"); }
        Progress(1, "");

        // exécution réelle, sur un thread de travail ; la progression revient sur l'interface
        var progress = new Progress<StepEvent>(ev =>
        {
            var vm = steps[ev.Index + 1];
            if (ev.Result is null) { vm.Set("…", ev.Item.Action == OpAction.Apply ? "Application en cours…" : "Restauration en cours…", "Accent"); return; }
            var r = ev.Result;
            switch (r.Outcome)
            {
                case StepOutcome.Succeeded: vm.Set("✓", r.Message, "Success"); break;
                case StepOutcome.Failed or StepOutcome.VerificationFailed: vm.Set("✕", r.Message, "Danger"); break;
                case StepOutcome.Refused: vm.Set("✕", "Refusée par la politique de sécurité : " + r.Message, "Danger"); break;
                default: vm.Set("–", r.Message, "Text3"); break;
            }
            Progress(ev.Index + 2, "");
        });
        ExecutionReport report;
        try { report = await Task.Run(() => Svc.Engine.Execute(plan, progress, cts.Token)); }
        catch (Exception ex)
        {
            Log.Write("Exécution : " + ex);
            w.RunLayer.Visibility = Visibility.Collapsed; w.RunCancel.Click -= OnCancel;
            await w.ShowDialogAsync("Erreur inattendue", ex.Message, null, ("Fermer", "secondary"));
            return null;
        }

        // mesure après
        steps[^1].Set("…", "Mesure après modification", "Accent");
        try { after = await SnapshotService.TakeAsync(includePing: before?.Ping is not null); steps[^1].Set("✓", "Mesure instantanée enregistrée", "Success"); }
        catch (Exception ex) { Log.Write("Mesure après : " + ex.Message); steps[^1].Set("–", "Mesure indisponible", "Text3"); }
        Anim.Smooth(w.RunBar, 100, 350);

        // rapport
        w.RunSpinner.Visibility = Visibility.Collapsed; w.RunCancel.Visibility = Visibility.Collapsed; w.RunCancel.Click -= OnCancel;
        PlayResultIcon(w, report.Failed == 0);
        w.RunTitle.Text = report.Failed == 0 ? "Terminé" : "Terminé avec des erreurs";
        w.RunSubtitle.Text = $"{report.Steps.Count} opération(s) traitée(s) en {(report.FinishedAt - report.StartedAt)?.TotalSeconds:0} s.";
        w.RunBadges.Children.Clear();
        AddBadge(w, $"{report.Succeeded} réussie(s)", "Badge.Success");
        if (report.Failed > 0) AddBadge(w, $"{report.Failed} en échec", "Badge.Danger");
        if (report.Skipped > 0) AddBadge(w, $"{report.Skipped} ignorée(s)", "Badge");
        var notices = new List<string>();
        if (report.NeedsReboot) notices.Add("Redémarre le PC pour activer tous les réglages.");
        if (report.NeedsSignOut) notices.Add("Certains réglages s'appliquent à la prochaine ouverture de session.");
        w.RunNotice.Text = string.Join(" ", notices); w.RunNotice.Visibility = notices.Count > 0 ? Visibility.Visible : Visibility.Collapsed;

        if (before is not null && after is not null)
        {
            w.CompareRows.ItemsSource = SnapshotComparison.Compare(before, after);
            w.CompareTitle.Visibility = w.CompareHead.Visibility = w.CompareRows.Visibility = w.CompareNote.Visibility = Visibility.Visible;
            w.CompareNote.Text = "Ces mesures sont instantanées : elles varient d'une seconde à l'autre et ne sont pas un benchmark. Elles n'indiquent ni gain de FPS ni baisse de ping garantis. " +
                                 "Pour comparer des performances en jeu, refais le même scénario avant et après.";
        }
        else
        {
            w.CompareTitle.Visibility = w.CompareHead.Visibility = w.CompareRows.Visibility = Visibility.Collapsed;
            w.CompareNote.Visibility = Visibility.Visible;
            w.CompareNote.Text = "Comparaison avant/après indisponible : une des deux mesures n'a pas pu être prise.";
        }
        w.RunResult.Visibility = Visibility.Visible;
        w.RunJournal.Visibility = w.RunClose.Visibility = Visibility.Visible;

        var done = new TaskCompletionSource<bool>();
        void CloseReport(object s, RoutedEventArgs e) { done.TrySetResult(false); }
        void ToJournal(object s, RoutedEventArgs e) { done.TrySetResult(true); }
        w.RunClose.Click += CloseReport; w.RunJournal.Click += ToJournal;
        w.RunClose.Focus();
        bool openJournal = await done.Task;
        w.RunClose.Click -= CloseReport; w.RunJournal.Click -= ToJournal;
        w.RunLayer.Visibility = Visibility.Collapsed;
        if (openJournal) w.Navigate("history");

        Log.Write($"Exécution terminée : {report.Succeeded} ok, {report.Failed} échec(s), {report.Skipped} ignorée(s)");
        return report;
    }

    /// <summary>Icône de résultat : le cercle « pop » avec rebond, puis une onde se propage (réussite) ou la croix apparaît (erreurs).</summary>
    private static void PlayResultIcon(MainWindow w, bool ok)
    {
        string color = ok ? "Success" : "Danger";
        w.RunDoneBg.Fill = (Brush)Application.Current.FindResource(ok ? "SuccessSoft" : "DangerSoft");
        w.RunDoneBg.Stroke = w.RunPulse.Stroke = w.RunDoneIcon.Fill = (Brush)Application.Current.FindResource(color);
        w.RunDoneIcon.Data = (Geometry)Application.Current.FindResource(ok ? "IconCheck" : "IconWarning");
        w.RunDone.Visibility = Visibility.Visible;
        var pop = new DoubleAnimation(0.2, 1, TimeSpan.FromMilliseconds(460)) { EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 1.3 } };
        w.RunDoneScale.BeginAnimation(ScaleTransform.ScaleXProperty, pop); w.RunDoneScale.BeginAnimation(ScaleTransform.ScaleYProperty, pop);
        if (!ok) return;
        var grow = new DoubleAnimation(1, 2.1, TimeSpan.FromMilliseconds(700)) { BeginTime = TimeSpan.FromMilliseconds(220), EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } };
        w.RunPulseScale.BeginAnimation(ScaleTransform.ScaleXProperty, grow); w.RunPulseScale.BeginAnimation(ScaleTransform.ScaleYProperty, grow);
        w.RunPulse.BeginAnimation(UIElement.OpacityProperty, new DoubleAnimation(0.7, 0, TimeSpan.FromMilliseconds(700)) { BeginTime = TimeSpan.FromMilliseconds(220) });
    }

    private static void AddBadge(MainWindow w, string text, string style)
    {
        w.RunBadges.Children.Add(new System.Windows.Controls.Border
        {
            Style = (Style)Application.Current.FindResource(style), Margin = new Thickness(0, 0, 8, 0), Padding = new Thickness(10, 3, 10, 3),
            Child = new System.Windows.Controls.TextBlock { Text = text, FontSize = 12.5 },
        });
    }
}
