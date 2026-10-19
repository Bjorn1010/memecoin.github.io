using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;

namespace Blatja.App.Controls;

/// <summary>Micro-animations courtes (aucune animation permanente) : apparition en cascade, « pop », compteurs.</summary>
public static class Anim
{
    private static readonly IEasingFunction Out = new CubicEase { EasingMode = EasingMode.EaseOut };
    private static readonly IEasingFunction Back = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.7 };

    /// <summary>Fait apparaître les éléments l'un après l'autre (fondu + léger glissement vers le haut).</summary>
    public static void Reveal(IEnumerable<UIElement> elements, int stepMs = 45, double dy = 12, int durMs = 340)
    {
        int i = 0;
        foreach (var e in elements)
        {
            int delay = Math.Min(i * stepMs, 420);
            i++;
            e.Opacity = 0;
            TranslateTransform? move = null;
            if (e.RenderTransform is TranslateTransform t && !t.IsFrozen) move = t;
            else if (e.RenderTransform is null || e.RenderTransform == Transform.Identity) { move = new TranslateTransform(0, dy); e.RenderTransform = move; }
            move?.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(dy, 0, TimeSpan.FromMilliseconds(durMs)) { BeginTime = TimeSpan.FromMilliseconds(delay), EasingFunction = Out });

            var fade = new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(durMs - 80)) { BeginTime = TimeSpan.FromMilliseconds(delay), EasingFunction = Out };
            var target = e;
            fade.Completed += (_, _) => { target.BeginAnimation(UIElement.OpacityProperty, null); target.Opacity = 1; };
            e.BeginAnimation(UIElement.OpacityProperty, fade);
        }
    }

    /// <summary>Révèle les blocs principaux d'une page (enfants du panneau défilant), en ignorant les listes gérées à part.</summary>
    public static void RevealContent(FrameworkElement page, Func<UIElement, bool>? skip = null)
    {
        var scroll = Descendants<ScrollViewer>(page).FirstOrDefault();
        var panel = scroll?.Content as Panel;
        if (panel is null) return;
        Reveal(panel.Children.Cast<UIElement>().Where(c => c.Visibility == Visibility.Visible && (skip is null || !skip(c))));
    }

    public static IEnumerable<T> Descendants<T>(DependencyObject root) where T : DependencyObject
    {
        int n = VisualTreeHelper.GetChildrenCount(root);
        for (int i = 0; i < n; i++)
        {
            var c = VisualTreeHelper.GetChild(root, i);
            if (c is T t) yield return t;
            foreach (var d in Descendants<T>(c)) yield return d;
        }
    }

    /// <summary>Effet « pop » : l'élément grossit légèrement avec un petit rebond.</summary>
    public static void Pop(UIElement e, double from = 0.6, int ms = 360)
    {
        e.RenderTransformOrigin = new Point(0.5, 0.5);
        var s = new ScaleTransform(from, from);
        e.RenderTransform = s;
        var a = new DoubleAnimation(from, 1, TimeSpan.FromMilliseconds(ms)) { EasingFunction = Back };
        s.BeginAnimation(ScaleTransform.ScaleXProperty, a);
        s.BeginAnimation(ScaleTransform.ScaleYProperty, a);
    }

    /// <summary>Anime une barre de progression vers une valeur (sans saut).</summary>
    public static void Smooth(ProgressBar bar, double to, int ms = 320) =>
        bar.BeginAnimation(System.Windows.Controls.Primitives.RangeBase.ValueProperty, new DoubleAnimation(to, TimeSpan.FromMilliseconds(ms)) { EasingFunction = Out });
}
