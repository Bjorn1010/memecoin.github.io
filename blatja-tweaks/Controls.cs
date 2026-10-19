using System.Globalization;
using System.Windows;
using System.Windows.Media;

namespace BlatjaTweaks;

/// <summary>Anneau de jauge dessiné directement (animable via la propriété Value).</summary>
public sealed class RingGauge : FrameworkElement
{
    public static readonly DependencyProperty ValueProperty = DependencyProperty.Register(
        nameof(Value), typeof(double), typeof(RingGauge), new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.AffectsRender));
    public static readonly DependencyProperty AccentProperty = DependencyProperty.Register(
        nameof(Accent), typeof(Brush), typeof(RingGauge), new FrameworkPropertyMetadata(Brushes.Red, FrameworkPropertyMetadataOptions.AffectsRender));
    public static readonly DependencyProperty ThicknessProperty = DependencyProperty.Register(
        nameof(Thickness), typeof(double), typeof(RingGauge), new FrameworkPropertyMetadata(8.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double Value { get => (double)GetValue(ValueProperty); set => SetValue(ValueProperty, value); }
    public Brush Accent { get => (Brush)GetValue(AccentProperty); set => SetValue(AccentProperty, value); }
    public double Thickness { get => (double)GetValue(ThicknessProperty); set => SetValue(ThicknessProperty, value); }

    protected override void OnRender(DrawingContext dc)
    {
        double t = Thickness, size = Math.Min(ActualWidth, ActualHeight);
        if (size <= t) return;
        var c = new Point(ActualWidth / 2, ActualHeight / 2);
        double r = (size - t) / 2;

        dc.DrawEllipse(null, new Pen(new SolidColorBrush(Color.FromRgb(0x24, 0x21, 0x28)), t), c, r, r);

        double v = Math.Clamp(Value, 0, 100) / 100;
        if (v < 0.004) return;
        double sweep = Math.Min(v, 0.9995) * 2 * Math.PI, start = -Math.PI / 2;
        var p0 = new Point(c.X + r * Math.Cos(start), c.Y + r * Math.Sin(start));
        var p1 = new Point(c.X + r * Math.Cos(start + sweep), c.Y + r * Math.Sin(start + sweep));
        var g = new StreamGeometry();
        using (var ctx = g.Open())
        {
            ctx.BeginFigure(p0, false, false);
            ctx.ArcTo(p1, new Size(r, r), 0, sweep > Math.PI, SweepDirection.Clockwise, true, false);
        }
        g.Freeze();
        dc.DrawGeometry(null, new Pen(Accent, t) { StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round }, g);
    }
}

/// <summary>Courbe en direct : aire dégradée, courbe lissée, grille, repère de valeur. Défile en continu.</summary>
public sealed class LiveChart : FrameworkElement
{
    public IList<double>? Source { get; set; }
    public string Unit { get; set; } = "%";
    public double Max { get; set; } = 100;
    public Color Accent { get; set; } = Color.FromRgb(0xFF, 0x3B, 0x52);
    public double Phase { get; set; }
    public Typeface Face { get; set; } = new Typeface("Segoe UI");

    private static readonly Brush Muted = Freeze(new SolidColorBrush(Color.FromRgb(0x7A, 0x75, 0x80)));
    private static readonly Pen Grid = FreezePen(new Pen(new SolidColorBrush(Color.FromRgb(0x25, 0x22, 0x29)), 1) { DashStyle = new DashStyle(new double[] { 2, 4 }, 0) });

    private static Brush Freeze(Brush b) { b.Freeze(); return b; }
    private static Pen FreezePen(Pen p) { p.Brush.Freeze(); p.Freeze(); return p; }

    private FormattedText Text(string s, double size, Brush b) =>
        new(s, CultureInfo.CurrentUICulture, FlowDirection.LeftToRight, Face, size, b, VisualTreeHelper.GetDpi(this).PixelsPerDip);

    protected override void OnRender(DrawingContext dc)
    {
        double w = ActualWidth, h = ActualHeight;
        if (w < 80 || h < 60) return;
        const double left = 46, bottom = 24, top = 8, right = 10;
        double pw = w - left - right, ph = h - top - bottom;

        // grille + libellés de l'axe Y
        for (int i = 0; i <= 5; i++)
        {
            double y = top + ph * i / 5;
            dc.DrawLine(Grid, new Point(left, y), new Point(w - right, y));
            var t = Text($"{Max * (5 - i) / 5:0}{(i == 5 ? "" : Unit)}", 11, Muted);
            dc.DrawText(t, new Point(left - 8 - t.Width, y - t.Height / 2));
        }
        string[] xs = { "60 s", "45 s", "30 s", "15 s", "maint." };
        for (int i = 0; i < xs.Length; i++)
        {
            var t = Text(xs[i], 11, Muted);
            double x = left + pw * i / 4;
            dc.DrawText(t, new Point(Math.Min(x - t.Width / 2, w - right - t.Width), h - bottom + 6));
        }

        var src = Source;
        if (src is null || src.Count < 2) return;

        // points : le plus récent à droite, décalé en continu par Phase (0..1 s)
        var pts = new List<Point>();
        int n = src.Count;
        double step = pw / (Metrics.History - 1);
        for (int k = 0; k < n; k++)
        {
            double age = (n - 1 - k) + Phase;
            double x = left + pw - age * step;
            double y = top + ph * (1 - Math.Clamp(src[k] / Max, 0, 1));
            pts.Add(new Point(x, y));
        }
        pts.Add(new Point(left + pw, pts[^1].Y));   // tête tenue jusqu'au bord

        dc.PushClip(new RectangleGeometry(new Rect(left, 0, pw + 1, h)));

        var line = new StreamGeometry();
        using (var ctx = line.Open())
        {
            ctx.BeginFigure(pts[0], false, false);
            for (int i = 0; i < pts.Count - 1; i++)
            {
                var p0 = i > 0 ? pts[i - 1] : pts[i];
                var p1 = pts[i]; var p2 = pts[i + 1];
                var p3 = i + 2 < pts.Count ? pts[i + 2] : p2;
                var c1 = new Point(p1.X + (p2.X - p0.X) / 6, Math.Clamp(p1.Y + (p2.Y - p0.Y) / 6, top, top + ph));
                var c2 = new Point(p2.X - (p3.X - p1.X) / 6, Math.Clamp(p2.Y - (p3.Y - p1.Y) / 6, top, top + ph));
                ctx.BezierTo(c1, c2, p2, true, true);
            }
        }
        line.Freeze();

        var area = new StreamGeometry();
        using (var ctx = area.Open())
        {
            ctx.BeginFigure(new Point(pts[0].X, top + ph), true, true);
            ctx.LineTo(pts[0], false, false);
            for (int i = 0; i < pts.Count - 1; i++)
            {
                var p0 = i > 0 ? pts[i - 1] : pts[i];
                var p1 = pts[i]; var p2 = pts[i + 1];
                var p3 = i + 2 < pts.Count ? pts[i + 2] : p2;
                var c1 = new Point(p1.X + (p2.X - p0.X) / 6, Math.Clamp(p1.Y + (p2.Y - p0.Y) / 6, top, top + ph));
                var c2 = new Point(p2.X - (p3.X - p1.X) / 6, Math.Clamp(p2.Y - (p3.Y - p1.Y) / 6, top, top + ph));
                ctx.BezierTo(c1, c2, p2, false, true);
            }
            ctx.LineTo(new Point(pts[^1].X, top + ph), false, false);
        }
        area.Freeze();

        var fill = new LinearGradientBrush(Color.FromArgb(110, Accent.R, Accent.G, Accent.B), Color.FromArgb(0, Accent.R, Accent.G, Accent.B), 90);
        fill.Freeze();
        dc.DrawGeometry(fill, null, area);
        var stroke = new Pen(new SolidColorBrush(Accent), 2.4) { LineJoin = PenLineJoin.Round, StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round };
        dc.DrawGeometry(null, stroke, line);
        dc.Pop();

        // repère sur la valeur courante
        var head = pts[^1];
        dc.DrawEllipse(new SolidColorBrush(Color.FromArgb(50, Accent.R, Accent.G, Accent.B)), null, head, 9, 9);
        dc.DrawEllipse(Brushes.White, new Pen(new SolidColorBrush(Accent), 2.5), head, 4.5, 4.5);

        var label = Text($"{src[^1]:0}{Unit}", 12.5, Brushes.White);
        var box = new Rect(head.X - label.Width - 26, Math.Max(top, head.Y - 38), label.Width + 18, label.Height + 8);
        dc.DrawRoundedRectangle(new SolidColorBrush(Color.FromRgb(0x1A, 0x17, 0x1D)), new Pen(new SolidColorBrush(Color.FromRgb(0x38, 0x33, 0x3E)), 1), box, 6, 6);
        dc.DrawText(label, new Point(box.X + 9, box.Y + 4));
    }
}
