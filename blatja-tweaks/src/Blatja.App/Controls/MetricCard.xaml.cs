using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace Blatja.App.Controls;

/// <summary>Carte de mesure : valeur réelle (qui défile en douceur) ou « Indisponible » (jamais de valeur inventée).</summary>
public partial class MetricCard : UserControl
{
    public static readonly DependencyProperty NumberProperty = DependencyProperty.Register(
        nameof(Number), typeof(double), typeof(MetricCard), new PropertyMetadata(0.0, (d, _) => ((MetricCard)d).RenderNumber()));

    private string _suffix = "";
    private int _decimals;
    private bool _showingNumber;

    public MetricCard() { InitializeComponent(); SetUnavailable(null); }

    public double Number { get => (double)GetValue(NumberProperty); set => SetValue(NumberProperty, value); }
    public string Label { set => LabelText.Text = value; }
    public Geometry Icon { set => Ico.Data = value; }

    private void RenderNumber() { if (_showingNumber) ValueText.Text = Number.ToString("F" + _decimals, CultureInfo.CurrentCulture) + _suffix; }

    /// <summary>Valeur numérique : le chiffre et la barre glissent vers la nouvelle mesure.</summary>
    public void SetNumber(double value, string suffix, string sub, double? percent = null, int decimals = 0)
    {
        ValueText.Style = (Style)FindResource("Txt.Value"); ValueText.ClearValue(TextBlock.ForegroundProperty);
        _suffix = suffix; _decimals = decimals; SubText.Text = sub; ToolTip = null;
        if (!_showingNumber) { _showingNumber = true; BeginAnimation(NumberProperty, null); Number = value; RenderNumber(); }
        else BeginAnimation(NumberProperty, new DoubleAnimation(value, TimeSpan.FromMilliseconds(500)) { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } });
        Progress(percent);
    }

    public void SetValue(string value, string sub, double? percent = null)
    {
        _showingNumber = false; BeginAnimation(NumberProperty, null);
        ValueText.Style = (Style)FindResource("Txt.Value"); ValueText.ClearValue(TextBlock.ForegroundProperty);
        ValueText.Text = value; SubText.Text = sub; ToolTip = null;
        Progress(percent);
    }

    private void Progress(double? percent)
    {
        if (percent is { } p) { Bar.Visibility = Visibility.Visible; Anim.Smooth(Bar, Math.Clamp(p, 0, 100), 500); }
        else Bar.Visibility = Visibility.Collapsed;
    }

    public void SetUnavailable(string? reason)
    {
        _showingNumber = false; BeginAnimation(NumberProperty, null);
        ValueText.Style = (Style)FindResource("Txt.H2");
        ValueText.Foreground = (Brush)FindResource("Text3");
        ValueText.Text = "Indisponible";
        SubText.Text = reason ?? "";
        Bar.Visibility = Visibility.Collapsed;
        ToolTip = reason;
    }
}
