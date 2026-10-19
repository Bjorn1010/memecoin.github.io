using System.Globalization;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;

namespace Blatja.App.Controls;

/// <summary>
/// Graphique temporel : historique réel, axes avec unités, infobulle au survol, trous là où la mesure manque.
/// Redessiné uniquement quand de nouvelles données arrivent (aucune animation permanente).
/// </summary>
public sealed class LiveChart : FrameworkElement
{
    private IReadOnlyList<(DateTime T, double V)> _pts = Array.Empty<(DateTime, double)>();
    private DateTime _now = DateTime.Now;
    private TimeSpan _window = TimeSpan.FromMinutes(1);
    private Point? _mouse;

    public string Unit { get; set; } = "%";
    /// <summary>Maximum fixe de l'axe ; 0 = échelle automatique (valeurs « rondes »).</summary>
    public double FixedMax { get; set; } = 100;
    public Color Accent { get; set; } = Color.FromRgb(0xFF, 0x5C, 0x50);
    public string EmptyText { get; set; } = "Indisponible";
    public string EmptyHint { get; set; } = "";
    public Typeface Face { get; set; } = new Typeface("Segoe UI");
    public Typeface FaceMono { get; set; } = new Typeface("Consolas");
    public int Decimals { get; set; }

    public LiveChart()
    {
        SnapsToDevicePixels = true;
        MouseMove += (_, e) => { _mouse = e.GetPosition(this); InvalidateVisual(); };
        MouseLeave += (_, _) => { _mouse = null; InvalidateVisual(); };
        Cursor = Cursors.Cross;
    }

    public void SetData(IReadOnlyList<(DateTime T, double V)> points, DateTime now, TimeSpan window)
    {
        _pts = points; _now = now; _window = window;
        InvalidateVisual();
    }

    private static readonly Brush Muted = Make(Color.FromRgb(0x7C, 0x84, 0x92));
    private static readonly Pen GridPen = MakePen(Color.FromRgb(0x20, 0x25, 0x2E), 1, dashed: true);
    private static Brush Make(Color c) { var b = new SolidColorBrush(c); b.Freeze(); return b; }
    private static Pen MakePen(Color c, double t, bool dashed = false)
    {
        var p = new Pen(Make(c), t);
        if (dashed) p.DashStyle = new DashStyle(new double[] { 2, 4 }, 0);
        p.Freeze(); return p;
    }

    private FormattedText Txt(string s, double size, Brush b, Typeface? f = null) =>
        new(s, CultureInfo.CurrentUICulture, FlowDirection.LeftToRight, f ?? Face, size, b, VisualTreeHelper.GetDpi(this).PixelsPerDip);

    private static double NiceMax(double v)
    {
        if (v <= 0) return 1;
        double mag = Math.Pow(10, Math.Floor(Math.Log10(v)));
        foreach (var m in new[] { 1, 2, 2.5, 5, 10 }) if (v <= m * mag) return m * mag;
        return 10 * mag;
    }

    private string Fmt(double v) => v.ToString("0." + new string('#', Decimals), CultureInfo.CurrentCulture) + (Unit == "%" ? " %" : " " + Unit);

