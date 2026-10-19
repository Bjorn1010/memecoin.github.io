using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Animation;

namespace Blatja.App.Controls;

/// <summary>Indicateur de chargement. L'animation ne tourne que lorsque le contrôle est visible.</summary>
public partial class Spinner : UserControl
{
    public Spinner() { InitializeComponent(); }

    private void OnVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (IsVisible) Rot.BeginAnimation(System.Windows.Media.RotateTransform.AngleProperty,
            new DoubleAnimation(0, 360, TimeSpan.FromSeconds(0.9)) { RepeatBehavior = RepeatBehavior.Forever });
        else Rot.BeginAnimation(System.Windows.Media.RotateTransform.AngleProperty, null);
    }
}
