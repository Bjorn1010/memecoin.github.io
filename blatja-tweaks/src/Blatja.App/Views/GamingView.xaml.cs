using System.Windows;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

public partial class GamingView : PageBase
{
    private readonly NetworkPanel _net = new();
    private GameProfile? _profile = GameProfiles.All[0];   // null = personnalisé
    private bool _loaded;

    public GamingView()
    {
        InitializeComponent();
        NetHost.Content = _net;
        (PBalName.Text, PBalSum.Text) = (GameProfiles.All[0].Name, GameProfiles.All[0].Summary);
        (PGamName.Text, PGamSum.Text) = (GameProfiles.All[1].Name, GameProfiles.All[1].Summary);
        (PMaxName.Text, PMaxSum.Text) = (GameProfiles.All[2].Name, GameProfiles.All[2].Summary);
        PBal.Checked += (_, _) => Select(GameProfiles.All[0]);
        PGam.Checked += (_, _) => Select(GameProfiles.All[1]);
        PMax.Checked += (_, _) => Select(GameProfiles.All[2]);
        PCus.Checked += (_, _) => Select(null);
        BtnApply.Click += async (_, _) => await ApplyAsync();
        BtnRevert.Click += async (_, _) => await RevertAsync();
        OpStore.Changed += () => { if (IsVisible) Refresh(); };
        Refresh();
    }

    public override async void OnShow()
    {
        Refresh();
        if (_loaded) return;
        _loaded = true;
        GamesSpin.Visibility = Visibility.Visible;
        var games = await Task.Run(() => { try { return Svc.Games.Detect(); } catch (Exception ex) { Log.Write("Jeux : " + ex.Message); return Array.Empty<DetectedGame>(); } });
        Games.ItemsSource = games;
        GamesEmpty.Visibility = games.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        GamesSpin.Visibility = Visibility.Collapsed;
        _ = OpStore.RefreshAsync();   // les optimisations propres à un jeu dépendent de sa détection
    }

    private void Select(GameProfile? p) { _profile = p; Refresh(); }

    private IEnumerable<OpVm> Included() => _profile is null
        ? OpStore.All.Where(v => v.Category is Categories.Gaming or Categories.Cpu or Categories.Gpu or Categories.Network && v.State != OpState.NotApplicable)
        : _profile.OpIds.Select(OpStore.Find).Where(v => v is not null).Select(v => v!);

    private void Refresh()
    {
        var items = Included().ToList();
        Included_Set(items);

        void Badge(GameProfile gp, System.Windows.Controls.Border b)
        {
            var applicable = gp.OpIds.Select(OpStore.Find).Where(v => v is { State: not OpState.NotApplicable }).ToList();
            b.Visibility = applicable.Count > 0 && applicable.All(v => v!.State == OpState.Enabled) ? Visibility.Visible : Visibility.Collapsed;
        }
        Badge(GameProfiles.All[0], PBalBadge); Badge(GameProfiles.All[1], PGamBadge); Badge(GameProfiles.All[2], PMaxBadge);

        BtnApply.Content = _profile is null ? "Appliquer la sélection" : $"Appliquer le profil « {_profile.Name} »";
        BtnRevert.Visibility = _profile is null ? Visibility.Collapsed : Visibility.Visible;
        BtnApply.IsEnabled = !OperationFlow.IsBusy;
    }

    private void Included_Set(List<OpVm> items)
    {
        Included_.ItemsSource = items;
        IncludeTitle.Text = _profile is null ? "Optimisations disponibles" : $"Ce que fait « {_profile.Name} »";
        int na = items.Count(v => v.State == OpState.NotApplicable);
        IncludeCount.Text = $"{items.Count(v => v.State == OpState.Enabled)} appliquée(s) · {items.Count} au total" + (na > 0 ? $" · {na} non applicable(s)" : "");
    }

    private async Task ApplyAsync()
    {
        var items = Included().ToList();
        var todo = (_profile is null ? items.Where(v => v.IsSelected && v.CanApply) : items.Where(v => v.CanApply)).Select(v => (v.Op, OpAction.Apply)).ToList();
        if (todo.Count == 0) { MainWindow.Current.ShowToast(_profile is null ? "Aucune optimisation n'est cochée." : "Ce profil est déjà entièrement appliqué sur ton système.", Kind.Info); return; }
        await OperationFlow.RunAsync(todo, _profile is null ? "Appliquer la sélection" : $"Appliquer le profil « {_profile.Name} »");
    }

    private async Task RevertAsync()
    {
        var todo = Included().Where(v => v.CanRevert).Select(v => (v.Op, OpAction.Revert)).ToList();
        if (todo.Count == 0) { MainWindow.Current.ShowToast("Aucune optimisation de ce profil n'est appliquée.", Kind.Info); return; }
        await OperationFlow.RunAsync(todo, $"Restaurer le profil « {_profile?.Name} »");
    }
}
