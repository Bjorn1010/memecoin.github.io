using System.Windows.Input;
using System.Windows.Controls;
using Blatja.App.Services;
using Blatja.Core;

namespace Blatja.App.Shell;

public static class Commands
{
    public static readonly RoutedUICommand RunOp = new("Appliquer ou restaurer", "RunOp", typeof(Commands));
}

/// <summary>Page affichée dans la zone de contenu. Les pages ne sont mises à jour que lorsqu'elles sont visibles.</summary>
public abstract class PageBase : UserControl
{
    public virtual void OnShow() { }
    public virtual void OnHide() { }
    /// <summary>Appelée à chaque nouvelle mesure, uniquement si la page est affichée.</summary>
    public virtual void OnMetrics() { }
}

/// <summary>État réel de toutes les optimisations, partagé par toutes les pages.</summary>
public static class OpStore
{
    public static IReadOnlyList<OpVm> All { get; private set; } = Array.Empty<OpVm>();
    public static bool Scanning { get; private set; }
    public static DateTime? LastScan { get; private set; }
    public static event Action? Changed;

    public static void Init() { All = Svc.Catalog.Select(o => new OpVm(o)).ToList(); }

    public static IEnumerable<OpVm> ByCategory(string category) => All.Where(v => v.Category == category);
    public static OpVm? Find(string id) => All.FirstOrDefault(v => v.Op.Id == id);
    public static int Pending(string? category = null) => All.Count(v => v.State == OpState.Disabled && v.Recommended && (category is null || v.Category == category));

    private static Task? _running;

    /// <summary>Relit l'état réel de Windows. Un seul scan à la fois : un appel pendant un scan attend le même.</summary>
    public static Task RefreshAsync(IProgress<(int Done, int Total)>? progress = null)
    {
        if (_running is { IsCompleted: false }) return _running;
        return _running = RefreshCore(progress);
    }

    private static async Task RefreshCore(IProgress<(int Done, int Total)>? progress)
    {
        Scanning = true; Changed?.Invoke();
        try
        {
            var statuses = await Task.Run(() => Svc.Engine.Scan(Svc.Catalog, progress));
            foreach (var s in statuses) Find(s.Op.Id)?.Update(s);
            LastScan = DateTime.Now;
        }
        catch (Exception ex) { Log.Write("Scan : " + ex); }
        finally { Scanning = false; Changed?.Invoke(); }
    }
}
