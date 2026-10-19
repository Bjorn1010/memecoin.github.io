using System.Text.Json;
using System.Windows;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace BlatjaTweaks;

public partial class MainWindow : Window
{
    private static readonly string StateFile = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks", "state.json");

    private readonly List<Tweak> _tweaks = Tweaks.Build();
    private readonly System.ComponentModel.ICollectionView _viewV;
    private GpuInfo _gpu = new("", "", null, null, null, null, null, null, null);
    private bool _busy;
    private string? _fnExe;

    public MainWindow()
    {
        InitializeComponent();

        var area = SystemParameters.WorkArea;
        Height = Math.Min(Height, area.Height - 24);
        Width = Math.Min(Width, area.Width - 24);
        Opacity = 0;
        Loaded += (_, _) => PlayIntro();

        Header.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        Brand.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        BtnMin.Click += (_, _) => WindowState = WindowState.Minimized;
        BtnClose.Click += (_, _) => Close();

        LoadState();
        _viewV = CollectionViewSource.GetDefaultView(_tweaks);
        TweakList.ItemsSource = _viewV;
        foreach (var t in _tweaks)
            t.PropertyChanged += (_, e) => { if (e.PropertyName == nameof(Tweak.Applied)) Dispatcher.Invoke(UpdateCount); };
        UpdateCount();

        // navigation
        NavDash.Checked += (_, _) => ShowPage("dash");
        NavSystem.Checked += (_, _) => ShowPage("SYSTÈME");
        NavInput.Checked += (_, _) => ShowPage("ENTRÉES & RÉSEAU");
        NavFn.Checked += (_, _) => ShowPage("FORTNITE");
        NavGpu.Checked += (_, _) => ShowPage("gpu");
        NavTools.Checked += (_, _) => ShowPage("tools");
        BtnOpenSystem.Click += (_, _) => NavSystem.IsChecked = true;
        BtnGoSystem.Click += (_, _) => NavSystem.IsChecked = true;
        BtnOpenInput.Click += (_, _) => NavInput.IsChecked = true;
        BtnOpenFn.Click += (_, _) => NavFn.IsChecked = true;

        BtnAll.Click += (_, _) => Visible().ForEach(t => t.IsOn = true);
        BtnNone.Click += (_, _) => Visible().ForEach(t => t.IsOn = false);
        BtnQuick.Click += async (_, _) => { _tweaks.ForEach(t => t.IsOn = true); await ApplyAsync(restoreAll: false); };
        BtnApply.Click += async (_, _) => await ApplyAsync(restoreAll: false);
        BtnRestore.Click += async (_, _) => await ApplyAsync(restoreAll: true);
        BtnClean.Click += async (_, _) => await RunAsync("Nettoyage", () => $"{Tweaks.CleanTemp()} Mo libérés");
        BtnGpuBoost.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Boost(_gpu)); await RefreshGpuAsync(); };
        BtnGpuReset.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Reset(_gpu)); await RefreshGpuAsync(); };

        ShowPage("dash");
        // page de départ optionnelle (utile pour les captures d'écran de développement)
        switch (Environment.GetEnvironmentVariable("BLATJA_PAGE"))
        {
            case "system": NavSystem.IsChecked = true; break;
            case "input": NavInput.IsChecked = true; break;
            case "fn": NavFn.IsChecked = true; break;
            case "gpu": NavGpu.IsChecked = true; break;
            case "tools": NavTools.IsChecked = true; break;
        }
        Loaded += async (_, _) =>
        {
            Log("Blatja Tweaks prêt. Chaque réglage est réversible.");
            await RefreshGpuAsync();
            await Task.Run(DetectFortnite);
        };
    }

    private List<Tweak> Visible() => _viewV.Cast<Tweak>().ToList();

    private void PlayIntro()
    {
        var ease = new CubicEase { EasingMode = EasingMode.EaseOut };
        var dur = TimeSpan.FromMilliseconds(380);
        BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, dur) { EasingFunction = ease });
        var sc = new DoubleAnimation(0.985, 1, dur) { EasingFunction = ease };
        RootScale.BeginAnimation(ScaleTransform.ScaleXProperty, sc);
        RootScale.BeginAnimation(ScaleTransform.ScaleYProperty, sc);
    }

    // ───────────── Navigation ─────────────
    private void ShowPage(string key)
    {
        if (PageDash is null) return;
        bool isTweaks = key is "SYSTÈME" or "ENTRÉES & RÉSEAU" or "FORTNITE";

        PageDash.Visibility = key == "dash" ? Visibility.Visible : Visibility.Collapsed;
        PageTweaks.Visibility = isTweaks ? Visibility.Visible : Visibility.Collapsed;
        PageGpu.Visibility = key == "gpu" ? Visibility.Visible : Visibility.Collapsed;
        PageTools.Visibility = key == "tools" ? Visibility.Visible : Visibility.Collapsed;
        TweakTools.Visibility = isTweaks ? Visibility.Visible : Visibility.Collapsed;
        ActionBar.Visibility = key == "tools" || key == "gpu" ? Visibility.Collapsed : Visibility.Visible;
        BtnApply.Visibility = isTweaks ? Visibility.Visible : Visibility.Collapsed;

        (PageTitle.Text, PageSub.Text) = key switch
        {
            "dash" => ("Tableau de bord", "État de ton PC et des optimisations"),
            "SYSTÈME" => ("Système", "Alimentation, planification, minuteur, effets visuels"),
            "ENTRÉES & RÉSEAU" => ("Entrées & réseau", "Souris et latence réseau"),
            "FORTNITE" => ("Fortnite", _fnExe ?? "Fortnite non détecté : lance-le une fois via Epic Games Launcher"),
            "gpu" => ("Carte graphique", "Puissance et fréquences"),
            _ => ("Outils", "Maintenance"),
        };

        if (isTweaks)
        {
            _viewV.Filter = o => ((Tweak)o).Category == key;
            _viewV.Refresh();
            PageTweaks.ScrollToTop();
        }
    }

    // ───────────── État persistant ─────────────
    private void LoadState()
    {
        try
        {
            var ids = JsonSerializer.Deserialize<HashSet<string>>(File.ReadAllText(StateFile)) ?? new();
            foreach (var t in _tweaks) t.Applied = t.IsOn = ids.Contains(t.Id);
        }
        catch { }
    }

    private void SaveState()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(StateFile)!);
            File.WriteAllText(StateFile, JsonSerializer.Serialize(_tweaks.Where(t => t.Applied).Select(t => t.Id)));
        }
        catch { }
    }

    // ───────────── Actions ─────────────
    private async Task ApplyAsync(bool restoreAll)
    {
        if (_busy) return;
        if (restoreAll) _tweaks.ForEach(t => t.IsOn = false);
        var todo = _tweaks.Where(t => t.IsOn != t.Applied).ToList();
        if (todo.Count == 0) { Log("Rien à faire : les réglages sont déjà à jour."); return; }

        SetBusy(true);
        bool reboot = false;
        await Task.Run(() =>
        {
            if (todo.Any(t => t.IsOn)) CreateRestorePoint();
            for (int i = 0; i < todo.Count; i++)
            {
                var t = todo[i];
                try
                {
                    if (t.IsOn) { t.Apply(); t.Applied = true; LogUi($"✔ Appliqué : {t.Name}"); }
                    else { t.Revert(); t.Applied = false; LogUi($"↩ Restauré : {t.Name}"); }
                    reboot |= t.NeedsReboot;
                }
                catch (Exception ex)
                {
                    Dispatcher.Invoke(() => t.IsOn = t.Applied);
                    LogUi($"✘ {t.Name} → {ex.Message}");
                }
                int done = i + 1;
                Dispatcher.Invoke(() => { Progress.Value = done * 100.0 / todo.Count; ProgressLabel.Text = $"{done} / {todo.Count} réglages traités"; });
            }
            SaveState();
        });
        Log(reboot ? "Terminé. Redémarre le PC pour activer tous les réglages." : "Terminé.");
        SetBusy(false);
    }

    private async Task RunAsync(string label, Func<string> work)
    {
        if (_busy) return;
        SetBusy(true);
        try { Log($"{label} : {await Task.Run(work)}"); }
        catch (Exception ex) { Log($"✘ {label} : {ex.Message}"); }
        SetBusy(false);
    }

    private void CreateRestorePoint()
    {
        LogUi("Création d'un point de restauration…");
        try
        {
            var r = Sh.Run("powershell", "-NoProfile -Command \"Checkpoint-Computer -Description 'Blatja Tweaks' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop\"", 90000);
            LogUi(r.Code == 0 ? "Point de restauration créé." : "Point de restauration indisponible (protection système désactivée ?) — on continue.");
        }
        catch { LogUi("Point de restauration indisponible — on continue."); }
    }

    // ───────────── Détection ─────────────
    private Brush Res(string key) => (Brush)FindResource(key);

    private async Task RefreshGpuAsync()
    {
        _gpu = await Task.Run(Gpu.Query);
        GpuName.Text = DashGpu.Text = _gpu.Name;
        GpuDriver.Text = _gpu.Driver is null ? "" : $"Pilote {_gpu.Driver}";
        TilePower.Text = DashPower.Text = _gpu.PowerLimit is double pl ? $"{pl:0} W" : "—";
        TileClock.Text = _gpu.MaxClock is int mc ? $"{mc} MHz" : "—";
        TileTemp.Text = DashTemp.Text = _gpu.Temp is int tp ? $"{tp} °C" : "—";
        if (_gpu.Temp is int t2)
            TileTemp.Foreground = DashTemp.Foreground = Res(t2 < 83 ? "Text" : "Warn");
        if (_gpu.PowerLimit is double cur && _gpu.PowerMax is double max && max > 0)
        {
            BarPower.Value = cur / max * 100;
            BarPowerLabel.Text = $"{cur:0} / {max:0} W";
        }
        else { BarPower.Value = 0; BarPowerLabel.Text = ""; }

        bool nv = _gpu.SmiPath is not null;
        BtnGpuBoost.IsEnabled = BtnGpuReset.IsEnabled = nv;
        GpuStatus.Text = nv ? "" :
            _gpu.Vendor == "AMD" ? "AMD : l'overclock se règle dans AMD Adrenalin (Performances → Réglages). Les réglages système restent actifs." :
            _gpu.Vendor == "NVIDIA" ? "Installe le pilote NVIDIA officiel pour activer le boost GPU." :
            "Boost GPU disponible uniquement pour les cartes NVIDIA.";
    }

    private void DetectFortnite()
    {
        string? exe = Fortnite.FindExe();
        Dispatcher.Invoke(() =>
        {
            _fnExe = exe;
            FnStatus.Text = exe is null ? "non détecté" : "installé";
            FnStatus.Foreground = Res(exe is null ? "Warn" : "Text");
            FnPath.Text = exe ?? "Installe Fortnite via Epic Games Launcher pour activer les réglages Fortnite.";
            if (NavFn.IsChecked == true) ShowPage("FORTNITE");
        });
    }

    // ───────────── Utilitaires UI ─────────────
    private void UpdateCount()
    {
        int n = _tweaks.Count(t => t.Applied);
        ActiveCount.Text = $"{n} / {_tweaks.Count}";
        HeroCount.Text = n.ToString();
        HeroCountLabel.Text = $"sur {_tweaks.Count} actifs";
        HeroTitle.Text = n == 0 ? "Aucun réglage appliqué" : n == _tweaks.Count ? "Configuration complète" : $"{n} réglage{(n > 1 ? "s" : "")} appliqué{(n > 1 ? "s" : "")}";
        ActiveBar.Value = _tweaks.Count == 0 ? 0 : n * 100.0 / _tweaks.Count;
        foreach (var (cat, box) in new[] { ("SYSTÈME", CntSystem), ("ENTRÉES & RÉSEAU", CntInput), ("FORTNITE", CntFn) })
        {
            int tot = _tweaks.Count(t => t.Category == cat), on = _tweaks.Count(t => t.Category == cat && t.Applied);
            box.Text = $"{on} / {tot}";
        }
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        BtnApply.IsEnabled = BtnRestore.IsEnabled = BtnClean.IsEnabled = BtnQuick.IsEnabled = !busy;
        if (!busy) { Progress.Value = 0; ProgressLabel.Text = "Prêt"; }
        else ProgressLabel.Text = "En cours…";
    }

    private void Log(string msg)
    {
        LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {msg}\n");
        LogBox.ScrollToEnd();
    }

    private void LogUi(string msg) => Dispatcher.Invoke(() => Log(msg));
}
