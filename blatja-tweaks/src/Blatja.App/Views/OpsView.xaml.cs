using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using Blatja.App.Controls;
using Blatja.App.Services;
using Blatja.App.Shell;
using Blatja.Core;

namespace Blatja.App.Views;

/// <summary>Page d'une catégorie d'optimisations : états réels détectés, sélection, application et restauration.</summary>
public partial class OpsView : PageBase
{
    private readonly string _category;
    private readonly List<OpVm> _items;
    private readonly System.ComponentModel.ICollectionView _view;
    private readonly PageBase? _extra;

    public OpsView(string category, string title, string subtitle, PageBase? extra)
    {
        InitializeComponent();
        _category = category;
        Title.Text = title; Sub.Text = subtitle;
        _items = OpStore.ByCategory(category).ToList();
        _view = CollectionViewSource.GetDefaultView(_items);
        _view.GroupDescriptions.Add(new PropertyGroupDescription(nameof(OpVm.Group)));
        List.ItemsSource = _view;

        _extra = extra;
        if (extra is not null) Extra.Content = extra;

        foreach (var v in _items) v.PropertyChanged += (_, e) => { if (e.PropertyName is nameof(OpVm.IsSelected) or nameof(OpVm.State)) RefreshSummary(); };
        BtnSelectRec.Click += (_, _) => { foreach (var v in _items) v.IsSelected = v.CanApply && v.Recommended; RefreshSummary(); };
        BtnClear.Click += (_, _) => { foreach (var v in _items) v.IsSelected = false; };
        BtnApply.Click += async (_, _) => await ApplyAsync();
        BtnRevertAll.Click += async (_, _) => await RevertAllAsync();
        OpStore.Changed += OnStore;
        RefreshSummary();
    }

    public override void OnShow()
    {
        OnStore(); _extra?.OnShow();
        Dispatcher.InvokeAsync(() =>
        {
            var cards = Anim.Descendants<ContentPresenter>(List).Where(cp => cp.DataContext is OpVm).Take(14).Cast<UIElement>();
            Anim.Reveal(cards.Prepend(Extra).Prepend((UIElement)Title.Parent), 38, 10, 300);
        }, System.Windows.Threading.DispatcherPriority.Loaded);
    }
    public override void OnHide() => _extra?.OnHide();
    public override void OnMetrics() => _extra?.OnMetrics();

    private void OnStore()
    {
        Spin.Visibility = OpStore.Scanning ? Visibility.Visible : Visibility.Collapsed;
        RefreshSummary();
    }

    private void RefreshSummary()
    {
        int sel = _items.Count(v => v.IsSelected && v.CanApply);
        int active = _items.Count(v => v.State == OpState.Enabled);
        int usable = _items.Count(v => v.State != OpState.NotApplicable);
        Summary.Text = OpStore.Scanning ? "Lecture de l'état de Windows…" : $"{active} appliquée(s) · {usable} applicable(s) sur {_items.Count}";
        BtnApply.Content = sel > 0 ? $"Appliquer les changements sélectionnés ({sel})" : "Appliquer les changements sélectionnés";
        BtnApply.IsEnabled = sel > 0 && !OperationFlow.IsBusy;
        BtnRevertAll.IsEnabled = active > 0 && !OperationFlow.IsBusy;
        BtnSelectRec.IsEnabled = _items.Any(v => v.CanApply && v.Recommended);
    }

    private async Task ApplyAsync()
    {
        var chosen = _items.Where(v => v.IsSelected && v.CanApply).Select(v => (v.Op, OpAction.Apply)).ToList();
        if (chosen.Count == 0) return;
        await OperationFlow.RunAsync(chosen, $"Appliquer {chosen.Count} optimisation(s)");
    }

    private async Task RevertAllAsync()
    {
        var active = _items.Where(v => v.CanRevert).Select(v => (v.Op, OpAction.Revert)).ToList();
        if (active.Count == 0) return;
        await OperationFlow.RunAsync(active, $"Restaurer {active.Count} optimisation(s)");
    }
}
