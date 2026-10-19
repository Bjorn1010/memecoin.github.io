using Blatja.Core;
using Xunit;

namespace Blatja.Tests;

public class GameDetectorTests
{
    private const string Manifests = @"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests";

    [Fact] public void Nothing_installed_means_no_games_detected()
    {
        Assert.Empty(new GameDetector(new Env().Ctx, appData: @"C:\Users\u\AppData\Roaming").Detect());
    }

    [Fact] public void Fortnite_is_detected_from_the_epic_manifest_with_its_executable()
    {
        var e = new Env();
        const string loc = @"D:\Epic Games\Fortnite";
        e.Files.Files[Manifests + @"\A.item"] = $$"""{"AppName":"Fortnite","DisplayName":"Fortnite","InstallLocation":"{{loc.Replace("\\", "\\\\")}}","AppCategories":["public","games"]}""";
        e.Files.Files[loc + @"\FortniteGame\Binaries\Win64\FortniteClient-Win64-Shipping.exe"] = "";
        var g = new GameDetector(e.Ctx).Find("fortnite");
        Assert.NotNull(g); Assert.EndsWith("FortniteClient-Win64-Shipping.exe", g!.ExePath);
    }

    [Fact] public void Incomplete_epic_install_and_non_game_items_are_ignored()
    {
        var e = new Env();
        e.Files.Files[Manifests + @"\A.item"] = """{"AppName":"Fortnite","DisplayName":"Fortnite","InstallLocation":"D:\\F","bIsIncompleteInstall":true,"AppCategories":["games"]}""";
        e.Files.Files[Manifests + @"\B.item"] = """{"AppName":"UE","DisplayName":"Unreal Engine","InstallLocation":"D:\\UE","AppCategories":["applications"]}""";
        Assert.Empty(new GameDetector(e.Ctx).Detect());
    }

    [Fact] public void A_corrupted_manifest_does_not_hide_other_games()
    {
        var e = new Env();
        e.Files.Files[Manifests + @"\bad.item"] = "{ pas du json";
        e.Files.Files[Manifests + @"\ok.item"] = """{"AppName":"Fortnite","DisplayName":"Fortnite","InstallLocation":"D:\\F","AppCategories":["games"]}""";
        Assert.Single(new GameDetector(e.Ctx).Detect());
    }

    [Fact] public void Steam_games_are_found_in_every_library_and_known_ones_are_labelled()
    {
        var e = new Env();
        e.Reg.Seed(@"HKCU\Software\Valve\Steam", "SteamPath", RegValue.Str("c:/program files (x86)/steam"));
        e.Files.Files[@"c:\program files (x86)\steam\steamapps\libraryfolders.vdf"] = "\"libraryfolders\"\n{\n\t\"0\"\n\t{\n\t\t\"path\"\t\t\"D:\\\\SteamLibrary\"\n\t}\n}";
        e.Files.Files[@"D:\SteamLibrary\steamapps\appmanifest_730.acf"] = "\"AppState\"\n{\n\t\"appid\"\t\t\"730\"\n\t\"name\"\t\t\"Counter-Strike 2\"\n\t\"installdir\"\t\t\"Counter-Strike Global Offensive\"\n}";
        e.Files.Files[@"D:\SteamLibrary\steamapps\appmanifest_228980.acf"] = "\"AppState\"\n{\n\t\"appid\"\t\t\"228980\"\n\t\"name\"\t\t\"Steamworks Common Redistributables\"\n\t\"installdir\"\t\t\"Steamworks Shared\"\n}";
        e.Files.Files[@"D:\SteamLibrary\steamapps\appmanifest_440.acf"] = "\"AppState\"\n{\n\t\"appid\"\t\t\"440\"\n\t\"name\"\t\t\"Team Fortress 2\"\n\t\"installdir\"\t\t\"Team Fortress 2\"\n}";
        var games = new GameDetector(e.Ctx).Detect();
        Assert.Contains(games, g => g.Key == "cs2" && g.Known);
        Assert.Contains(games, g => g.Name == "Team Fortress 2" && !g.Known);
        Assert.DoesNotContain(games, g => g.Name.Contains("Steamworks"));
    }

