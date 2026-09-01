import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type AlphaRow, type Decision, type EquityPoint, type Fill, type Summary } from "./api";

const fmtMoney = (v: number | null | undefined) =>
  v == null || !isFinite(v) ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 });
const fmtPct = (v: number | null | undefined, digits = 2) =>
  v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(digits)}%`;
const fmtNum = (v: number | null | undefined, digits = 2) =>
  v == null || !isFinite(v) ? "—" : v.toFixed(digits);
const fmtTime = (ts: number) =>
  new Date(ts).toISOString().replace("T", " ").slice(0, 16);

function Stat({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad";
  hint?: string;
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone}`}>{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <header>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [fills, setFills] = useState<Fill[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [alphas, setAlphas] = useState<AlphaRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [s, e, f, d] = await Promise.all([
        api.summary(),
        api.equity(),
        api.fills(),
        api.decisions(),
      ]);
      setSummary(s);
      setEquity(e.equity);
      setFills(f.fills);
      setDecisions(d.decisions);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    refresh();
    api.alphas().then((a) => setAlphas(a.alphas)).catch(() => undefined);
    const timer = setInterval(refresh, 10_000);
    return () => clearInterval(timer);
  }, []);

  const m = summary?.metrics ?? {};
  const start = equity.length ? equity[0].equity : null;
  const now = equity.length ? equity[equity.length - 1].equity : null;
  const pnl = start && now ? now / start - 1 : null;

  const chartData = equity.map((p) => ({
    ts: p.ts,
    time: fmtTime(p.ts),
    equity: p.equity,
    drawdown: p.drawdown * 100,
    exposure: p.gross_exposure,
  }));

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>qt</h1>
          <span className="badge">PAPER ONLY — no exchange credentials exist in this system</span>
        </div>
        <div className="run">
          {summary?.run_id ?? "no run"}
          {error && <span className="error"> · {error}</span>}
        </div>
      </header>

      <div className="stats">
        <Stat label="Equity" value={fmtMoney(now)} />
        <Stat
          label="P&L"
          value={fmtPct(pnl)}
          tone={pnl == null ? "neutral" : pnl >= 0 ? "good" : "bad"}
        />
        <Stat label="Sharpe" value={fmtNum(m.sharpe)} hint="annualised, after costs" />
        <Stat
          label="Max drawdown"
          value={fmtPct(m.max_drawdown)}
          tone={(m.max_drawdown ?? 0) < -0.1 ? "bad" : "neutral"}
        />
        <Stat label="Fills" value={String(summary?.n_fills ?? 0)} />
        <Stat
          label="Costs paid"
          value={fmtMoney(summary?.total_costs)}
          hint="commission + spread + impact"
        />
      </div>

      <Panel title="Equity" subtitle="Marked every bar, after all modelled costs.">
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#5b8def" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#5b8def" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#232733" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#7d8598" }} minTickGap={60} />
            <YAxis
              tick={{ fontSize: 11, fill: "#7d8598" }}
              domain={["auto", "auto"]}
              tickFormatter={(v) => fmtMoney(v)}
              width={70}
            />
            <Tooltip
              contentStyle={{ background: "#12151d", border: "1px solid #232733", fontSize: 12 }}
              formatter={(v: number) => fmtMoney(v)}
            />
            <Area type="monotone" dataKey="equity" stroke="#5b8def" fill="url(#eq)" strokeWidth={1.6} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Drawdown" subtitle="Distance below the running peak — the constraint that actually binds.">
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#232733" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#7d8598" }} minTickGap={60} />
            <YAxis tick={{ fontSize: 11, fill: "#7d8598" }} width={70} tickFormatter={(v) => `${v.toFixed(0)}%`} />
            <Tooltip
              contentStyle={{ background: "#12151d", border: "1px solid #232733", fontSize: 12 }}
              formatter={(v: number) => `${v.toFixed(2)}%`}
            />
            <Line type="monotone" dataKey="drawdown" stroke="#e2606a" dot={false} strokeWidth={1.4} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <div className="grid">
        <Panel
          title="Decisions"
          subtitle="What the strategy asked for, what risk allowed, and why it was cut."
        >
          <table>
            <thead>
              <tr>
                <th>time</th>
                <th>symbol</th>
                <th>signal</th>
                <th>asked</th>
                <th>allowed</th>
                <th>risk note</th>
              </tr>
            </thead>
            <tbody>
              {decisions.slice(0, 30).map((d, i) => (
                <tr key={i}>
                  <td className="dim">{fmtTime(d.ts)}</td>
                  <td>{d.symbol}</td>
                  <td className={(d.signal ?? 0) >= 0 ? "good" : "bad"}>{fmtNum(d.signal, 3)}</td>
                  <td>{fmtNum(d.target_weight, 3)}</td>
                  <td>{fmtNum(d.allowed_weight, 3)}</td>
                  <td className="dim">{d.risk_reason || "—"}</td>
                </tr>
              ))}
              {!decisions.length && (
                <tr>
                  <td colSpan={6} className="dim">
                    no decisions recorded yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>

        <Panel title="Fills" subtitle="Every simulated execution, with its cost breakdown.">
          <table>
            <thead>
              <tr>
                <th>time</th>
                <th>symbol</th>
                <th>side</th>
                <th>notional</th>
                <th>price</th>
                <th>slip bps</th>
              </tr>
            </thead>
            <tbody>
              {fills.slice(0, 30).map((f, i) => (
                <tr key={i}>
                  <td className="dim">{fmtTime(f.ts)}</td>
                  <td>{f.symbol}</td>
                  <td className={f.side === "buy" ? "good" : "bad"}>{f.side}</td>
                  <td>{fmtMoney(f.notional)}</td>
                  <td>{fmtNum(f.price, 2)}</td>
                  <td className="dim">{fmtNum(f.slippage_bps, 1)}</td>
                </tr>
              ))}
              {!fills.length && (
                <tr>
                  <td colSpan={6} className="dim">
                    no fills yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>
      </div>

      <Panel title="Positions" subtitle="Current book.">
        <table>
          <thead>
            <tr>
              <th>symbol</th>
              <th>qty</th>
              <th>avg price</th>
            </tr>
          </thead>
          <tbody>
            {(summary?.positions ?? []).map((p) => (
              <tr key={p.symbol}>
                <td>{p.symbol}</td>
                <td className={p.qty >= 0 ? "good" : "bad"}>{fmtNum(p.qty, 4)}</td>
                <td>{fmtNum(p.avg_price, 2)}</td>
              </tr>
            ))}
            {!summary?.positions?.length && (
              <tr>
                <td colSpan={3} className="dim">
                  flat
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Panel>

      <Panel
        title="Alpha library"
        subtitle="Each signal and the economic mechanism it rests on. A rule with no mechanism is a data-mining result."
      >
        <table>
          <thead>
            <tr>
              <th>alpha</th>
              <th>family</th>
              <th>horizon</th>
              <th>rationale</th>
            </tr>
          </thead>
          <tbody>
            {alphas.map((a) => (
              <tr key={a.name}>
                <td>{a.name}</td>
                <td className="dim">{a.family}</td>
                <td className="dim">{a.horizon_bars}b</td>
                <td className="rationale">{a.rationale}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
