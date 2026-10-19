using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace Blatja.App.Controls;

/// <summary>Carte de mesure : valeur réelle ou « Indisponible » (jamais de valeur inventée).</summary>
public partial class MetricCard : UserControl
{
    public MetricCard() { InitializeComponent(); SetUnavailable(null); }

    public string Label { set => LabelText.Text = value; }
    public Geometry Icon { set => Ico.Data = value; }

    public void SetValue(string value, string sub, double? percent = null)
    {
        ValueText.Style = (Style)FindResource("Txt.Value");
        ValueText.Text = value; SubText.Text = sub; ToolTip = null;
        if (percent is { } p) { Bar.Value = Math.Clamp(p, 0, 100); Bar.Visibility = Visibility.Visible; }
        else Bar.Visibility = Visibility.Collapsed;
    }

    public void SetUnavailable(string? reason)
    {
        ValueText.Style = (Style)FindResource("Txt.H2");
        ValueText.Foreground = (Brush)FindResource("Text3");
        ValueText.Text = "Indisponible";
        SubText.Text = reason ?? "";
        Bar.Visibility = Visibility.Collapsed;
        ToolTip = reason;
    }
}