    [Fact] public void Riot_games_are_detected_from_their_uninstall_entries()
    {
        var e = new Env();
        e.Reg.Seed(@"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Riot Game valorant.live", "InstallLocation", RegValue.Str(@"C:\Riot Games\VALORANT"));
        var games = new GameDetector(e.Ctx).Detect();
        Assert.Single(games); Assert.Equal("valorant", games[0].Key);
    }

    [Fact] public void Known_games_are_listed_before_other_games()
    {
        var e = new Env();
        e.Files.Files[Manifests + @"\z.item"] = """{"AppName":"abc","DisplayName":"A Game","InstallLocation":"D:\\A","AppCategories":["games"]}""";
        e.Files.Files[Manifests + @"\f.item"] = """{"AppName":"Fortnite","DisplayName":"Fortnite","InstallLocation":"D:\\F","AppCategories":["games"]}""";
        Assert.True(new GameDetector(e.Ctx).Detect()[0].Known);
    }
}

public class StartupManagerTests
{
    private const string Run = @"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";

    [Fact] public void Entries_are_listed_with_their_real_enabled_state()
    {
        var e = new Env();
        e.Reg.Seed(Run, "Discord", RegValue.Str(@"C:\Discord\Update.exe")); e.Reg.Seed(Run, "Steam", RegValue.Str(@"C:\Steam\steam.exe"));
        e.Reg.Seed(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", "Steam", RegValue.Bin(new byte[] { 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }));
        var list = new StartupManager(e.Ctx).List();
        Assert.True(list.Single(x => x.Name == "Discord").Enabled);
        Assert.False(list.Single(x => x.Name == "Steam").Enabled);
    }

    [Fact] public void Disable_then_enable_is_verified_and_reversible()
    {
        var e = new Env(); e.Reg.Seed(Run, "Discord", RegValue.Str("x"));
        var m = new StartupManager(e.Ctx); var entry = m.List().Single();
        m.SetEnabled(entry, false); Assert.False(m.List().Single().Enabled);
        m.SetEnabled(entry, true); Assert.True(m.List().Single().Enabled);
        Assert.NotNull(e.Reg.Get(Run, "Discord"));   // l'entrée d'origine n'est jamais supprimée
    }

    [Fact] public void Machine_wide_entries_need_admin_rights()
    {
        var e = new Env(); e.Info.IsAdmin = false;
        e.Reg.Seed(@"HKLM\Software\Microsoft\Windows\CurrentVersion\Run", "Driver", RegValue.Str("x"));
        var m = new StartupManager(e.Ctx);
        Assert.Throws<UnauthorizedAccessException>(() => m.SetEnabled(m.List().Single(), false));
    }

    [Fact] public void Startup_folder_items_are_listed_but_desktop_ini_is_ignored()
    {
        var e = new Env(); const string f = @"C:\Users\u\Startup";
        e.Files.Files[f + @"\App.lnk"] = ""; e.Files.Files[f + @"\desktop.ini"] = "";
        Assert.Equal(new[] { "App.lnk" }, new StartupManager(e.Ctx, f).List().Select(x => x.Name));
    }
}

public class DiagnosticRuleTests
{
    private static DiagnosticInput Input(double? diskUsed = null, double? diskTotal = null, double? ram = null, int? startup = null, double? gpuTemp = null,
        bool admin = true, IReadOnlyList<ProcessUsage>? procs = null, IReadOnlyList<OpStatus>? ops = null) =>
        new(diskUsed, diskTotal, ram, null, procs ?? Array.Empty<ProcessUsage>(), startup, gpuTemp, ops ?? Array.Empty<OpStatus>(), admin);

    [Fact] public void No_data_produces_no_finding() => Assert.Empty(Input().Evaluate());

    [Fact] public void Healthy_system_produces_no_problem()
    {
        var f = Input(100, 500, 40, 5, 60).Evaluate();
        Assert.DoesNotContain(f, x => x.Kind != FindingKind.Info);
    }