    protected override void OnRender(DrawingContext dc)
    {
        double w = ActualWidth, h = ActualHeight;
        if (w < 120 || h < 70) return;
        const double left = 52, right = 12, top = 10, bottom = 26;
        double pw = w - left - right, ph = h - top - bottom;

        var valid = _pts.Where(p => !double.IsNaN(p.V)).ToList();
        double max = FixedMax > 0 ? FixedMax : NiceMax(valid.Count == 0 ? 1 : valid.Max(p => p.V) * 1.15);

        // grille + axe Y avec unités
        for (int i = 0; i <= 4; i++)
        {
            double y = top + ph * i / 4;
            dc.DrawLine(GridPen, new Point(left, y), new Point(w - right, y));
            double val = max * (4 - i) / 4;
            var t = Txt(i == 4 ? "0" : Fmt(val), 11.5, Muted, FaceMono);
            dc.DrawText(t, new Point(left - 8 - t.Width, y - t.Height / 2));
        }
        // axe X : temps relatif
        for (int i = 0; i <= 4; i++)
        {
            double sec = _window.TotalSeconds * (4 - i) / 4;
            string label = i == 4 ? "maint." : sec >= 60 ? $"-{sec / 60:0.#} min" : $"-{sec:0} s";
            var t = Txt(label, 11.5, Muted, FaceMono);
            double x = left + pw * i / 4;
            dc.DrawText(t, new Point(Math.Clamp(x - t.Width / 2, left - 10, w - right - t.Width), h - bottom + 7));
        }

        if (valid.Count == 0)
        {
            var t = Txt(EmptyText, 14, Muted);
            dc.DrawText(t, new Point(left + (pw - t.Width) / 2, top + ph / 2 - t.Height));
            if (EmptyHint.Length > 0)
            {
                var hint = Txt(EmptyHint, 12, Muted); hint.MaxTextWidth = Math.Max(80, pw - 40); hint.TextAlignment = TextAlignment.Center;
                dc.DrawText(hint, new Point(left + 20, top + ph / 2 + 4));
            }
            return;
        }

        // conversion en coordonnées, avec décimation si les points sont plus nombreux que les pixels
        int step = Math.Max(1, (int)(_pts.Count / (pw / 2)));
        var pos = new List<(Point P, double V, DateTime T)?>();
        for (int i = 0; i < _pts.Count; i += step)
        {
            var (t, v) = _pts[i];
            if (double.IsNaN(v)) { pos.Add(null); continue; }
            double x = left + pw - (_now - t).TotalSeconds / _window.TotalSeconds * pw;
            double y = top + ph * (1 - Math.Clamp(v / max, 0, 1));
            pos.Add((new Point(Math.Clamp(x, left, left + pw), y), v, t));
        }

        dc.PushClip(new RectangleGeometry(new Rect(left, 0, pw + 1, h)));
        var fill = new LinearGradientBrush(Color.FromArgb(70, Accent.R, Accent.G, Accent.B), Color.FromArgb(0, Accent.R, Accent.G, Accent.B), 90);
        fill.Freeze();
        var stroke = new Pen(new SolidColorBrush(Accent), 2) { LineJoin = PenLineJoin.Round, StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round };

        // un segment par série continue : les données manquantes restent visibles comme des trous
        var seg = new List<Point>();
        void Flush()
        {
            if (seg.Count >= 2)
            {
                var line = Curve(seg, top, top + ph, closeToBottom: false);
                var area = Curve(seg, top, top + ph, closeToBottom: true);
                dc.DrawGeometry(fill, null, area);
                dc.DrawGeometry(null, stroke, line);
            }
            else if (seg.Count == 1) dc.DrawEllipse(stroke.Brush, null, seg[0], 2, 2);
            seg.Clear();
        }
        foreach (var p in pos) { if (p is null) Flush(); else seg.Add(p.Value.P); }
        Flush();
        dc.Pop();

        // infobulle : point réel le plus proche de la souris
        if (_mouse is { } m && m.X >= left && m.X <= left + pw)
        {
            var near = pos.Where(p => p is not null).Select(p => p!.Value).OrderBy(p => Math.Abs(p.P.X - m.X)).FirstOrDefault();
            if (near.P.X != 0 || near.V != 0)
            {
                dc.DrawLine(MakePen(Color.FromRgb(0x44, 0x4B, 0x5A), 1), new Point(near.P.X, top), new Point(near.P.X, top + ph));
                dc.DrawEllipse(Brushes.White, new Pen(new SolidColorBrush(Accent), 2), near.P, 4, 4);
                var l1 = Txt(Fmt(near.V), 13, Brushes.White);
                double ago = (_now - near.T).TotalSeconds;
                var l2 = Txt(ago < 3 ? "maintenant" : ago < 90 ? $"il y a {ago:0} s" : $"il y a {ago / 60:0.#} min", 11.5, Muted);
                double bw = Math.Max(l1.Width, l2.Width) + 20, bh = l1.Height + l2.Height + 14;
                double bx = near.P.X + 12 + bw > w - right ? near.P.X - 12 - bw : near.P.X + 12;
                double by = Math.Clamp(near.P.Y - bh / 2, top, top + ph - bh);
                dc.DrawRoundedRectangle(Make(Color.FromRgb(0x1B, 0x1F, 0x27)), MakePen(Color.FromRgb(0x33, 0x3A, 0x47), 1), new Rect(bx, by, bw, bh), 6, 6);
                dc.DrawText(l1, new Point(bx + 10, by + 6));
                dc.DrawText(l2, new Point(bx + 10, by + 6 + l1.Height));
            }
        }
    }

    private static StreamGeometry Curve(IReadOnlyList<Point> pts, double minY, double maxY, bool closeToBottom)
    {
        var g = new StreamGeometry();
        using (var ctx = g.Open())
        {
            if (closeToBottom)
            {
                ctx.BeginFigure(new Point(pts[0].X, maxY), true, true);
                ctx.LineTo(pts[0], false, false);
            }
            else ctx.BeginFigure(pts[0], false, false);
            for (int i = 0; i < pts.Count - 1; i++)
            {
                var p0 = i > 0 ? pts[i - 1] : pts[i]; var p1 = pts[i]; var p2 = pts[i + 1]; var p3 = i + 2 < pts.Count ? pts[i + 2] : p2;
                var c1 = new Point(p1.X + (p2.X - p0.X) / 6, Math.Clamp(p1.Y + (p2.Y - p0.Y) / 6, minY, maxY));
                var c2 = new Point(p2.X - (p3.X - p1.X) / 6, Math.Clamp(p2.Y - (p3.Y - p1.Y) / 6, minY, maxY));
                ctx.BezierTo(c1, c2, p2, !closeToBottom, true);
            }
            if (closeToBottom) ctx.LineTo(new Point(pts[^1].X, maxY), false, false);
        }
        g.Freeze();
        return g;
    }
}
