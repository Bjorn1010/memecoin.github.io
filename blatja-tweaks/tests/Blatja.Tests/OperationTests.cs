using Blatja.Core;
using Xunit;

namespace Blatja.Tests;

public class RegistryOperationTests
{
    private const string P = @"HKCU\Software\Test";

    private static RegistryOperation Op(bool absentMeansEnabled = false, bool cleanup = false, RegValue? def = null) =>
        new(new[] { new RegTarget(P, "Value", RegValue.DWord(1), def) }) { Id = "t", Name = "t", Description = "d", Effect = "e", Category = Categories.Gaming, AbsentMeansEnabled = absentMeansEnabled, CleanupEmptyKeys = cleanup };

    [Fact] public void Detect_Disabled_when_value_absent() => Assert.Equal(OpState.Disabled, Op().Detect(new Env().Ctx));

    [Fact] public void Detect_Enabled_when_value_matches()
    {
        var e = new Env(); e.Reg.Seed(P, "Value", RegValue.DWord(1));
        Assert.Equal(OpState.Enabled, Op().Detect(e.Ctx));
    }

    [Fact] public void Detect_Disabled_when_value_differs()
    {
        var e = new Env(); e.Reg.Seed(P, "Value", RegValue.DWord(0));
        Assert.Equal(OpState.Disabled, Op().Detect(e.Ctx));
    }

    [Fact] public void AbsentMeansEnabled_reports_enabled_when_nothing_set()
    {
        Assert.Equal(OpState.Enabled, Op(absentMeansEnabled: true).Detect(new Env().Ctx));
    }

    [Fact] public void AbsentMeansEnabled_does_not_hide_an_explicit_opposite_value()
    {
        var e = new Env(); e.Reg.Seed(P, "Value", RegValue.DWord(0));
        Assert.Equal(OpState.Disabled, Op(absentMeansEnabled: true).Detect(e.Ctx));
    }

    [Fact] public void DWord_minus_one_equals_0xFFFFFFFF()
    {
        Assert.True(RegValue.DWord(-1).SameAs(RegValue.DWordU(0xFFFFFFFF)));
    }

    [Fact] public void String_comparison_ignores_case() => Assert.True(RegValue.Str("High").SameAs(RegValue.Str("high")));

    [Fact] public void Revert_restores_original_value_from_backup()
    {
        var e = new Env(); e.Reg.Seed(P, "Value", RegValue.DWord(7));
        var op = Op(); var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx);
        Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        op.Revert(e.Ctx, b);
        Assert.True(e.Reg.Get(P, "Value")!.Value.SameAs(RegValue.DWord(7)));
    }

    [Fact] public void Revert_deletes_value_that_did_not_exist_originally()
    {
        var e = new Env(); var op = Op(); var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx); op.Revert(e.Ctx, b);
        Assert.Null(e.Reg.Get(P, "Value"));
    }

    [Fact] public void Revert_without_backup_uses_documented_default()
    {
        var e = new Env(); e.Reg.Seed(P, "Value", RegValue.DWord(1));
        Op(def: RegValue.DWord(2)).Revert(e.Ctx, null);
        Assert.True(e.Reg.Get(P, "Value")!.Value.SameAs(RegValue.DWord(2)));
    }

    [Fact] public void Cleanup_removes_empty_key_after_revert()
    {
        var e = new Env(); var op = Op(cleanup: true); var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx); op.Revert(e.Ctx, b);
        Assert.False(e.Reg.KeyExists(P));
    }

    [Fact] public void Dynamic_targets_follow_the_system_state()
    {
        var e = new Env(); e.Reg.Seed(@"HKLM\Interfaces\A", "x", RegValue.DWord(0)); e.Reg.Seed(@"HKLM\Interfaces\B", "x", RegValue.DWord(0));
        var op = new RegistryOperation(c => c.Registry.SubKeys(@"HKLM\Interfaces").Select(i => new RegTarget($@"HKLM\Interfaces\{i}", "NoDelay", RegValue.DWord(1))).ToList())
        { Id = "n", Name = "n", Description = "d", Effect = "e", Category = Categories.Network };
        op.Apply(e.Ctx);
        Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        Assert.NotNull(e.Reg.Get(@"HKLM\Interfaces\A", "NoDelay")); Assert.NotNull(e.Reg.Get(@"HKLM\Interfaces\B", "NoDelay"));
    }

    [Fact] public void No_targets_means_not_applicable()
    {
        var op = new RegistryOperation(_ => Array.Empty<RegTarget>()) { Id = "n", Name = "n", Description = "d", Effect = "e", Category = Categories.Network };
        Assert.False(op.CheckApplicable(new Env().Ctx).Ok);
    }

    [Fact] public void MinBuild_makes_operation_not_applicable_on_older_windows()
    {
        var e = new Env(); e.Info.Build = 19045;
        var op = new RegistryOperation(new[] { new RegTarget(P, "V", RegValue.DWord(1)) }) { Id = "w", Name = "w", Description = "d", Effect = "e", Category = Categories.Debloat, MinBuild = 22000 };
        var app = op.CheckApplicable(e.Ctx);
        Assert.False(app.Ok); Assert.Contains("19045", app.Reason);
    }
}