    [Fact] public void Nearly_full_disk_is_reported_as_a_problem_with_evidence()
    {
        var f = Input(diskUsed: 470, diskTotal: 500).Evaluate().Single();
        Assert.Equal(FindingKind.Problem, f.Kind); Assert.Contains("30 Go libres", f.Evidence);
    }

    [Fact] public void Saturated_memory_is_a_problem_and_high_memory_is_only_an_improvement()
    {
        Assert.Equal(FindingKind.Problem, Input(ram: 93).Evaluate().Single().Kind);
        Assert.Equal(FindingKind.Improvement, Input(ram: 82).Evaluate().Single().Kind);
        Assert.Empty(Input(ram: 60).Evaluate());
    }

    [Fact] public void Hot_gpu_is_reported_only_above_the_thresholds()
    {
        Assert.Empty(Input(gpuTemp: 70).Evaluate());
        Assert.Equal(FindingKind.Problem, Input(gpuTemp: 88).Evaluate().Single().Kind);
    }

    [Fact] public void Heavy_process_is_informational_not_a_problem()
    {
        var f = Input(procs: new[] { new ProcessUsage("chrome", 3072, null), new ProcessUsage("small", 100, null) }).Evaluate().Single();
        Assert.Equal(FindingKind.Info, f.Kind); Assert.Contains("chrome", f.Title);
    }

    [Fact] public void Missing_admin_rights_are_reported_as_info()
    {
        Assert.Equal(FindingKind.Info, Input(admin: false).Evaluate().Single().Kind);
    }

    [Fact] public void Pending_recommended_operations_are_suggested_but_applied_or_optional_ones_are_not()
    {
        var env = new Env();
        var cat = OperationCatalog.Build(new GameDetector(env.Ctx), "", _ => false);
        Operation Get(string id) => cat.Single(o => o.Id == id);
        var ops = new[]
        {
            new OpStatus(Get("power"), OpState.Disabled, null),      // recommandée, impact moyen : proposée
            new OpStatus(Get("hags"), OpState.Enabled, null),        // déjà appliquée : non proposée
            new OpStatus(Get("svcxbox"), OpState.Disabled, null),    // non recommandée : non proposée
            new OpStatus(Get("tips"), OpState.Disabled, null),       // faible impact : regroupée
            new OpStatus(Get("fngpu"), OpState.NotApplicable, null), // non applicable : ignorée
        };
        var f = Input(ops: ops).Evaluate();
        Assert.Contains(f, x => x.OpIds.SequenceEqual(new[] { "power" }));
        Assert.Contains(f, x => x.OpIds.Contains("tips"));
        Assert.DoesNotContain(f, x => x.OpIds.Contains("hags") || x.OpIds.Contains("svcxbox") || x.OpIds.Contains("fngpu"));
    }

    [Fact] public void Detection_errors_are_reported_without_inventing_a_problem()
    {
        var env = new Env(); var cat = OperationCatalog.Build(new GameDetector(env.Ctx), "", _ => false);
        var f = Input(ops: new[] { new OpStatus(cat[0], OpState.Error, "accès refusé") }).Evaluate().Single();
        Assert.Equal(FindingKind.Info, f.Kind); Assert.Contains("accès refusé", f.Evidence);
    }

    [Fact] public void Findings_are_ordered_by_priority()
    {
        var kinds = Input(diskUsed: 480, diskTotal: 500, ram: 85, admin: false).Evaluate().Select(x => x.Kind).ToList();
        Assert.Equal(kinds.OrderBy(k => k).ToList(), kinds);
    }
}

internal static class InputExt
{
    public static IReadOnlyList<Finding> Evaluate(this DiagnosticInput i) => DiagnosticRules.Evaluate(i);
}

public class StorageAndMeasureTests
{
    private static string Tmp() => Path.Combine(Path.GetTempPath(), "blatja-test-" + Guid.NewGuid().ToString("N"));

