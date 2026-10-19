using Blatja.Core;
using Xunit;

namespace Blatja.Tests;

public class EngineTests
{
    private const string P = @"HKCU\Software\Test";

    private static RegistryOperation RegOp(string id, string name = "V", bool admin = false, RestartKind restart = RestartKind.None, int value = 1) =>
        new(new[] { new RegTarget(P, name, RegValue.DWord(value)) })
        { Id = id, Name = id, Description = "d", Effect = "e", Category = Categories.Gaming, RequiresAdmin = admin, Restart = restart };

    [Fact] public void Apply_success_is_backed_up_verified_and_journaled()
    {
        var e = new Env(); e.Reg.Seed(P, "V", RegValue.DWord(9));
        var op = RegOp("a");
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) }));
        Assert.Equal(1, report.Succeeded);
        Assert.True(e.Reg.Get(P, "V")!.Value.SameAs(RegValue.DWord(1)));
        Assert.NotNull(e.Backups.Load("a"));
        Assert.Single(e.Journal.Entries); Assert.Equal(JournalOutcome.Succeeded, e.Journal.Entries[0].Outcome);
    }

    [Fact] public void Already_applied_operation_is_skipped_not_reapplied()
    {
        var e = new Env(); e.Reg.Seed(P, "V", RegValue.DWord(1));
        var plan = e.Engine.BuildPlan(new[] { (RegOp("a") as Operation, OpAction.Apply) });
        Assert.Equal(PlanItemStatus.SkippedAlreadyDone, plan.Items[0].Status);
        Assert.Empty(e.Backups.Items);
    }

    [Fact] public void Operation_requiring_admin_is_skipped_without_admin_rights()
    {
        var e = new Env(); e.Info.IsAdmin = false;
        var plan = e.Engine.BuildPlan(new[] { (RegOp("a", admin: true) as Operation, OpAction.Apply) });
        Assert.Equal(PlanItemStatus.SkippedNeedsAdmin, plan.Items[0].Status);
        var report = e.Engine.Execute(plan);
        Assert.Equal(StepOutcome.Skipped, report.Steps[0].Outcome);
        Assert.Null(e.Reg.Get(P, "V"));
    }

    [Fact] public void Operation_without_admin_requirement_still_runs_without_admin_rights()
    {
        var e = new Env(); e.Info.IsAdmin = false;
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (RegOp("a", admin: false) as Operation, OpAction.Apply) }));
        Assert.Equal(1, report.Succeeded);
    }

    [Fact] public void Failure_in_apply_rolls_back_and_the_run_continues_with_the_next_operation()
    {
        var e = new Env();
        var bad = RegOp("bad", "A"); var good = RegOp("good", "B");
        e.Reg.FailSetWhen = (_, n) => n == "A";
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (bad as Operation, OpAction.Apply), (good as Operation, OpAction.Apply) }));
        Assert.Equal(StepOutcome.Failed, report.Steps[0].Outcome);
        Assert.Equal(StepOutcome.Succeeded, report.Steps[1].Outcome);
        Assert.Null(e.Reg.Get(P, "A"));
        Assert.NotNull(e.Reg.Get(P, "B"));
    }

    [Fact] public void Partial_apply_is_rolled_back_to_the_original_values()
    {
        var e = new Env(); e.Reg.Seed(P, "A", RegValue.DWord(5)); e.Reg.Seed(P, "B", RegValue.DWord(6));
        var op = new RegistryOperation(new[] { new RegTarget(P, "A", RegValue.DWord(1)), new RegTarget(P, "B", RegValue.DWord(1)) }) { Id = "p", Name = "p", Description = "d", Effect = "e", Category = Categories.Gaming, RequiresAdmin = false };
        e.Reg.FailSetWhen = (_, n) => n == "B";   // A est écrite, B échoue
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) }));
        Assert.Equal(StepOutcome.Failed, report.Steps[0].Outcome);
        e.Reg.FailSetWhen = null;
        Assert.True(e.Reg.Get(P, "A")!.Value.SameAs(RegValue.DWord(5)));
        Assert.True(e.Reg.Get(P, "B")!.Value.SameAs(RegValue.DWord(6)));
    }

    [Fact] public void Change_that_cannot_be_verified_is_reported_and_undone()
    {
        var e = new Env(); bool applied = false;
        var op = CustomOp.Make("liar", _ => OpState.Disabled, _ => applied = true);   // prétend réussir mais l'état ne change jamais
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) }));
        Assert.True(applied);
        Assert.Equal(StepOutcome.VerificationFailed, report.Steps[0].Outcome);
        Assert.Equal(1, report.Failed);
    }

    [Fact] public void Cancellation_stops_before_the_next_operation()
    {
        var e = new Env(); using var cts = new CancellationTokenSource();
        var first = CustomOp.Make("first", c => e.Reg.Get(P, "X") is null ? OpState.Disabled : OpState.Enabled, c => { c.Registry.Set(P, "X", RegValue.DWord(1)); cts.Cancel(); });
        var second = CustomOp.Make("second", _ => OpState.Disabled, _ => throw new Exception("ne doit pas s'exécuter"));
        var plan = e.Engine.BuildPlan(new[] { (first as Operation, OpAction.Apply), (second as Operation, OpAction.Apply) });
        var report = e.Engine.Execute(plan, null, cts.Token);
        Assert.Equal(StepOutcome.Succeeded, report.Steps[0].Outcome);
        Assert.Equal(StepOutcome.Cancelled, report.Steps[1].Outcome);
    }

    [Fact] public void Reboot_requirement_is_reported_only_for_operations_that_succeeded()
    {
        var e = new Env();
        var ok = RegOp("ok", "A", restart: RestartKind.Reboot);
        var report = e.Engine.Execute(e.Engine.BuildPlan(new[] { (ok as Operation, OpAction.Apply) }));
        Assert.True(report.NeedsReboot);

        var e2 = new Env(); e2.Reg.ThrowOnSet = true;
        var report2 = e2.Engine.Execute(e2.Engine.BuildPlan(new[] { (RegOp("ko", "A", restart: RestartKind.Reboot) as Operation, OpAction.Apply) }));
        Assert.False(report2.NeedsReboot);
    }

    [Fact] public void Revert_restores_the_exact_original_value_and_clears_the_backup()
    {
        var e = new Env(); e.Reg.Seed(P, "V", RegValue.DWord(42));
        var op = RegOp("a");
        e.Engine.Execute(e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) }));
        var rep = e.Engine.Execute(e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Revert) }));
        Assert.Equal(1, rep.Succeeded);
        Assert.True(e.Reg.Get(P, "V")!.Value.SameAs(RegValue.DWord(42)));
        Assert.Null(e.Backups.Load("a"));
    }

    [Fact] public void Revert_of_an_operation_not_applied_is_skipped()
    {
        var e = new Env();
        Assert.Equal(PlanItemStatus.SkippedAlreadyDone, e.Engine.BuildPlan(new[] { (RegOp("a") as Operation, OpAction.Revert) }).Items[0].Status);
    }

    [Fact] public void Detection_exception_becomes_an_error_state_not_a_crash()
    {
        var e = new Env(); var op = CustomOp.Make("boom", _ => throw new InvalidOperationException("lecture impossible"));
        var st = e.Engine.Inspect(op);
        Assert.Equal(OpState.Error, st.State); Assert.Contains("lecture impossible", st.Detail);
    }

    [Fact] public void Operation_not_applicable_is_never_planned()
    {
        var e = new Env(); e.Info.Build = 19045;
        var op = new RegistryOperation(new[] { new RegTarget(P, "V", RegValue.DWord(1)) }) { Id = "w", Name = "w", Description = "d", Effect = "e", Category = Categories.Debloat, MinBuild = 22000 };
        Assert.Equal(PlanItemStatus.SkippedNotApplicable, e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) }).Items[0].Status);
    }

    [Fact] public void Scan_is_read_only()
    {
        var e = new Env(); var ops = new Operation[] { RegOp("a"), RegOp("b", "B") };
        e.Engine.Scan(ops);
        Assert.Empty(e.Backups.Items); Assert.Empty(e.Journal.Entries); Assert.Null(e.Reg.Get(P, "V"));
    }

    [Fact] public void A_failing_journal_never_breaks_the_operation()
    {
        var e = new Env();
        var engine = new OptimizationEngine(e.Ctx, e.Backups, new ThrowingJournal());
        var report = engine.Execute(engine.BuildPlan(new[] { (RegOp("a") as Operation, OpAction.Apply) }));
        Assert.Equal(1, report.Succeeded);
    }

    private sealed class ThrowingJournal : IJournal
    {
        public void Append(JournalEntry entry) => throw new IOException("disque plein");
        public IReadOnlyList<JournalEntry> Recent(int max = 200) => Array.Empty<JournalEntry>();
    }
}

