namespace Blatja.Core;

public sealed record OpStatus(Operation Op, OpState State, string? Detail);

public enum PlanItemStatus { Planned, SkippedAlreadyDone, SkippedNotApplicable, SkippedNeedsAdmin, Refused }

public sealed record PlanItem(Operation Op, OpAction Action, PlanItemStatus Status, string? Reason)
{
    public bool WillRun => Status == PlanItemStatus.Planned;
}

public sealed record Plan(IReadOnlyList<PlanItem> Items)
{
    public IEnumerable<PlanItem> Runnable => Items.Where(i => i.WillRun);
    public bool RequiresReboot => Runnable.Any(i => i.Op.Restart == RestartKind.Reboot);
    public bool RequiresSignOut => Runnable.Any(i => i.Op.Restart == RestartKind.SignOut);
}

public enum StepOutcome { Succeeded, Skipped, Failed, VerificationFailed, Refused, Cancelled }

public sealed record StepResult(PlanItem Item, StepOutcome Outcome, string Message, TimeSpan Duration);

public sealed record StepEvent(int Index, int Total, PlanItem Item, StepResult? Result);

public sealed class ExecutionReport
{
    public List<StepResult> Steps { get; } = new();
    public DateTime StartedAt { get; init; } = DateTime.Now;
    public DateTime? FinishedAt { get; set; }
    public int Succeeded => Steps.Count(s => s.Outcome == StepOutcome.Succeeded);
    public int Failed => Steps.Count(s => s.Outcome is StepOutcome.Failed or StepOutcome.VerificationFailed);
    public int Skipped => Steps.Count(s => s.Outcome is StepOutcome.Skipped or StepOutcome.Refused or StepOutcome.Cancelled);
    public bool NeedsReboot => Steps.Any(s => s.Outcome == StepOutcome.Succeeded && s.Item.Action == OpAction.Apply && s.Item.Op.Restart == RestartKind.Reboot);
    public bool NeedsSignOut => Steps.Any(s => s.Outcome == StepOutcome.Succeeded && s.Item.Op.Restart == RestartKind.SignOut);
}

/// <summary>Orchestre l'inspection, la planification et l'exécution des opérations, sans aucune dépendance à l'interface.</summary>
public sealed class OptimizationEngine
{
    private readonly SystemContext _ctx;
    private readonly IBackupStore _backups;
    private readonly IJournal _journal;
    private readonly Action<string>? _log;

    public OptimizationEngine(SystemContext ctx, IBackupStore backups, IJournal journal, Action<string>? log = null)
    {
        _ctx = ctx; _backups = backups; _journal = journal; _log = log;
    }

    public SystemContext Context => _ctx;

    /// <summary>Lit l'état réel d'une opération ; toute exception devient l'état Error plutôt que de remonter.</summary>
    public OpStatus Inspect(Operation op)
    {
        try
        {
            var app = op.CheckApplicable(_ctx);
            if (!app.Ok) return new OpStatus(op, OpState.NotApplicable, app.Reason);
            return new OpStatus(op, op.Detect(_ctx), null);
        }
        catch (Exception ex)
        {
            _log?.Invoke($"Détection {op.Id} : {ex.Message}");
            return new OpStatus(op, OpState.Error, ex.Message);
        }
    }

    /// <summary>Analyse non destructive : ne modifie rien.</summary>
    public IReadOnlyList<OpStatus> Scan(IEnumerable<Operation> ops, IProgress<(int Done, int Total)>? progress = null, CancellationToken ct = default)
    {
        var list = ops.ToList();
        var result = new List<OpStatus>(list.Count);
        for (int i = 0; i < list.Count; i++)
        {
            ct.ThrowIfCancellationRequested();
            result.Add(Inspect(list[i]));
            progress?.Report((i + 1, list.Count));
        }
        return result;
    }

    public Plan BuildPlan(IEnumerable<(Operation Op, OpAction Action)> requests)
    {
        var items = new List<PlanItem>();
        foreach (var (op, action) in requests)
        {
            var st = Inspect(op);
            if (st.State == OpState.NotApplicable) { items.Add(new(op, action, PlanItemStatus.SkippedNotApplicable, st.Detail)); continue; }
            if (SafetyPolicy.Violation(op, _ctx) is { } why) { items.Add(new(op, action, PlanItemStatus.Refused, why)); continue; }
            if (action == OpAction.Apply && st.State == OpState.Enabled) { items.Add(new(op, action, PlanItemStatus.SkippedAlreadyDone, "Déjà appliquée sur ce système.")); continue; }
            if (action == OpAction.Revert && st.State == OpState.Disabled) { items.Add(new(op, action, PlanItemStatus.SkippedAlreadyDone, "Déjà dans l'état d'origine.")); continue; }
            if (op.RequiresAdmin && !_ctx.Info.IsAdmin) { items.Add(new(op, action, PlanItemStatus.SkippedNeedsAdmin, "Nécessite les droits administrateur.")); continue; }
            items.Add(new(op, action, PlanItemStatus.Planned, null));
        }
        return new Plan(items);
    }