    [Fact] public void Backup_roundtrip_keeps_every_value_kind()
    {
        var dir = Tmp(); var store = new JsonBackupStore(dir);
        var rec = new BackupRecord { OpId = "x" };
        rec.Entries.Add(BackupEntry.From("HKCU\\a", "d", RegValue.DWord(-1)));
        rec.Entries.Add(BackupEntry.From("HKCU\\a", "s", RegValue.Str("héllo")));
        rec.Entries.Add(BackupEntry.From("HKCU\\a", "b", RegValue.Bin(new byte[] { 1, 2, 255 })));
        rec.Entries.Add(BackupEntry.From("HKCU\\a", "absent", null));
        rec.Extra["k"] = "v"; store.Save(rec);
        var loaded = new JsonBackupStore(dir).Load("x")!;
        Assert.True(loaded.Entries[0].ToValue()!.Value.SameAs(RegValue.DWord(-1)));
        Assert.True(loaded.Entries[1].ToValue()!.Value.SameAs(RegValue.Str("héllo")));
        Assert.True(loaded.Entries[2].ToValue()!.Value.SameAs(RegValue.Bin(new byte[] { 1, 2, 255 })));
        Assert.Null(loaded.Entries[3].ToValue()); Assert.Equal("v", loaded.Extra["k"]);
        Directory.Delete(dir, true);
    }

    [Fact] public void Corrupted_backup_file_is_ignored_instead_of_crashing()
    {
        var dir = Tmp(); Directory.CreateDirectory(dir); File.WriteAllText(Path.Combine(dir, "x.json"), "{ cassé");
        var store = new JsonBackupStore(dir);
        Assert.Null(store.Load("x")); Assert.Empty(store.All());
        Directory.Delete(dir, true);
    }

    [Fact] public void Journal_is_append_only_newest_first_and_survives_corrupted_lines()
    {
        var dir = Tmp(); var file = Path.Combine(dir, "j.jsonl"); var j = new FileJournal(file);
        j.Append(new JournalEntry(DateTime.Now, "a", "A", "Apply", JournalOutcome.Succeeded, "ok"));
        File.AppendAllText(file, "ligne corrompue\n");
        j.Append(new JournalEntry(DateTime.Now, "b", "B", "Revert", JournalOutcome.Failed, "ko"));
        var r = j.Recent();
        Assert.Equal(new[] { "b", "a" }, r.Select(x => x.OpId));
        Directory.Delete(dir, true);
    }

    [Fact] public void Settings_fall_back_to_defaults_when_the_file_is_missing_or_invalid()
    {
        var dir = Tmp(); Directory.CreateDirectory(dir); var p = Path.Combine(dir, "s.json");
        Assert.Equal(2, AppSettings.Load(p).RefreshSeconds);
        File.WriteAllText(p, "{\"RefreshSeconds\": 7}"); Assert.Equal(2, AppSettings.Load(p).RefreshSeconds);
        new AppSettings { RefreshSeconds = 5 }.Save(p); Assert.Equal(5, AppSettings.Load(p).RefreshSeconds);
        Directory.Delete(dir, true);
    }

    [Fact] public void Timeseries_keeps_gaps_as_nan_and_trims_old_points()
    {
        var s = new TimeSeries(TimeSpan.FromMinutes(1)); var t0 = DateTime.Now;
        s.Add(t0, 10); s.Add(t0.AddSeconds(30), null); s.Add(t0.AddSeconds(90), 20);
        var w = s.Window(t0.AddSeconds(90), TimeSpan.FromMinutes(1));
        Assert.Equal(2, w.Count); Assert.True(double.IsNaN(w[0].V)); Assert.Equal(20, s.Last);
    }

    [Fact] public void Timeseries_without_any_value_reports_no_data()
    {
        var s = new TimeSeries(TimeSpan.FromMinutes(5)); s.Add(DateTime.Now, null);
        Assert.False(s.HasData(DateTime.Now, TimeSpan.FromMinutes(1))); Assert.Null(s.Last);
    }

    [Fact] public void Ping_statistics_compute_loss_and_jitter()
    {
        var p = PingStats.From(new long?[] { 10, 20, null, 30 });
        Assert.Equal(4, p.Sent); Assert.Equal(3, p.Received); Assert.Equal(25, p.LossPercent, 3);
        Assert.Equal(20, p.AvgMs!.Value, 3); Assert.Equal(10, p.MinMs); Assert.Equal(30, p.MaxMs); Assert.Equal(10, p.JitterMs!.Value, 3);
    }

