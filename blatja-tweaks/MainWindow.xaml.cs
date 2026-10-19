using System.Diagnostics;
using System.Text.Json;
using System.Windows;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;

namespace BlatjaTweaks;

public partial class MainWindow : Window
{
    private static readonly string StateFile = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks", "state.json");

    // circonférence de l'anneau (diamètre 150, épaisseur 10) exprimée en épaisseurs de trait
    private const double RingLength = Math.PI * (150 - 10) / 10;

    private readonly List<Tweak> _tweaks = Tweaks.Build();
    private readonly System.ComponentModel.ICollectionView _view;
    private GpuInfo _gpu = new("", "", null, null, null, null, null, null, null);
    private bool _busy;
    private bool _safe;            // point de restauration validé (ou ignoré explicitement)
    private string? _fnExe;
    private double _score;         // 0..1 affiché par l'anneau

    public MainWindow()
    {
        InitializeComponent();

        var area = SystemParameters.WorkArea;
        Height = Math.Min(Height, area.Height - 20);
        Width = Math.Min(Width, area.Width - 20);

        Header.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        Brand.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        BtnMin.Click += (_, _) => WindowState = WindowState.Minimized;
        BtnClose.Click += (_, _) => Close();

        LoadState();
        _view = CollectionViewSource.GetDefaultView(_tweaks);
        TweakList.ItemsSource = _view;
        foreach (var t in _tweaks)
            t.PropertyChanged += (_, e) => { if (e.PropertyName == nameof(Tweak.Applied)) Dispatcher.Invoke(UpdateCount); };
        UpdateCount(animate: false);
        HeroText.Text = $"Active {_tweaks.Count(t => t.Recommended)} réglages d'un coup. Chacun peut être annulé individuellement.";

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

        BtnAll.Click += (_, _) => Visible().ForEach(t => t.IsOn = t.Recommended);
        BtnNone.Click += (_, _) => Visible().ForEach(t => t.IsOn = false);
        BtnQuick.Click += async (_, _) => { _tweaks.ForEach(t => t.IsOn = t.Recommended); await ApplyAsync(restoreAll: false); };
        BtnApply.Click += async (_, _) => await ApplyAsync(restoreAll: false);
        BtnRestore.Click += async (_, _) => await ApplyAsync(restoreAll: true);
        BtnClean.Click += async (_, _) => await RunAsync("Nettoyage", () => $"{Tweaks.CleanTemp()} Mo libérés");
        BtnActivation.Click += (_, _) => Process.Start(new ProcessStartInfo("ms-settings:activation") { UseShellExecute = true });
        BtnGpuBoost.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Boost(_gpu)); await RefreshGpuAsync(); };
        BtnGpuReset.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Reset(_gpu)); await RefreshGpuAsync(); };

        // point de restauration obligatoire
        GateBtn.Click += async (_, _) => await CreateRestoreAsync();
        GateSkip.Click += (_, _) =>
        {
            if (MessageBox.Show("Sans point de restauration, tu ne pourras annuler les réglages qu'avec le bouton « Tout restaurer » de l'application.\n\nContinuer quand même ?",
                    "Blatja Tweaks", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes)
            { _safe = true; Log("Point de restauration ignoré par l'utilisateur."); CloseGate(); }
        };
        if (Restore.Recent() is DateTime when)
        {
            GateStatus.Text = $"Un point de restauration existe déjà ({when:dd/MM à HH:mm}).";
            GateBtn.Content = "Continuer";
            GateBtn.Tag = "ok";
        }

        ShowPage("dash", animate: false);
        switch (Environment.GetEnvironmentVariable("BLATJA_PAGE"))   // utile pour les captures de développement
        {
            case "system": NavSystem.IsChecked = true; break;
            case "input": NavInput.IsChecked = true; break;
            case "fn": NavFn.IsChecked = true; break;
            case "gpu": NavGpu.IsChecked = true; break;
            case "tools": NavTools.IsChecked = true; break;
        }
        if (Environment.GetEnvironmentVariable("BLATJA_NOGATE") == "1") { _safe = true; Gate.Visibility = Visibility.Collapsed; }

        Loaded += async (_, _) =>
        {
            Root.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(420)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } });
            Log("Blatja Tweaks prêt. Chaque réglage est réversible.");
            await RefreshGpuAsync();
            await Task.Run(DetectFortnite);
        };
    }

    private List<Tweak> Visible() => _view.Cast<Tweak>().ToList();

    // ───────────── Point de restauration ─────────────
    private async Task CreateRestoreAsync()
    {
        if (GateBtn.Tag as string == "ok") { _safe = true; CloseGate(); return; }

        GateBtn.IsEnabled = false;
        GateSkip.Visibility = Visibility.Collapsed;
        GateStatus.Foreground = Res("Muted");
        GateStatus.Text = "Création en cours… (jusqu'à une minute)";
        var (ok, msg) = await Task.Run(Restore.Create);
        if (ok)
        {
            _safe = true;
            GateStatus.Foreground = Res("Good");
            GateStatus.Text = "✔ " + msg;
            Log(msg);
            await Task.Delay(650);
            CloseGate();
        }
        else
        {
            GateStatus.Foreground = Res("Warn");
            GateStatus.Text = "Échec : " + msg;
            GateBtn.Content = "Réessayer";
            GateBtn.IsEnabled = true;
            GateSkip.Visibility = Visibility.Visible;
        }
    }

    private void CloseGate()
    {
        var fade = new DoubleAnimation(1, 0, TimeSpan.FromMilliseconds(280));
        fade.Completed += (_, _) => Gate.Visibility = Visibility.Collapsed;
        Gate.BeginAnimation(OpacityProperty, fade);
    }

    // ───────────── Navigation ─────────────
    private void ShowPage(string key, bool animate = true)
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
            "SYSTÈME" => ("Système", "Alimentation, planification, minuteur, tâches de fond"),
            "ENTRÉES & RÉSEAU" => ("Entrées & réseau", "Souris et latence réseau"),
            "FORTNITE" => ("Fortnite", _fnExe ?? "Fortnite non détecté : lance-le une fois via Epic Games Launcher"),
            "gpu" => ("Carte graphique", "Puissance et fréquences"),
            _ => ("Outils", "Maintenance et activation"),
        };

        if (isTweaks)
        {
            _view.Filter = o => ((Tweak)o).Category == key;
            _view.Refresh();
            PageTweaks.ScrollToTop();
        }

        if (animate)
        {
            var ease = new CubicEase { EasingMode = EasingMode.EaseOut };
            PageHost.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(240)));
            PageSlide.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(14, 0, TimeSpan.FromMilliseconds(300)) { EasingFunction = ease });
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
        if (!_safe) { Gate.Visibility = Visibility.Visible; Gate.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(200))); return; }

        if (restoreAll) _tweaks.ForEach(t => t.IsOn = false);
        var todo = _tweaks.Where(t => t.IsOn != t.Applied).ToList();
        if (todo.Count == 0) { Log("Rien à faire : les réglages sont déjà à jour."); return; }

        SetBusy(true);
        bool reboot = false;
        await Task.Run(() =>
        {
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
                Dispatcher.Invoke(() =>
                {
                    Tween(Progress.Value, done * 100.0 / todo.Count, 260, v => Progress.Value = v);
                    ProgressLabel.Text = $"{done} / {todo.Count} réglages traités";
                });
                Thread.Sleep(120);   // laisse l'animation respirer
            }
            SaveState();
        });
        Log(reboot ? "Terminé. Redémarre le PC pour activer tous les réglages." : "Terminé.");
        await Task.Delay(500);
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
            Tween(BarPower.Value, cur / max * 100, 600, v => BarPower.Value = v);
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
            if (NavFn.IsChecked == true) ShowPage("FORTNITE", animate: false);
        });
    }

    // ───────────── Utilitaires UI ─────────────
    /// <summary>Interpolation douce (ease-out cubique) pilotée par minuteur, pour les valeurs sans propriété animable.</summary>
    private void Tween(double from, double to, int ms, Action<double> set)
    {
        var sw = Stopwatch.StartNew();
        var timer = new DispatcherTimer(DispatcherPriority.Render) { Interval = TimeSpan.FromMilliseconds(8) };
        timer.Tick += (_, _) =>
        {
            double p = Math.Min(1, sw.ElapsedMilliseconds / (double)ms);
            double e = 1 - Math.Pow(1 - p, 3);
            set(from + (to - from) * e);
            if (p >= 1) timer.Stop();
        };
        timer.Start();
    }

    private void UpdateCount(bool animate = true)
    {
        int n = _tweaks.Count(t => t.Applied);
        int total = _tweaks.Count;
        ActiveCount.Text = $"{n} / {total}";
        Tween(ActiveBar.Value, total == 0 ? 0 : n * 100.0 / total, animate ? 500 : 1, v => ActiveBar.Value = v);

        double target = total == 0 ? 0 : (double)n / total;
        double start = _score;
        Tween(start, target, animate ? 700 : 1, v =>
        {
            _score = v;
            HeroCount.Text = $"{Math.Round(v * 100)}%";
            Ring.Opacity = v < 0.005 ? 0 : 1;
            Ring.StrokeDashArray = new DoubleCollection { Math.Max(0.001, v * RingLength), 100 };
        });

        HeroTitle.Text = n == 0 ? "Aucun réglage appliqué" : n == total ? "Configuration complète" : $"{n} réglage{(n > 1 ? "s" : "")} appliqué{(n > 1 ? "s" : "")}";
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
        if (!busy) { Tween(Progress.Value, 0, 300, v => Progress.Value = v); ProgressLabel.Text = "Prêt"; }
        else ProgressLabel.Text = "En cours…";
    }

    private void Log(string msg)
    {
        LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {msg}\n");
        LogBox.ScrollToEnd();
    }

    private void LogUi(string msg) => Dispatcher.Invoke(() => Log(msg));
}