    public ExecutionReport Execute(Plan plan, IProgress<StepEvent>? progress = null, CancellationToken ct = default)
    {
        var report = new ExecutionReport();
        var items = plan.Items.ToList();
        for (int i = 0; i < items.Count; i++)
        {
            var item = items[i];
            if (!item.WillRun)
            {
                var outcome = item.Status == PlanItemStatus.Refused ? StepOutcome.Refused : StepOutcome.Skipped;
                Record(report, new StepResult(item, outcome, item.Reason ?? "Ignorée.", TimeSpan.Zero), i, items.Count, progress);
                continue;
            }
            if (ct.IsCancellationRequested)
            {
                Record(report, new StepResult(item, StepOutcome.Cancelled, "Annulée avant exécution.", TimeSpan.Zero), i, items.Count, progress);
                continue;
            }
            progress?.Report(new StepEvent(i, items.Count, item, null));
            Record(report, RunOne(item), i, items.Count, progress);
        }
        report.FinishedAt = DateTime.Now;
        return report;
    }

    private StepResult RunOne(PlanItem item)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        var op = item.Op;
        try
        {
            if (item.Action == OpAction.Apply)
            {
                var backup = new BackupRecord { OpId = op.Id };
                op.Capture(_ctx, backup);
                _backups.Save(backup);                       // sauvegarde AVANT toute modification
                try { op.Apply(_ctx); }
                catch
                {
                    TryRollback(op, backup);                 // échec partiel : on revient à l'état d'origine
                    throw;
                }
                var after = op.Detect(_ctx);
                if (after != OpState.Enabled)
                {
                    TryRollback(op, backup);
                    return new StepResult(item, StepOutcome.VerificationFailed, $"Modification non vérifiée (état lu : {after}) — annulée.", sw.Elapsed);
                }
                return new StepResult(item, StepOutcome.Succeeded, "Appliquée et vérifiée.", sw.Elapsed);
            }
            else
            {
                var backup = _backups.Load(op.Id);
                op.Revert(_ctx, backup);
                var after = op.Detect(_ctx);
                if (after == OpState.Enabled && !op.EnabledIsDefault)
                    return new StepResult(item, StepOutcome.VerificationFailed, "La restauration n'a pas pu être confirmée.", sw.Elapsed);
                _backups.Remove(op.Id);
                return new StepResult(item, StepOutcome.Succeeded, backup is null ? "Rétablie aux valeurs par défaut (aucune sauvegarde Blatja)." : "Valeurs d'origine rétablies et vérifiées.", sw.Elapsed);
            }
        }
        catch (Exception ex)
        {
            _log?.Invoke($"{op.Id} : {ex}");
            return new StepResult(item, StepOutcome.Failed, ex.Message, sw.Elapsed);
        }
    }

    private void TryRollback(Operation op, BackupRecord backup)
    {
        try { op.Revert(_ctx, backup); }
        catch (Exception ex) { _log?.Invoke($"Rollback {op.Id} impossible : {ex.Message}"); }
    }

    private void Record(ExecutionReport report, StepResult r, int index, int total, IProgress<StepEvent>? progress)
    {
        report.Steps.Add(r);
        var outcome = r.Outcome switch
        {
            StepOutcome.Succeeded => JournalOutcome.Succeeded,
            StepOutcome.Failed => JournalOutcome.Failed,
            StepOutcome.VerificationFailed => JournalOutcome.VerificationFailed,
            StepOutcome.Refused => JournalOutcome.Refused,
            StepOutcome.Cancelled => JournalOutcome.Cancelled,
            _ => JournalOutcome.Skipped,
        };
        try { _journal.Append(new JournalEntry(DateTime.Now, r.Item.Op.Id, r.Item.Op.Name, r.Item.Action.ToString(), outcome, r.Message)); }
        catch (Exception ex) { _log?.Invoke($"Journal : {ex.Message}"); }
        progress?.Report(new StepEvent(index, total, r.Item, r));
    }
}