public class ServiceOperationTests
{
    private const string Svc = @"HKLM\SYSTEM\CurrentControlSet\Services\Foo";

    private static (Env e, ServiceOperation op) Make(int start = 2, int delayed = 0, bool installed = true)
    {
        var e = new Env();
        if (installed) { e.Reg.Seed(Svc, "Start", RegValue.DWord(start)); if (delayed == 1) e.Reg.Seed(Svc, "DelayedAutostart", RegValue.DWord(1)); }
        // émule `sc config` en écrivant le type de démarrage dans le faux registre
        e.Runner.Handler = (f, a) =>
        {
            if (f == "sc" && a.StartsWith("config Foo start= "))
            {
                string m = a["config Foo start= ".Length..];
                e.Reg.Seed(Svc, "Start", RegValue.DWord(m switch { "disabled" => 4, "demand" => 3, "boot" => 0, _ => 2 }));
                e.Reg.Seed(Svc, "DelayedAutostart", RegValue.DWord(m == "delayed-auto" ? 1 : 0));
            }
            return new ProcessResult(0, "");
        };
        return (e, new ServiceOperation("auto", "Foo") { Id = "s", Name = "s", Description = "d", Effect = "e", Category = Categories.Debloat });
    }

    [Fact] public void Missing_service_is_not_applicable() => Assert.Equal(OpState.NotApplicable, Make(installed: false).op.Detect(Make(installed: false).e.Ctx));

    [Fact] public void Detect_reflects_start_type()
    {
        var (e, op) = Make(start: 2); Assert.Equal(OpState.Disabled, op.Detect(e.Ctx));
        var (e2, op2) = Make(start: 4); Assert.Equal(OpState.Enabled, op2.Detect(e2.Ctx));
    }

    [Fact] public void Apply_then_revert_restores_original_start_type()
    {
        var (e, op) = Make(start: 3);
        var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx); Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        op.Revert(e.Ctx, b);
        Assert.Equal(3L, Convert.ToInt64(e.Reg.Get(Svc, "Start")!.Value.Data));
    }

    [Fact] public void Delayed_auto_start_is_restored_as_delayed()
    {
        var (e, op) = Make(start: 2, delayed: 1);
        var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx); op.Revert(e.Ctx, b);
        Assert.Contains(e.Runner.Calls, c => c == "sc config Foo start= delayed-auto");
    }

    [Fact] public void Sc_failure_raises_an_error()
    {
        var (e, op) = Make(start: 2);
        e.Runner.Handler = (_, _) => new ProcessResult(5, "Accès refusé");
        Assert.Throws<InvalidOperationException>(() => op.Apply(e.Ctx));
    }
}

