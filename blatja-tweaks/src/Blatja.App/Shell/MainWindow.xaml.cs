using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;
using Blatja.App.Controls;
using Blatja.App.Services;
using Blatja.App.Views;
using Blatja.Core;

namespace Blatja.App.Shell;

public enum Kind { Success, Warning, Danger, Info }
public enum StatusKind { Ready, Busy, Error }

public partial class MainWindow : Window
{
    public static MainWindow Current { get; private set; } = null!;

    private readonly Dictionary<string, (RadioButton Nav, string Title, Func<PageBase> Make)> _pages = new();
    private readonly Dictionary<string, PageBase> _cache = new();
    private PageBase? _current;
    private string _currentKey = "";
    private readonly DispatcherTimer _toastTimer = new() { Interval = TimeSpan.FromSeconds(4) };
    private readonly DispatcherTimer _clock = new() { Interval = TimeSpan.FromSeconds(1) };
    private TaskCompletionSource<int>? _dialog;

    public MainWindow()
    {
        Current = this;
        InitializeComponent();

        var area = SystemParameters.WorkArea;
        Height = Math.Min(Height, area.Height - 20);
        Width = Math.Min(Width, area.Width - 20);

        TopBar.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed && e.ClickCount == 1) DragMove(); };
        Brand.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        Brand.MouseEnter += (_, _) => { var a = new DoubleAnimation(1.12, TimeSpan.FromMilliseconds(260)) { EasingFunction = new BackEase { Amplitude = 0.9 } }; LogoScale.BeginAnimation(ScaleTransform.ScaleXProperty, a); LogoScale.BeginAnimation(ScaleTransform.ScaleYProperty, a); };
        Brand.MouseLeave += (_, _) => { var a = new DoubleAnimation(1, TimeSpan.FromMilliseconds(220)); LogoScale.BeginAnimation(ScaleTransform.ScaleXProperty, a); LogoScale.BeginAnimation(ScaleTransform.ScaleYProperty, a); };
        BtnMin.Click += (_, _) => WindowState = WindowState.Minimized;
        BtnClose.Click += (_, _) => Close();
        BtnSettings.Click += (_, _) => NavSettings.IsChecked = true;
        BtnElevate.Click += async (_, _) => await ElevateAsync();

        Register("dashboard", NavDashboard, "Dashboard", () => new DashboardView());
        Register("monitoring", NavMonitoring, "Monitoring", () => new MonitoringView());
        Register("auto", NavAuto, "Analyse et optimisation", () => new AutoView());
        Register("gaming", NavGaming, "Gaming", () => new GamingView());
        Register("cpu", NavCpu, "CPU et processeur", () => new OpsView(Categories.Cpu, "CPU et processeur", "Alimentation, planification et priorités du processeur.", new CpuPanel()));
        Register("gpu", NavGpu, "GPU et pilotes", () => new OpsView(Categories.Gpu, "GPU et pilotes", "Carte graphique, pilote et planification GPU.", new GpuPanel()));
        Register("memory", NavMemory, "Mémoire et processus", () => new OpsView(Categories.Memory, "Mémoire et processus", "Applications consommatrices et priorités des applications en arrière-plan.", new ProcessPanel()));
        Register("network", NavNetwork, "Réseau et latence", () => new OpsView(Categories.Network, "Réseau et latence", "Latence réseau mesurée et réglages de la pile réseau.", new NetworkPanel()));
        Register("storage", NavStorage, "Stockage et démarrage", () => new OpsView(Categories.Storage, "Stockage et démarrage", "Espace disque, indexation et programmes lancés au démarrage.", new StartupPanel()));
        Register("debloat", NavDebloat, "Windows Debloat", () => new OpsView(Categories.Debloat, "Windows Debloat", "Retire de Windows ce qui consomme des ressources ou distrait. Chaque réglage affiche son état réel et se restaure.", null));
        Register("utilities", NavUtilities, "Utilitaires système", () => new UtilitiesView());
        Register("history", NavHistory, "Historique des modifications", () => new HistoryView());
        Register("restore", NavRestore, "Points de restauration", () => new RestoreView());
        Register("settings", NavSettings, "Paramètres", () => new SettingsView());

        SideWindows.Text = Svc.Ctx.Info.Description;
        UpdateAdminChip();

        _toastTimer.Tick += (_, _) => { _toastTimer.Stop(); HideToast(); };
        _clock.Tick += (_, _) => UpdateRefreshLabel();

        PreviewKeyDown += OnKey;
        StateChanged += (_, _) => Svc.Metrics.Pause(WindowState == WindowState.Minimized);
        Closing += (_, e) =>
        {
            if (!OperationFlow.IsBusy) return;
            e.Cancel = true;
            ShowToast("Une opération est en cours : attends sa fin pour fermer Blatja.", Kind.Warning);
        };

        OpStore.Init();
        OpStore.Changed += OnStoreChanged;
        Svc.Metrics.Updated += OnMetrics;

        Loaded += async (_, _) =>
        {
            Navigate(Environment.GetEnvironmentVariable("BLATJA_PAGE") is { Length: > 0 } p && _pages.ContainsKey(p) ? p : "dashboard");
            Svc.Metrics.Start();
            _clock.Start();
            await OpStore.RefreshAsync();
        };
    }

    private void Register(string key, RadioButton nav, string title, Func<PageBase> make)
    {
        _pages[key] = (nav, title, make);
        nav.Checked += (_, _) => Navigate(key);
    }

    // ───────────── Navigation ─────────────
    public void Navigate(string key)
    {
        if (!_pages.TryGetValue(key, out var page) || key == _currentKey && _current is not null) return;
        _current?.OnHide();
        PageBase view;
        try
        {
            if (!_cache.TryGetValue(key, out view!)) _cache[key] = view = page.Make();
        }
        catch (Exception ex)
        {
            Log.Write($"Page {key} : {ex}");
            ShowToast($"La page « {page.Title} » n'a pas pu s'ouvrir : {ex.Message}", Kind.Danger);
            if (_current is not null) _current.OnShow();
            return;
        }
        _currentKey = key; _current = view;
        if (page.Nav.IsChecked != true) page.Nav.IsChecked = true;
        PageTitle.Text = page.Title;
        PageHost.Content = view;
        view.Opacity = 0;
        view.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(160)));
        view.OnShow();
        if (view is not (DashboardView or OpsView))
            view.Dispatcher.InvokeAsync(() => Anim.RevealContent(view), DispatcherPriority.Loaded);
    }

    private void OnMetrics()
    {
        if (WindowState == WindowState.Minimized) return;
        UpdateRefreshLabel();
        _current?.OnMetrics();
    }

    private void OnStoreChanged()
    {
        void Badge(RadioButton nav, string? cat) { int n = OpStore.Pending(cat); Ui.SetBadge(nav, n > 0 ? n.ToString() : ""); }
        Badge(NavGaming, Categories.Gaming); Badge(NavCpu, Categories.Cpu); Badge(NavGpu, Categories.Gpu); Badge(NavMemory, Categories.Memory);
        Badge(NavNetwork, Categories.Network); Badge(NavStorage, Categories.Storage); Badge(NavDebloat, Categories.Debloat);
        int active = OpStore.All.Count(v => v.State == OpState.Enabled), usable = OpStore.All.Count(v => v.State != OpState.NotApplicable);
        SideSummary.Text = OpStore.Scanning ? "Lecture de l'état de Windows…" : $"{active} optimisation(s) active(s) sur {usable} applicable(s)";
    }

    // ───────────── Barre supérieure ─────────────
    private void UpdateAdminChip()
    {
        bool admin = Svc.IsAdmin;
        AdminChip.Style = (Style)FindResource(admin ? "Badge.Success" : "Badge.Warning");
        AdminText.Text = admin ? "Administrateur" : "Lecture seule";
        AdminChip.ToolTip = admin ? "Blatja peut appliquer des modifications système." : "Sans droits administrateur, Blatja peut analyser et surveiller, mais pas modifier le système.";
        BtnElevate.Visibility = admin ? Visibility.Collapsed : Visibility.Visible;
    }

    private async Task ElevateAsync()
    {
        int choice = await ShowDialogAsync("Relancer en administrateur",
            "Windows va demander ta confirmation (UAC) puis Blatja redémarrera avec les droits nécessaires pour appliquer des modifications. Les opérations en cours d'analyse seront perdues.",
            null, ("Relancer", "primary"), ("Annuler", "secondary"));
        if (choice != 0) return;
        if (Elevation.Relaunch()) { Log.Write("Relance en administrateur"); Application.Current.Shutdown(); }
        else ShowToast("Relance annulée : l'invite Windows a été refusée.", Kind.Warning);
    }

    private void UpdateRefreshLabel()
    {
        if (Svc.Metrics.LastUpdate is not { } t) { LastRefresh.Text = "En attente de mesures…"; return; }
        int s = (int)(DateTime.Now - t).TotalSeconds;
        LastRefresh.Text = $"Actualisé à {t:HH:mm:ss}" + (s > Svc.Settings.RefreshSeconds * 3 + 2 ? $" · il y a {s} s" : "");
    }

    public void SetStatus(string text, StatusKind kind)
    {
        StatusText.Text = text;
        StatusDot.Fill = (Brush)FindResource(kind switch { StatusKind.Busy => "Accent", StatusKind.Error => "Danger", _ => "Success" });
    }

    // ───────────── Clavier ─────────────
    private void OnKey(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape && DialogLayer.Visibility == Visibility.Visible && _dialog is not null) { CloseDialog(-1); e.Handled = true; }
        else if (e.Key == Key.F5 && !OperationFlow.IsBusy) { _ = OpStore.RefreshAsync(); ShowToast("État de Windows relu.", Kind.Info); e.Handled = true; }
        else if (Keyboard.Modifiers == ModifierKeys.Control && e.Key >= Key.D1 && e.Key <= Key.D9)
        {
            string[] order = { "dashboard", "monitoring", "auto", "gaming", "cpu", "gpu", "memory", "network", "storage" };
            int i = e.Key - Key.D1; if (i < order.Length) { Navigate(order[i]); e.Handled = true; }
        }
    }

    // ───────────── Commande « appliquer / restaurer » d'une carte ─────────────
    private void RunOp_CanExecute(object sender, CanExecuteRoutedEventArgs e) =>
        e.CanExecute = e.Parameter is OpVm { Busy: false } v && (v.CanApply || v.CanRevert) && !OperationFlow.IsBusy;

    private async void RunOp_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        if (e.Parameter is not OpVm v) return;
        var action = v.CanRevert ? OpAction.Revert : OpAction.Apply;
        await OperationFlow.RunAsync(new[] { (v.Op, action) }, action == OpAction.Apply ? $"Appliquer « {v.Name} »" : $"Restaurer « {v.Name} »");
    }

    // ───────────── Notifications ─────────────
    public void ShowToast(string message, Kind kind = Kind.Success)
    {
        ToastText.Text = message;
        ToastDot.Fill = (Brush)FindResource(kind switch { Kind.Danger => "Danger", Kind.Warning => "Warning", Kind.Info => "Text2", _ => "Success" });
        Toast.BeginAnimation(OpacityProperty, new DoubleAnimation(1, TimeSpan.FromMilliseconds(160)));
        ToastSlide.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(18, 0, TimeSpan.FromMilliseconds(380)) { EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.9 } });
        _toastTimer.Stop(); _toastTimer.Start();
    }

    private void HideToast()
    {
        Toast.BeginAnimation(OpacityProperty, new DoubleAnimation(0, TimeSpan.FromMilliseconds(200)));
        ToastSlide.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(12, TimeSpan.FromMilliseconds(200)));
    }

    // ───────────── Dialogues homogènes ─────────────
    /// <summary>Affiche un dialogue modal. Renvoie l'index du bouton choisi, ou -1 (Échap).</summary>
    public Task<int> ShowDialogAsync(string title, string message, IEnumerable<UIElement>? body, params (string Text, string Style)[] buttons)
    {
        var tcs = new TaskCompletionSource<int>();
        _dialog = tcs;

        var stack = new StackPanel { Margin = new Thickness(24, 22, 24, 0) };
        stack.Children.Add(new TextBlock { Text = title, Style = (Style)FindResource("Txt.H2"), TextWrapping = TextWrapping.Wrap });
        if (message.Length > 0) stack.Children.Add(new TextBlock { Text = message, Style = (Style)FindResource("Txt.Body"), Foreground = (Brush)FindResource("Text2"), Margin = new Thickness(0, 8, 0, 0), LineHeight = 20 });

        var content = new StackPanel();
        content.Children.Add(stack);
        if (body is not null)
        {
            var list = new StackPanel { Margin = new Thickness(0, 14, 0, 0) };
            foreach (var el in body) list.Children.Add(el);
            content.Children.Add(new ScrollViewer { Content = list, MaxHeight = 330, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Margin = new Thickness(24, 0, 20, 0) });
        }

        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(24, 18, 24, 20) };
        for (int i = 0; i < buttons.Length; i++)
        {
            int idx = i;
            var b = new Button { Content = buttons[i].Text, Style = (Style)FindResource("Btn." + char.ToUpper(buttons[i].Style[0]) + buttons[i].Style[1..]), Margin = new Thickness(i == 0 ? 0 : 8, 0, 0, 0) };
            b.Click += (_, _) => CloseDialog(idx);
            row.Children.Add(b);
        }
        // le bouton principal passe en dernier visuellement (à droite) : on inverse l'ordre d'affichage
        var ordered = row.Children.Cast<UIElement>().Reverse().ToList();
        row.Children.Clear(); foreach (var el in ordered) row.Children.Add(el);
        content.Children.Add(row);

        DialogCard.Child = content;
        DialogLayer.Opacity = 0; DialogLayer.Visibility = Visibility.Visible;
        DialogLayer.BeginAnimation(OpacityProperty, new DoubleAnimation(1, TimeSpan.FromMilliseconds(140)));
        var zoom = new DoubleAnimation(0.94, 1, TimeSpan.FromMilliseconds(260)) { EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.6 } };
        DialogScale.BeginAnimation(ScaleTransform.ScaleXProperty, zoom); DialogScale.BeginAnimation(ScaleTransform.ScaleYProperty, zoom);
        row.Children.OfType<Button>().LastOrDefault()?.Focus();
        return tcs.Task;
    }

    private void CloseDialog(int result)
    {
        var t = _dialog; _dialog = null;
        DialogLayer.Visibility = Visibility.Collapsed;
        DialogCard.Child = null;
        t?.TrySetResult(result);
    }

    /// <summary>Dialogue d'attente sans bouton (opération courte et non interruptible). À libérer avec Dispose.</summary>
    public IDisposable ShowBusy(string text)
    {
        var panel = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(24, 22, 24, 22) };
        panel.Children.Add(new Spinner { Margin = new Thickness(0, 0, 14, 0) });
        panel.Children.Add(new TextBlock { Text = text, Style = (Style)FindResource("Txt.Body"), VerticalAlignment = VerticalAlignment.Center });
        DialogCard.Child = panel;
        DialogLayer.Opacity = 1; DialogLayer.Visibility = Visibility.Visible;
        return new BusyScope(() => { if (_dialog is null) { DialogLayer.Visibility = Visibility.Collapsed; DialogCard.Child = null; } });
    }

    private sealed class BusyScope : IDisposable
    {
        private readonly Action _close; public BusyScope(Action close) { _close = close; }
        public void Dispose() => _close();
    }

    /// <summary>Ligne de dialogue : puce colorée, texte et détail.</summary>
    public UIElement DialogLine(string text, string? detail = null, Kind kind = Kind.Info, string? tag = null)
    {
        var g = new Grid { Margin = new Thickness(0, 0, 0, 10) };
        g.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        g.ColumnDefinitions.Add(new ColumnDefinition());
        g.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        g.Children.Add(new System.Windows.Shapes.Ellipse { Width = 7, Height = 7, Margin = new Thickness(0, 7, 12, 0), VerticalAlignment = VerticalAlignment.Top,
            Fill = (Brush)FindResource(kind switch { Kind.Danger => "Danger", Kind.Warning => "Warning", Kind.Success => "Success", _ => "Text3" }) });
        var tx = new StackPanel();
        tx.Children.Add(new TextBlock { Text = text, Style = (Style)FindResource("Txt.Body"), FontWeight = FontWeights.Medium });
        if (!string.IsNullOrEmpty(detail)) tx.Children.Add(new TextBlock { Text = detail, Style = (Style)FindResource("Txt.Caption") });
        Grid.SetColumn(tx, 1); g.Children.Add(tx);
        if (tag is not null)
        {
            var b = new Border { Style = (Style)FindResource("Badge"), VerticalAlignment = VerticalAlignment.Top, Margin = new Thickness(10, 1, 0, 0), Child = new TextBlock { Text = tag } };
            Grid.SetColumn(b, 2); g.Children.Add(b);
        }
        return g;
    }
}
