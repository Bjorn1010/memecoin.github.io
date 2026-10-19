using System.Diagnostics;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
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

    private readonly List<Tweak> _tweaks = Tweaks.Build();
    private readonly List<Fix> _fixes = Fixes.Build();
    private readonly Metrics _m = new();
    private readonly System.ComponentModel.ICollectionView _view;
    private readonly Stopwatch _sinceSample = Stopwatch.StartNew();
    private readonly bool _demo = Environment.GetEnvironmentVariable("BLATJA_DEMO") == "1";
    private readonly DispatcherTimer _toastTimer = new() { Interval = TimeSpan.FromSeconds(3.4) };

    private GpuInfo _gpu = new("", "", null, null, null, null, null, null, null);
    private GpuLive? _gpuLive;
    private bool _polling;
    private bool _busy;
    private bool _safe;            // point de restauration validé (ou ignoré explicitement)
    private string? _fnExe;
    private string _page = "dash";

    private static readonly (string Key, string Label, string Icon, string Title, string Sub)[] Cats =
    {
        ("GÉNÉRAL",  "Général",           Icons.Bolt,    "Général",           "Alimentation, Mode Jeu, capture, effets visuels."),
        ("DÉBLOAT",  "Débloat",           Icons.Trash,   "Débloat",           "Retire de Windows ce qui ralentit et distrait."),
        ("RÉSEAU",   "Réseau & souris",   Icons.Wifi,    "Réseau & souris",   "Latence réseau et précision de la souris."),
        ("AVANCÉ",   "Avancé",            Icons.Speed,   "Avancé",            "Planification GPU, minuteur, priorités. Pour utilisateurs avertis."),
        ("SERVICES", "Services",          Icons.Wrench,  "Services",          "Désactive les services Windows dont tu n'as pas besoin."),
        ("JEUX",     "Profils de jeu",    Icons.Gamepad, "Profils de jeu",    ""),
        ("APPS",     "Optimiseur d'apps", Icons.Memory,  "Optimiseur d'apps", "Priorités CPU des applications en arrière-plan."),
    };
    private readonly Dictionary<string, RadioButton> _navs = new();

    private static readonly (string Title, string Body)[] BiosTips =
    {
        ("Profil mémoire XMP / EXPO", "Sans lui, ta RAM tourne à une fréquence de base bien plus basse que celle vendue. Active-le dans le BIOS (onglet Mémoire ou Overclocking) : c'est souvent le plus gros gain gratuit."),
        ("Resizable BAR / Smart Access Memory", "Permet au processeur d'accéder à toute la mémoire de la carte graphique. Demande « Above 4G Decoding » activé et un GPU récent (RTX 3000+ / RX 6000+)."),
        ("Boost du processeur", "Vérifie que Intel Turbo Boost ou AMD Precision Boost (Core Performance Boost) est activé. Sans lui, le CPU reste à sa fréquence de base."),
        ("Mise à jour du BIOS", "Les nouvelles versions corrigent des bugs de stabilité et de compatibilité mémoire. Fais-la depuis le site du fabricant de ta carte mère, jamais à l'aveugle."),
        ("Courbes de ventilation", "Une courbe plus agressive évite que le CPU et le GPU ne ralentissent à cause de la chaleur pendant les longues sessions."),
        ("Démarrage sécurisé (Secure Boot)", "À laisser activé : certains jeux à anti-triche (Valorant, Fortnite selon le mode) l'exigent."),
    };
    public MainWindow()
    {
        InitializeComponent();

        var area = SystemParameters.WorkArea;
        Height = Math.Min(Height, area.Height - 20);
        Width = Math.Min(Width, area.Width - 20);

        UserName.Text = Environment.UserName;
        UserInitial.Text = Environment.UserName.Length > 0 ? char.ToUpper(Environment.UserName[0]).ToString() : "U";
        WelcomeTitle.Text = $"Bienvenue, {Environment.UserName} !";
        Chart.Face = new Typeface((FontFamily)FindResource("Mono"), FontStyles.Normal, FontWeights.Normal, FontStretches.Normal);
        Chart.Accent = (Color)FindResource("AccentColor");

        Header.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        Brand.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        BtnMin.Click += (_, _) => WindowState = WindowState.Minimized;
        BtnClose.Click += (_, _) => Close();

        LoadState();
        _view = CollectionViewSource.GetDefaultView(_tweaks);
        TweakList.ItemsSource = _view;
        FixList.ItemsSource = _fixes;
        foreach (var t in _tweaks)
            t.PropertyChanged += (_, e) => { if (e.PropertyName == nameof(Tweak.Applied)) Dispatcher.Invoke(UpdateCount); };
        UpdateCount();

        // navigation (catégories générées)
        foreach (var c in Cats)
        {
            var rb = new RadioButton { Style = (Style)FindResource("NavItem"), GroupName = "Nav", Tag = "" };
            var icon = new System.Windows.Shapes.Path { Data = Geometry.Parse(c.Icon), Stretch = Stretch.Uniform, Width = 17, Height = 17 };
            icon.SetBinding(System.Windows.Shapes.Shape.FillProperty, new Binding("Foreground") { RelativeSource = new RelativeSource(RelativeSourceMode.FindAncestor, typeof(RadioButton), 1) });
            rb.Content = new StackPanel { Orientation = Orientation.Horizontal, Children = { icon, new TextBlock { Text = c.Label, Margin = new Thickness(12, 0, 0, 0) } } };
            string key = c.Key;
            rb.Checked += (_, _) => ShowPage(key);
            _navs[c.Key] = rb;
            NavTweaks.Children.Add(rb);
        }
        BiosList.ItemsSource = BiosTips.Select((t, i) => new { Number = $"{i + 1:00}", t.Title, t.Body }).ToList();
        BtnBios.Click += (_, _) =>
        {
            if (MessageBox.Show("Le PC va redémarrer immédiatement vers le BIOS/UEFI.\n\nEnregistre ton travail avant de continuer.\n\nRedémarrer maintenant ?",
                    "Blatja Tweaks", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                Sh.Run("shutdown", "/r /fw /t 3");
        };

        NavDash.Checked += (_, _) => ShowPage("dash");
        NavRestore.Checked += (_, _) => ShowPage("restore");
        NavFix.Checked += (_, _) => ShowPage("fix");
        NavGpu.Checked += (_, _) => ShowPage("gpu");
        NavBios.Checked += (_, _) => ShowPage("bios");
        BtnGoSystem.Click += (_, _) => _navs["GÉNÉRAL"].IsChecked = true;

        // graphique : onglets
        TabCpu.Checked += (_, _) => SetChart(_m.Cpu, "%", "CPU", _m.CpuName);
        TabGpu.Checked += (_, _) => SetChart(_m.Gpu, "%", "GPU", _gpu.Name);
        TabRam.Checked += (_, _) => SetChart(_m.Ram, "%", "RAM", "Mémoire vive");
        TabTemp.Checked += (_, _) => SetChart(_m.Temp, "°C", "Température", "Carte graphique");
        SetChart(_m.Cpu, "%", "CPU", _m.CpuName);

        BtnAll.Click += (_, _) => Visible().ForEach(t => t.IsOn = t.Recommended);
        BtnNone.Click += (_, _) => Visible().ForEach(t => t.IsOn = false);
        BtnQuick.Click += async (_, _) => { _tweaks.ForEach(t => t.IsOn = t.Recommended); await ApplyAsync(restoreAll: false); };
        BtnApply.Click += async (_, _) => await ApplyAsync(restoreAll: false);
        BtnRestore.Click += async (_, _) => await ApplyAsync(restoreAll: true);
        BtnClean.Click += async (_, _) => await RunAsync("Nettoyage", () => $"{Tweaks.CleanTemp()} Mo libérés");
        BtnSysInfo.Click += (_, _) => Launch("msinfo32.exe");
        BtnGpuBoost.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Boost(_gpu)); await RefreshGpuAsync(); };
        BtnGpuReset.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Reset(_gpu)); await RefreshGpuAsync(); };
        BtnCreateRestore.Click += async (_, _) => await CreateRestorePageAsync();

        // point de restauration obligatoire
        GateBtn.Click += async (_, _) => await CreateRestoreGateAsync();
        GateSkip.Click += (_, _) =>
        {
            if (MessageBox.Show("Sans point de restauration, tu ne pourras annuler les réglages qu'avec « Annuler tous les réglages Blatja ».\n\nContinuer quand même ?",
                    "Blatja Tweaks", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes)
            { _safe = true; Log("Point de restauration ignoré par l'utilisateur."); CloseGate(); }
        };
        if (Restore.Recent() is DateTime when)
        {
            GateStatus.Text = $"Un point de restauration existe déjà ({when:dd/MM à HH:mm}).";
            GateBtn.Content = "Continuer";
            GateBtn.Tag = "ok";
        }

        _toastTimer.Tick += (_, _) => { _toastTimer.Stop(); HideToast(); };

        ShowPage("dash", animate: false);
        switch (Environment.GetEnvironmentVariable("BLATJA_PAGE"))   // utile pour les captures de développement
        {
            case "restore": NavRestore.IsChecked = true; break;
            case "fix": NavFix.IsChecked = true; break;
            case "system": _navs["GÉNÉRAL"].IsChecked = true; break;
            case "debloat": _navs["DÉBLOAT"].IsChecked = true; break;
            case "services": _navs["SERVICES"].IsChecked = true; break;
            case "fn": _navs["JEUX"].IsChecked = true; break;
            case "bios": NavBios.IsChecked = true; break;
            case "gpu": NavGpu.IsChecked = true; break;
        }
        if (Environment.GetEnvironmentVariable("BLATJA_NOGATE") == "1") { _safe = true; Gate.Visibility = Visibility.Collapsed; }
        if (_demo) for (int i = 0; i < Metrics.History; i++) _m.Sample(null, demo: true);

        Loaded += async (_, _) =>
        {
            Root.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(420)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } });
            Log("Blatja Tweaks prêt. Chaque réglage est réversible.");
            RefreshRestoreList();
            await RefreshGpuAsync();
            await Task.Run(DetectFortnite);

            var timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            timer.Tick += (_, _) => Tick();
            timer.Start();
            Tick();
            CompositionTarget.Rendering += (_, _) =>
            {
                if (PageDash.Visibility != Visibility.Visible && PageGpu.Visibility != Visibility.Visible) return;
                Chart.Phase = Math.Clamp(_sinceSample.Elapsed.TotalSeconds, 0, 1);
                Chart.InvalidateVisual();
            };
        };
    }

    private List<Tweak> Visible() => _view.Cast<Tweak>().ToList();
    private Brush Res(string key) => (Brush)FindResource(key);
    private static void Launch(string target) { try { Process.Start(new ProcessStartInfo(target) { UseShellExecute = true }); } catch { } }

    // ───────────── Mesures en direct ─────────────
    private void Tick()
    {
        if (!_polling && _gpu.SmiPath is not null && !_demo)
        {
            _polling = true;
            _ = Task.Run(() => Metrics.PollNvidia(_gpu.SmiPath)).ContinueWith(t =>
                Dispatcher.Invoke(() => { _gpuLive = t.Result; _polling = false; }));
        }

        _m.Sample(_gpuLive, _demo);
        _sinceSample.Restart();

        Animate(GaugeCpu, _m.CpuNow); Animate(GaugeRam, _m.RamNow);
        CpuVal.Text = $"{_m.CpuNow:0}%";
        CpuSub.Text = Shorten(_m.CpuName, 30);
        RamVal.Text = $"{_m.RamNow:0}%";
        RamSub.Text = $"{_m.RamUsedGb:0.0} / {_m.RamTotalGb:0} Go";

        if (_m.HasGpu)
        {
            Animate(GaugeGpu, _m.GpuNow);
            GpuVal.Text = $"{_m.GpuNow:0}%";
            GpuSub.Text = $"{_m.TempNow:0} °C · {Shorten(_gpu.Name, 22)}";
            TileTemp.Text = $"{_m.TempNow:0} °C";
            TileTemp.Foreground = Res(_m.TempNow < 83 ? "Text" : "Warn");
        }
        else
        {
            GpuVal.Text = "—";
            GpuSub.Text = _gpu.Name.Length > 0 ? Shorten(_gpu.Name, 30) : "Aucune donnée GPU";
        }

        var (used, total) = Metrics.Disk();
        if (total > 0)
        {
            DiskText.Text = $"{used:0} Go utilisés sur {total:0} Go";
            DiskBar.Value = used / total * 100;
        }
    }

    private static void Animate(RingGauge g, double to) =>
        g.BeginAnimation(RingGauge.ValueProperty, new DoubleAnimation(to, TimeSpan.FromMilliseconds(700)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } });

    private static string Shorten(string s, int n) => s.Length <= n ? s : s[..(n - 1)] + "…";

    private void SetChart(List<double> src, string unit, string title, string sub)
    {
        if (Chart is null) return;
        Chart.Source = src; Chart.Unit = unit; Chart.InvalidateVisual();
        ChartSub.Text = $"{title} · {sub}";
    }

    // ───────────── Point de restauration ─────────────
    private async Task CreateRestoreGateAsync()
    {
        if (GateBtn.Tag as string == "ok") { _safe = true; CloseGate(); return; }

        GateBtn.IsEnabled = false;
        GateSkip.Visibility = Visibility.Collapsed;
        GateStatus.Foreground = Res("Muted");
        GateStatus.Text = "Création en cours… (jusqu'à une minute)";
        var (ok, msg) = await Task.Run(() => Restore.Create("Avant optimisation", "Point créé automatiquement au premier lancement", "#FF3B52"));
        if (ok)
        {
            _safe = true;
            GateStatus.Foreground = Res("Good");
            GateStatus.Text = "✔ " + msg;
            Log(msg); RefreshRestoreList();
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

    private async Task CreateRestorePageAsync()
    {
        if (_busy) return;
        string name = string.IsNullOrWhiteSpace(RpName.Text) ? "Point Blatja" : RpName.Text.Trim();
        string color = new[] { Sw1, Sw2, Sw3, Sw4, Sw5 }.FirstOrDefault(s => s.IsChecked == true)?.Tag as string ?? "#FF3B52";
        BtnCreateRestore.IsEnabled = false;
        RpStatus.Text = "Création en cours…";
        var (ok, msg) = await Task.Run(() => Restore.Create(name, RpDesc.Text.Trim(), color));
        BtnCreateRestore.IsEnabled = true;
        RpStatus.Text = ok ? "" : "Échec : " + msg;
        if (ok) { _safe = true; RefreshRestoreList(); }
        Toast(ok ? $"Point « {name} » créé" : "Impossible de créer le point de restauration", ok);
        Log(ok ? $"Point de restauration « {name} » créé." : "Point de restauration : " + msg);
    }

    private void RefreshRestoreList()
    {
        var h = Restore.History().OrderByDescending(e => e.When).ToList();
        RestoreList.ItemsSource = h;
        RestoreEmpty.Visibility = h.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    private void RestoreItem_Click(object sender, RoutedEventArgs e)
    {
        Launch("rstrui.exe");
        Toast("Choisis ton point dans l'assistant de restauration Windows", true);
    }

    private void CloseGate()
    {
        var fade = new DoubleAnimation(1, 0, TimeSpan.FromMilliseconds(280));
        fade.Completed += (_, _) => Gate.Visibility = Visibility.Collapsed;
        Gate.BeginAnimation(OpacityProperty, fade);
    }

    // ───────────── Corrections ─────────────
    private async void Fix_Click(object sender, RoutedEventArgs e)
    {
        if (_busy || ((FrameworkElement)sender).DataContext is not Fix fix) return;
        var btn = (Button)sender;
        _busy = true;
        object? old = btn.Content;
        btn.Content = fix.Long ? "En cours…" : "…";
        btn.IsEnabled = false;
        try
        {
            string r = await Task.Run(fix.Run);
            Log($"✔ {fix.Name} : {r}");
            Toast(r, true);
        }
        catch (Exception ex)
        {
            Log($"✘ {fix.Name} : {ex.Message}");
            Toast($"{fix.Name} : {ex.Message}", false);
        }
        btn.Content = old; btn.IsEnabled = true; _busy = false;
    }

    // ───────────── Navigation ─────────────
    private void ShowPage(string key, bool animate = true)
    {
        if (PageDash is null) return;
        _page = key;
        var cat = Cats.FirstOrDefault(c => c.Key == key);
        bool isTweaks = cat.Key is not null;

        PageDash.Visibility = key == "dash" ? Visibility.Visible : Visibility.Collapsed;
        PageRestore.Visibility = key == "restore" ? Visibility.Visible : Visibility.Collapsed;
        PageFix.Visibility = key == "fix" ? Visibility.Visible : Visibility.Collapsed;
        PageTweaks.Visibility = isTweaks ? Visibility.Visible : Visibility.Collapsed;
        PageGpu.Visibility = key == "gpu" ? Visibility.Visible : Visibility.Collapsed;
        PageBios.Visibility = key == "bios" ? Visibility.Visible : Visibility.Collapsed;
        ActionBar.Visibility = isTweaks ? Visibility.Visible : Visibility.Collapsed;

        PageCrumb.Text = isTweaks ? $"Réglages  ›  {cat.Label}" : key switch
        {
            "dash" => "Accueil", "restore" => "Restauration", "fix" => "Corrections", "gpu" => "Matériel  ›  Carte graphique", _ => "Matériel  ›  BIOS",
        };

        if (isTweaks)
        {
            PageTitle.Text = cat.Title;
            PageSub.Text = key == "JEUX" ? (_fnExe ?? "Fortnite non détecté : lance-le une fois via Epic Games Launcher.") : cat.Sub;
            _view.Filter = o => ((Tweak)o).Category == key;
            _view.Refresh();
        }
        if (key == "restore") RefreshRestoreList();

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

    // ───────────── Application des réglages ─────────────
    private async Task ApplyAsync(bool restoreAll)
    {
        if (_busy) return;
        if (!_safe)
        {
            Gate.Visibility = Visibility.Visible;
            Gate.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(200)));
            return;
        }

        if (restoreAll) _tweaks.ForEach(t => t.IsOn = false);
        var todo = _tweaks.Where(t => t.IsOn != t.Applied).ToList();
        if (todo.Count == 0) { Toast("Rien à faire : tout est déjà à jour", true); return; }

        SetBusy(true);
        bool reboot = false; int failed = 0;
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
                    failed++;
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
        Toast(failed > 0 ? $"{failed} réglage(s) en échec — voir l'activité" : reboot ? "Terminé — redémarre le PC pour tout activer" : "Réglages appliqués", failed == 0);
        await Task.Delay(500);
        SetBusy(false);
    }

    private async Task RunAsync(string label, Func<string> work)
    {
        if (_busy) return;
        SetBusy(true);
        try { string r = await Task.Run(work); Log($"{label} : {r}"); Toast(r, true); }
        catch (Exception ex) { Log($"✘ {label} : {ex.Message}"); Toast($"{label} : {ex.Message}", false); }
        SetBusy(false);
    }

    // ───────────── Détection ─────────────
    private async Task RefreshGpuAsync()
    {
        _gpu = await Task.Run(Gpu.Query);
        GpuName.Text = _gpu.Name;
        GpuDriver.Text = _gpu.Driver is null ? "" : $"Pilote {_gpu.Driver}";
        TilePower.Text = _gpu.PowerLimit is double pl ? $"{pl:0} W" : "—";
        TileClock.Text = _gpu.MaxClock is int mc ? $"{mc}" : "—";
        if (_gpu.PowerLimit is double cur && _gpu.PowerMax is double max && max > 0)
        {
            Tween(BarPower.Value, cur / max * 100, 600, v => BarPower.Value = v);
            BarPowerLabel.Text = $"sur {max:0} W maximum";
        }
        else { BarPower.Value = 0; BarPowerLabel.Text = ""; }

        bool nv = _gpu.SmiPath is not null;
        BtnGpuBoost.IsEnabled = BtnGpuReset.IsEnabled = nv;
        GpuStatus.Text = nv ? "" :
            _gpu.Vendor == "AMD" ? "AMD : l'overclock se règle dans AMD Adrenalin (Performances → Réglages). Les réglages système restent actifs." :
            _gpu.Vendor == "NVIDIA" ? "Installe le pilote NVIDIA officiel pour activer le boost GPU." :
            "Boost GPU disponible uniquement pour les cartes NVIDIA.";
        if (TabGpu.IsChecked == true) SetChart(_m.Gpu, "%", "GPU", _gpu.Name);
    }

    private void DetectFortnite()
    {
        string? exe = Fortnite.FindExe();
        Dispatcher.Invoke(() =>
        {
            _fnExe = exe;
            FnStatus.Text = exe is null ? "Fortnite non détecté" : "Fortnite · Epic Games";
            FnPath.Text = exe ?? "Installe-le via Epic Games Launcher.";
            GameBadgeText.Text = exe is null ? "ABSENT" : "PRÊT";
            if (_page == "JEUX") ShowPage("JEUX", animate: false);
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
            set(from + (to - from) * (1 - Math.Pow(1 - p, 3)));
            if (p >= 1) timer.Stop();
        };
        timer.Start();
    }

    private void UpdateCount()
    {
        int n = _tweaks.Count(t => t.Applied), total = _tweaks.Count;
        ActiveCount.Text = $"{n} / {total} réglages actifs";
        HeroCount.Text = $"{(total == 0 ? 0 : Math.Round(n * 100.0 / total))}%";

        int rec = _tweaks.Count(t => t.Recommended), recOn = _tweaks.Count(t => t.Recommended && t.Applied);
        PresetName.Text = n == 0 ? "Aucun" : recOn == rec ? "Recommandé" : "Personnalisé";

        foreach (var (key, nav) in _navs)
        {
            int tot = _tweaks.Count(t => t.Category == key), on = _tweaks.Count(t => t.Category == key && t.Applied);
            nav.Tag = $"{on}/{tot}";
        }
        if (_fnExe is not null && GameBadgeText is not null)
            GameBadgeText.Text = _tweaks.Where(t => t.Category == "JEUX").All(t => t.Applied) ? "ACTIF" : "PRÊT";
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        BtnApply.IsEnabled = BtnRestore.IsEnabled = BtnClean.IsEnabled = BtnQuick.IsEnabled = !busy;
        if (!busy) { Tween(Progress.Value, 0, 300, v => Progress.Value = v); ProgressLabel.Text = "Prêt"; }
        else ProgressLabel.Text = "En cours…";
    }

    private void Toast(string msg, bool ok)
    {
        ToastText.Text = msg;
        ToastDot.Fill = Res(ok ? "Good" : "Warn");
        var ease = new CubicEase { EasingMode = EasingMode.EaseOut };
        Toast_.BeginAnimation(OpacityProperty, new DoubleAnimation(1, TimeSpan.FromMilliseconds(220)));
        ToastSlide.BeginAnimation(TranslateTransform.XProperty, new DoubleAnimation(0, TimeSpan.FromMilliseconds(300)) { EasingFunction = ease });
        _toastTimer.Stop(); _toastTimer.Start();
    }

    private void HideToast()
    {
        Toast_.BeginAnimation(OpacityProperty, new DoubleAnimation(0, TimeSpan.FromMilliseconds(260)));
        ToastSlide.BeginAnimation(TranslateTransform.XProperty, new DoubleAnimation(30, TimeSpan.FromMilliseconds(260)));
    }

    private void Log(string msg)
    {
        LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {msg}\n");
        LogBox.ScrollToEnd();
    }

    private void LogUi(string msg) => Dispatcher.Invoke(() => Log(msg));
}
