using System.ComponentModel;

namespace BlatjaTweaks;

public sealed class Tweak : INotifyPropertyChanged
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Description { get; init; }
    public required string Category { get; init; }
    public bool NeedsReboot { get; init; }

    public string Icon => Id switch
    {
        "power" => "⚡", "gamemode" => "🎮", "gamedvr" => "⏺", "hags" => "🧠", "timer" => "⏱",
        "prio" => "📈", "mmcss" => "🎯", "visual" => "✨", "mouse" => "🖱", "nagle" => "🌐",
        "fnprio" => "🔥", "fngpu" => "🖥", "fnini" => "🎨", _ => "•",
    };
    public required Action Apply { get; init; }
    public required Action Revert { get; init; }

    private bool _isOn;
    public bool IsOn
    {
        get => _isOn;
        set { if (_isOn != value) { _isOn = value; Notify(nameof(IsOn)); } }
    }

    private bool _applied;
    public bool Applied
    {
        get => _applied;
        set { if (_applied != value) { _applied = value; Notify(nameof(Applied)); } }
    }

    public event PropertyChangedEventHandler? PropertyChanged;
    private void Notify(string n) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
}
