using System.Windows;
using System.Windows.Media;

namespace Blatja.App.Controls;

/// <summary>Propriétés attachées du design system : icône vectorielle et pastille de compteur.</summary>
public static class Ui
{
    public static readonly DependencyProperty IconProperty = DependencyProperty.RegisterAttached(
        "Icon", typeof(Geometry), typeof(Ui), new FrameworkPropertyMetadata(null));
    public static Geometry? GetIcon(DependencyObject o) => (Geometry?)o.GetValue(IconProperty);
    public static void SetIcon(DependencyObject o, Geometry? v) => o.SetValue(IconProperty, v);

    public static readonly DependencyProperty BadgeProperty = DependencyProperty.RegisterAttached(
        "Badge", typeof(string), typeof(Ui), new FrameworkPropertyMetadata(""));
    public static string GetBadge(DependencyObject o) => (string)o.GetValue(BadgeProperty);
    public static void SetBadge(DependencyObject o, string v) => o.SetValue(BadgeProperty, v);
}