public class SafetyTests
{
    [Theory]
    [InlineData("WinDefend")] [InlineData("mpssvc")] [InlineData("wuauserv")] [InlineData("SecurityHealthService")] [InlineData("RpcSs")] [InlineData("BITS")]
    public void Security_and_critical_services_are_refused(string service)
    {
        var e = new Env();
        var op = new ServiceOperation("auto", service) { Id = "x", Name = "x", Description = "d", Effect = "e", Category = Categories.Debloat };
        Assert.NotNull(SafetyPolicy.Violation(op, e.Ctx));
    }

    [Theory]
    [InlineData(@"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender")]
    [InlineData(@"HKLM\SOFTWARE\Microsoft\Windows Defender\Real-Time Protection")]
    [InlineData(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU")]
    [InlineData(@"HKLM\SOFTWARE\Policies\Microsoft\WindowsFirewall\DomainProfile")]
    [InlineData(@"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard")]
    public void Security_registry_keys_are_refused(string key)
    {
        var op = new RegistryOperation(new[] { new RegTarget(key, "x", RegValue.DWord(0)) }) { Id = "x", Name = "x", Description = "d", Effect = "e", Category = Categories.Debloat };
        Assert.NotNull(SafetyPolicy.Violation(op, new Env().Ctx));
    }

    [Fact] public void Engine_refuses_a_dangerous_operation_and_changes_nothing()
    {
        var e = new Env();
        var op = new RegistryOperation(new[] { new RegTarget(@"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender", "DisableAntiSpyware", RegValue.DWord(1)) }) { Id = "evil", Name = "evil", Description = "d", Effect = "e", Category = Categories.Debloat };
        var plan = e.Engine.BuildPlan(new[] { (op as Operation, OpAction.Apply) });
        Assert.Equal(PlanItemStatus.Refused, plan.Items[0].Status);
        var report = e.Engine.Execute(plan);
        Assert.Equal(StepOutcome.Refused, report.Steps[0].Outcome);
        Assert.Null(e.Reg.Get(@"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender", "DisableAntiSpyware"));
        Assert.Equal(JournalOutcome.Refused, e.Journal.Entries[0].Outcome);
    }

    [Fact] public void Catalog_construction_rejects_nothing_dangerous_and_contains_no_security_target()
    {
        var e = new Env();
        var catalog = OperationCatalog.Build(new GameDetector(e.Ctx), @"C:\Users\u\AppData\Local", _ => false);
        Assert.All(catalog, op => Assert.Null(SafetyPolicy.Violation(op, e.Ctx)));
    }

    [Fact] public void No_risk_level_above_medium_exists()
    {
        Assert.Equal(new[] { Risk.Low, Risk.Medium }, Enum.GetValues<Risk>());
    }
}

public class CatalogTests
{
    private static IReadOnlyList<Operation> Catalog(Env e) => OperationCatalog.Build(new GameDetector(e.Ctx), @"C:\Users\u\AppData\Local", _ => false);

    [Fact] public void Ids_are_unique_and_stable_format()
    {
        var ids = Catalog(new Env()).Select(o => o.Id).ToList();
        Assert.Equal(ids.Count, ids.Distinct().Count());
        Assert.All(ids, id => Assert.Matches("^[a-z0-9]+$", id));
    }

    [Fact] public void Every_operation_is_documented()
    {
        Assert.All(Catalog(new Env()), o =>
        {
            Assert.False(string.IsNullOrWhiteSpace(o.Name)); Assert.True(o.Description.Length > 20, o.Id);
            Assert.True(o.Effect.Length > 10, o.Id); Assert.False(string.IsNullOrWhiteSpace(o.Drawbacks), o.Id);
            Assert.Contains(o.Category, Categories.All); Assert.False(string.IsNullOrWhiteSpace(o.Group), o.Id);
        });
    }

    [Fact] public void Detection_never_throws_on_a_completely_empty_system()
    {
        var e = new Env(); e.Runner.Handler = (_, _) => new ProcessResult(1, "");
        var statuses = e.Engine.Scan(Catalog(e));
        Assert.DoesNotContain(statuses, s => s.State == OpState.Error);
    }

    [Fact] public void Windows_11_only_operations_are_not_applicable_on_windows_10()
    {
        var e = new Env { }; e.Info.Build = 19045;
        var st = e.Engine.Scan(Catalog(e)).ToDictionary(s => s.Op.Id);
        Assert.Equal(OpState.NotApplicable, st["widgets"].State);
        Assert.Equal(OpState.NotApplicable, st["copilot"].State);
        Assert.NotEqual(OpState.NotApplicable, st["gamemode"].State);
    }

    [Fact] public void Windows_11_enables_the_modern_operations()
    {
        var e = new Env(); e.Info.Build = 22631;
        var st = e.Engine.Scan(Catalog(e)).ToDictionary(s => s.Op.Id);
        Assert.NotEqual(OpState.NotApplicable, st["widgets"].State);
        Assert.NotEqual(OpState.NotApplicable, st["copilot"].State);
    }

    [Fact] public void Fortnite_operations_are_not_applicable_when_the_game_is_absent()
    {
        var e = new Env(); var st = e.Engine.Scan(Catalog(e)).ToDictionary(s => s.Op.Id);
        Assert.Equal(OpState.NotApplicable, st["fngpu"].State); Assert.Equal(OpState.NotApplicable, st["fnini"].State);
    }

    [Fact] public void Not_recommended_operations_are_those_with_real_side_effects()
    {
        var notRecommended = Catalog(new Env()).Where(o => !o.Recommended).Select(o => o.Id).OrderBy(x => x).ToArray();
        Assert.Equal(new[] { "onedrive", "svcprint", "svcsearch", "svcsys", "svcxbox" }, notRecommended);
    }

    [Fact] public void No_security_feature_is_ever_offered_for_disabling()
    {
        var all = string.Join(" ", Catalog(new Env()).Select(o => (o.Name + " " + o.Effect).ToLowerInvariant()));
        Assert.DoesNotContain("defender", all); Assert.DoesNotContain("pare-feu", all); Assert.DoesNotContain("smartscreen", all);
        Assert.DoesNotContain("deviceguard", all);
    }

    [Fact] public void Profiles_reference_only_existing_operations_and_grow_in_scope()
    {
        var ids = Catalog(new Env()).Select(o => o.Id).ToHashSet();
        Assert.All(GameProfiles.All, p => Assert.All(p.OpIds, id => Assert.Contains(id, ids)));
        Assert.True(GameProfiles.All[0].OpIds.Count < GameProfiles.All[1].OpIds.Count);
        Assert.True(GameProfiles.All[1].OpIds.Count < GameProfiles.All[2].OpIds.Count);
        Assert.All(GameProfiles.All, p => Assert.DoesNotContain(Catalog(new Env()).Where(o => !o.Recommended).Select(o => o.Id), id => p.OpIds.Contains(id)));
    }

    [Fact] public void Full_apply_and_revert_cycle_on_the_whole_registry_catalog_restores_the_system()
    {
        var e = new Env();
        e.Reg.Seed(@"HKCU\Control Panel\Mouse", "MouseSpeed", RegValue.Str("1"));
        e.Reg.Seed(@"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{A}", "IPAddress", RegValue.Str("1.2.3.4"));
        e.Runner.Handler = (_, _) => new ProcessResult(1, "");
        var ops = Catalog(e).OfType<RegistryOperation>().ToList();
        var applicable = ops.Where(o => o.CheckApplicable(e.Ctx).Ok).Cast<Operation>().ToList();
        Assert.True(applicable.Count >= 15);

        var apply = e.Engine.Execute(e.Engine.BuildPlan(applicable.Select(o => (o, OpAction.Apply))));
        Assert.True(apply.Failed == 0, "Apply KO : " + string.Join(" | ", apply.Steps.Where(x => x.Outcome == StepOutcome.Failed || x.Outcome == StepOutcome.VerificationFailed).Select(x => x.Item.Op.Id + " : " + x.Message)));
        Assert.All(applicable, o => Assert.Equal(OpState.Enabled, o.Detect(e.Ctx)));

        var revert = e.Engine.Execute(e.Engine.BuildPlan(applicable.Select(o => (o, OpAction.Revert))));
        Assert.True(revert.Failed == 0, "Revert KO : " + string.Join(" | ", revert.Steps.Where(x => x.Outcome == StepOutcome.Failed || x.Outcome == StepOutcome.VerificationFailed).Select(x => x.Item.Op.Id + " : " + x.Message)));
        Assert.True(e.Reg.Get(@"HKCU\Control Panel\Mouse", "MouseSpeed")!.Value.SameAs(RegValue.Str("1")));
        var stillEnabled = applicable.Where(o => o.Detect(e.Ctx) == OpState.Enabled && o.Id is not "gamemode").Select(o => o.Id).ToList();
        Assert.True(stillEnabled.Count == 0 || stillEnabled.All(id => id == "gamemode"), "Encore actives après restauration : " + string.Join(", ", stillEnabled));
    }
}
