using System.ComponentModel;

namespace Blatja.Core;

/// <summary>Opération + état RÉEL détecté + sélection de l'utilisateur. L'état ne dérive jamais de la sélection.</summary>
public sealed class OpVm : INotifyPropertyChanged
{
    public Operation Op { get; }
    public OpVm(Operation op) { Op = op; }

    private OpState _state = OpState.Unknown;
    private string? _detail;
    private bool _selected;
    private bool _busy;

    public OpState State { get => _state; private set { _state = value; Raise(nameof(State), nameof(StateText), nameof(StateKind), nameof(CanApply), nameof(CanRevert), nameof(ActionText)); } }
    public string? Detail { get => _detail; private set { _detail = value; Raise(nameof(Detail)); } }
    public bool IsSelected { get => _selected; set { _selected = value; Raise(nameof(IsSelected)); } }
    public bool Busy { get => _busy; set { _busy = value; Raise(nameof(Busy), nameof(CanApply), nameof(CanRevert)); } }

    public void Update(OpStatus s) { State = s.State; Detail = s.Detail; if (s.State is OpState.NotApplicable or OpState.Enabled) IsSelected = false; }

    // ── présentation ──
    public string Name => Op.Name;
    public string Description => Op.Description;
    public string Effect => Op.Effect;
    public string Drawbacks => Op.Drawbacks;
    public string Group => Op.Group;
    public string Category => Op.Category;
    public string IconKey => Op.Category switch
    {
        Categories.Gaming => "IconGamepad", Categories.Cpu => "IconCpu", Categories.Gpu => "IconGpu", Categories.Memory => "IconRam",
        Categories.Network => "IconNetwork", Categories.Storage => "IconStorage", _ => "IconTrash",
    };

    public string StateText => State switch
    {
        OpState.Enabled => "Activée", OpState.Disabled => "Désactivée", OpState.NotApplicable => "Non applicable",
        OpState.Error => "Erreur de détection", _ => "État inconnu",
    };
    /// <summary>success | neutral | warning | danger : sert de clé de style au badge.</summary>
    public string StateKind => State switch { OpState.Enabled => "success", OpState.Error => "danger", OpState.Unknown => "warning", _ => "neutral" };

    public string ImpactText => Op.Impact switch { Impact.None => "Aucun", Impact.Low => "Faible", Impact.Medium => "Moyen", _ => "Élevé" };
    public string RiskText => Op.Risk == Risk.Low ? "Faible" : "Moyen";
    public string RestartText => Op.Restart switch { RestartKind.Reboot => "Redémarrage requis", RestartKind.SignOut => "Reconnexion requise", _ => "" };
    public bool HasRestart => Op.Restart != RestartKind.None;
    public bool Recommended => Op.Recommended;
    public bool NeedsAdmin => Op.RequiresAdmin;

    public bool CanApply => State == OpState.Disabled && !Busy;
    public bool CanRevert => State == OpState.Enabled && !Busy;
    public string ActionText => State == OpState.Enabled ? "Restaurer" : "Appliquer";
    public bool IsApplicable => State != OpState.NotApplicable;

    public event PropertyChangedEventHandler? PropertyChanged;
    private void Raise(params string[] names) { foreach (var n in names) PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n)); }
}