public class CustomOperationTests
{
    [Fact] public void PowerPlan_detects_active_scheme_and_restores_previous_one()
    {
        var e = new Env(); string active = PowerPlanOperation.BalancedScheme;
        e.Runner.Handler = (f, a) =>
        {
            if (a == "/getactivescheme") return new ProcessResult(0, $"Identificateur GUID du mode de gestion de l'alimentation : {active}  (Utilisation normale)");
            if (a.StartsWith("-setactive ")) active = a["-setactive ".Length..];
            return new ProcessResult(0, "");
        };
        var op = new PowerPlanOperation { Id = "p", Name = "p", Description = "d", Effect = "e", Category = Categories.Cpu };
        Assert.Equal(OpState.Disabled, op.Detect(e.Ctx));
        var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx);
        Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        op.Revert(e.Ctx, b);
        Assert.Equal(PowerPlanOperation.BalancedScheme, active);
        Assert.Contains(e.Runner.Calls, c => c.Contains("-delete " + PowerPlanOperation.BlatjaScheme));
    }

    [Fact] public void PowerPlan_never_edits_builtin_plans()
    {
        var e = new Env();
        new PowerPlanOperation { Id = "p", Name = "p", Description = "d", Effect = "e", Category = Categories.Cpu }.Apply(e.Ctx);
        Assert.All(e.Runner.Calls.Where(c => c.Contains("-setacvalueindex")), c => Assert.Contains(PowerPlanOperation.BlatjaScheme, c));
    }

    [Fact] public void PowerPlan_falls_back_to_high_performance_when_ultimate_is_unavailable()
    {
        var e = new Env(); string active = "";
        e.Runner.Handler = (f, a) =>
        {
            if (a.StartsWith("-duplicatescheme")) return new ProcessResult(1, "introuvable");
            if (a.StartsWith("-setactive ")) active = a["-setactive ".Length..];
            return new ProcessResult(0, "");
        };
        new PowerPlanOperation { Id = "p", Name = "p", Description = "d", Effect = "e", Category = Categories.Cpu }.Apply(e.Ctx);
        Assert.Equal(PowerPlanOperation.HighPerfScheme, active);
    }

    [Fact] public void PowerPlan_unreadable_output_is_unknown_state()
    {
        var e = new Env(); e.Runner.Handler = (_, _) => new ProcessResult(1, "");
        Assert.Equal(OpState.Unknown, new PowerPlanOperation { Id = "p", Name = "p", Description = "d", Effect = "e", Category = Categories.Cpu }.Detect(e.Ctx));
    }

    [Fact] public void LastAccess_roundtrip()
    {
        var e = new Env(); int val = 2;
        e.Runner.Handler = (f, a) =>
        {
            if (a.StartsWith("behavior query")) return new ProcessResult(0, $"DisableLastAccess = {val} (Gestion par le système)");
            if (a.StartsWith("behavior set disablelastaccess ")) val = int.Parse(a.Split(' ')[^1]);
            return new ProcessResult(0, "");
        };
        var op = new LastAccessOperation { Id = "n", Name = "n", Description = "d", Effect = "e", Category = Categories.Storage };
        Assert.Equal(OpState.Disabled, op.Detect(e.Ctx));
        var b = new BackupRecord(); op.Capture(e.Ctx, b);
        op.Apply(e.Ctx); Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        op.Revert(e.Ctx, b); Assert.Equal(2, val);
    }

    private const string Ini = @"C:\Users\u\AppData\Local\FortniteGame\GameUserSettings.ini";

    private static (Env e, GameIniOperation op, Func<bool> running, bool[] flag) IniOp()
    {
        var e = new Env(); var flag = new[] { false };
        e.Files.Files[Ini] = "[Section]\r\nsg.ShadowQuality=3\r\nbUseVSync=True\r\nOther=1\r\n";
        var op = new GameIniOperation(() => Ini, () => flag[0], ("sg.ShadowQuality", "0"), ("bUseVSync", "False"), ("Missing", "1")) { Id = "i", Name = "i", Description = "d", Effect = "e", Category = Categories.Gaming };
        return (e, op, () => flag[0], flag);
    }

    [Fact] public void GameIni_changes_only_existing_keys_and_keeps_a_backup()
    {
        var (e, op, _, _) = IniOp();
        var b = new BackupRecord(); op.Capture(e.Ctx, b); op.Apply(e.Ctx);
        string text = e.Files.Files[Ini];
        Assert.Contains("sg.ShadowQuality=0", text); Assert.Contains("bUseVSync=False", text); Assert.Contains("Other=1", text);
        Assert.DoesNotContain("Missing", text);
        Assert.Equal(OpState.Enabled, op.Detect(e.Ctx));
        op.Revert(e.Ctx, b);
        Assert.Contains("sg.ShadowQuality=3", e.Files.Files[Ini]);
    }

    [Fact] public void GameIni_refuses_to_run_while_the_game_is_open()
    {
        var (e, op, _, flag) = IniOp(); flag[0] = true;
        Assert.Throws<InvalidOperationException>(() => op.Apply(e.Ctx));
        Assert.DoesNotContain("sg.ShadowQuality=0", e.Files.Files[Ini]);
    }

    [Fact] public void GameIni_missing_file_is_not_applicable()
    {
        var (e, op, _, _) = IniOp(); e.Files.Files.Remove(Ini);
        Assert.False(op.CheckApplicable(e.Ctx).Ok);
    }
}