    [Fact] public void Ping_with_all_packets_lost_has_no_invented_numbers()
    {
        var p = PingStats.From(new long?[] { null, null });
        Assert.Null(p.AvgMs); Assert.Null(p.JitterMs); Assert.Equal(100, p.LossPercent);
    }

    [Fact] public void Snapshot_comparison_reports_unavailable_instead_of_zero()
    {
        var before = new SystemSnapshot(DateTime.Now, 30, 50, 200, 10, null, 40);
        var after = new SystemSnapshot(DateTime.Now, 20, 45, 190, 8, null, 40);
        var rows = SnapshotComparison.Compare(before, after);
        Assert.Contains(rows, r => r.Label == "Utilisation CPU" && r.Delta.StartsWith("-10"));
        Assert.Contains(rows, r => r.Label == "Latence réseau moyenne" && r.Delta == "Indisponible");
        Assert.All(rows, r => Assert.False(string.IsNullOrEmpty(r.Note) && r.Label.Contains("CPU")));
    }
}

public class OpViewModelTests
{
    private static OpVm Vm(OpState state, bool recommended = true)
    {
        var op = CustomOp.Make("x", _ => state);
        var vm = new OpVm(new CustomOp { Id = "x", Name = "x", Description = "d", Effect = "e", Category = Categories.Gaming, Recommended = recommended });
        vm.Update(new OpStatus(op, state, state == OpState.NotApplicable ? "raison" : null));
        return vm;
    }

    [Fact] public void State_comes_from_detection_never_from_selection()
    {
        var vm = Vm(OpState.Disabled); vm.IsSelected = true;
        Assert.Equal(OpState.Disabled, vm.State); Assert.Equal("Désactivée", vm.StateText);
    }

    [Theory]
    [InlineData(OpState.Disabled, true, false, "Appliquer")]
    [InlineData(OpState.Enabled, false, true, "Restaurer")]
    [InlineData(OpState.NotApplicable, false, false, "Appliquer")]
    [InlineData(OpState.Unknown, false, false, "Appliquer")]
    [InlineData(OpState.Error, false, false, "Appliquer")]
    public void Commands_are_only_offered_when_they_make_sense(OpState s, bool canApply, bool canRevert, string text)
    {
        var vm = Vm(s);
        Assert.Equal(canApply, vm.CanApply); Assert.Equal(canRevert, vm.CanRevert); Assert.Equal(text, vm.ActionText);
    }

    [Fact] public void A_busy_operation_cannot_be_triggered_twice()
    {
        var vm = Vm(OpState.Disabled); vm.Busy = true;
        Assert.False(vm.CanApply); Assert.False(vm.CanRevert);
    }

    [Fact] public void Selection_is_cleared_when_the_operation_becomes_applied_or_not_applicable()
    {
        var vm = Vm(OpState.Disabled); vm.IsSelected = true;
        vm.Update(new OpStatus(vm.Op, OpState.Enabled, null)); Assert.False(vm.IsSelected);
        vm.IsSelected = true; vm.Update(new OpStatus(vm.Op, OpState.NotApplicable, "x")); Assert.False(vm.IsSelected);
    }

    [Fact] public void Not_applicable_operation_keeps_its_reason_and_unknown_or_error_states_are_flagged()
    {
        Assert.Equal("raison", Vm(OpState.NotApplicable).Detail);
        Assert.Equal("danger", Vm(OpState.Error).StateKind); Assert.Equal("warning", Vm(OpState.Unknown).StateKind);
        Assert.Equal("success", Vm(OpState.Enabled).StateKind); Assert.Equal("neutral", Vm(OpState.Disabled).StateKind);
    }

    [Fact] public void Property_changes_are_notified_to_the_view()
    {
        var vm = Vm(OpState.Disabled); var raised = new List<string>();
        vm.PropertyChanged += (_, e) => raised.Add(e.PropertyName!);
        vm.Update(new OpStatus(vm.Op, OpState.Enabled, null));
        Assert.Contains("State", raised); Assert.Contains("CanRevert", raised);
    }
}
