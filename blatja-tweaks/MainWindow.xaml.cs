using System.Collections.ObjectModel;
using System.Text.Json;
using System.Windows;
using System.Windows.Data;
using System.Windows.Input;

namespace BlatjaTweaks;

public partial class MainWindow : Window
{
    private static readonly string StateFile = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "BlatjaTweaks", "state.json");

    private readonly List<Tweak> _tweaks = Tweaks.Build();
    private GpuInfo _gpu = new("", "", null, null, null, null, null, null, null);
    private bool _busy;

    public MainWindow()
    {
        InitializeComponent();

        Header.MouseLeftButtonDown += (_, e) => { if (e.ButtonState == MouseButtonState.Pressed) DragMove(); };
        BtnMin.Click += (_, _) => WindowState = WindowState.Minimized;
        BtnClose.Click += (_, _) => Close();

        LoadState();
        var view = CollectionViewSource.GetDefaultView(_tweaks);
        view.GroupDescriptions.Add(new PropertyGroupDescription(nameof(Tweak.Category)));
        TweakList.ItemsSource = view;

        BtnAll.Click += (_, _) => _tweaks.ForEach(t => t.IsOn = true);
        BtnNone.Click += (_, _) => _tweaks.ForEach(t => t.IsOn = false);
        BtnApply.Click += async (_, _) => await ApplyAsync(restoreAll: false);
        BtnRestore.Click += async (_, _) => await ApplyAsync(restoreAll: true);
        BtnClean.Click += async (_, _) => await RunAsync("Nettoyage", () => $"{Tweaks.CleanTemp()} Mo libérés");
        BtnGpuBoost.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Boost(_gpu)); await RefreshGpuAsync(); };
        BtnGpuReset.Click += async (_, _) => { await RunAsync("GPU", () => Gpu.Reset(_gpu)); await RefreshGpuAsync(); };

        Loaded += async (_, _) =>
        {
            Log("Blatja Tweaks prêt. Chaque réglage est réversible.");
            await RefreshGpuAsync();
            await Task.Run(DetectFortnite);
        };
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
                Dispatcher.Invoke(() => Progress.Value = (i + 1) * 100.0 / todo.Count);
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
    private async Task RefreshGpuAsync()
    {
        _gpu = await Task.Run(Gpu.Query);
        GpuName.Text = _gpu.Name;
        var d = new List<string>();
        if (_gpu.Driver is not null) d.Add($"Pilote {_gpu.Driver}");
        if (_gpu.PowerLimit is double pl) d.Add($"Puissance {pl:0} W (max {_gpu.PowerMax:0} W)");
        if (_gpu.MaxClock is int mc) d.Add($"Boost max {mc} MHz");
        if (_gpu.Temp is int tp) d.Add($"{tp} °C");
        GpuDetails.Text = string.Join("\n", d);

        bool nv = _gpu.SmiPath is not null;
        BtnGpuBoost.IsEnabled = BtnGpuReset.IsEnabled = nv;
        GpuStatus.Text = nv ? "" :
            _gpu.Vendor == "AMD" ? "AMD : l'overclock se règle dans AMD Adrenalin (Performances → Réglages). Les réglages système ci-contre restent actifs." :
            _gpu.Vendor == "NVIDIA" ? "Installe le pilote NVIDIA officiel pour activer le boost GPU." :
            "Boost GPU disponible uniquement pour les cartes NVIDIA.";
    }

    private void DetectFortnite()
    {
        string? exe = Fortnite.FindExe();
        Dispatcher.Invoke(() =>
        {
            FnStatus.Text = exe is null ? "Non détecté" : "Installé ✔";
            FnStatus.Foreground = exe is null ? (System.Windows.Media.Brush)FindResource("Warn") : (System.Windows.Media.Brush)FindResource("Good");
            FnPath.Text = exe ?? "Installe-le via Epic Games Launcher pour activer les réglages Fortnite.";
        });
    }

    // ───────────── Utilitaires UI ─────────────
    private void SetBusy(bool busy)
    {
        _busy = busy;
        BtnApply.IsEnabled = BtnRestore.IsEnabled = BtnClean.IsEnabled = !busy;
        if (!busy) Progress.Value = 0;
    }

    private void Log(string msg)
    {
        LogBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {msg}\n");
        LogBox.ScrollToEnd();
    }

    private void LogUi(string msg) => Dispatcher.Invoke(() => Log(msg));
}
