"""Command-line interface.

    qt ingest --symbols BTCUSDT,ETHUSDT --start 2021-01-01
    qt lake
    qt research BTCUSDT
    qt train BTCUSDT
    qt paper --venue coinbase_ws --symbols BTC-USD
    qt replay BTCUSDT --bars 2000
    qt serve
"""

from __future__ import annotations

import asyncio
import json
import warnings
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from .config import CONFIG

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

app = typer.Typer(add_completion=False, help="qt — free-data quant research and paper trading")
console = Console()


def _table(df: pd.DataFrame, title: str = "", max_rows: int = 50) -> None:
    if df is None or df.empty:
        console.print(f"[yellow]{title or 'result'}: empty[/yellow]")
        return
    t = Table(title=title, show_lines=False, header_style="bold cyan")
    for col in df.columns:
        t.add_column(str(col), overflow="fold")
    for _, row in df.head(max_rows).iterrows():
        t.add_row(*[f"{v:.4f}" if isinstance(v, float) else str(v) for v in row])
    console.print(t)
    if len(df) > max_rows:
        console.print(f"[dim]... {len(df) - max_rows} more rows[/dim]")


def _load_bars(symbol: str, venue: str = "binance", interval: str = "1h") -> pd.DataFrame:
    from .bars import klines_to_bars
    from .data import Catalog

    cat = Catalog()
    k = cat.read_indexed(f"klines_{interval}", venue, symbol)
    if k.empty:
        raise typer.BadParameter(
            f"no {interval} data for {symbol} in the lake — run `qt ingest --symbols {symbol}` first"
        )
    bars = klines_to_bars(k)
    bars.index = pd.to_datetime(bars["ts"], unit="ms", utc=True)
    bars.index.name = "dt"
    return bars


# ---------------------------------------------------------------------- data
@app.command()
def ingest(
    symbols: str = typer.Option("BTCUSDT,ETHUSDT,SOLUSDT", help="comma-separated"),
    interval: str = typer.Option("1h"),
    start: str = typer.Option("2021-01-01"),
    end: Optional[str] = typer.Option(None),
    market: str = typer.Option("spot", help="spot | um (USD-M perps)"),
    funding: bool = typer.Option(False, help="also download realised funding (perps only)"),
    macro: bool = typer.Option(False, help="also download cross-asset context from Stooq"),
) -> None:
    """Download free historical data into the lake (Binance archive; no API key)."""
    from .data import Catalog
    from .data.sources import binance_vision as bv
    from .data.sources import stooq

    CONFIG.ensure_dirs()
    cat = Catalog()
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    console.print(f"[cyan]downloading[/cyan] {syms} {interval} {market} from {start}")
    res = bv.ingest(cat, syms, interval=interval, start=start, end=end, market=market, with_funding=funding)
    _table(res, "ingested")

    if macro:
        console.print("[cyan]downloading[/cyan] cross-asset context from Stooq")
        _table(stooq.ingest(cat, start=start, end=end), "macro")


@app.command()
def lake() -> None:
    """Show what is stored in the data lake."""
    from .data import Catalog

    inv = Catalog().inventory()
    if inv.empty:
        console.print("[yellow]lake is empty — run `qt ingest`[/yellow]")
        return
    grouped = (
        inv.groupby(["dataset", "venue", "symbol"])
        .agg(months=("month", "count"), rows=("rows", "sum"), mb=("mb", "sum"),
             start=("start", "min"), end=("end", "max"))
        .reset_index()
    )
    _table(grouped, f"data lake ({CONFIG.lake_dir})")


@app.command()
def catalog_sql(query: str) -> None:
    """Run DuckDB SQL over the lake. Use lake('dataset','venue','SYMBOL') as the table."""
    from .data import Catalog

    _table(Catalog().sql(query), "query result")


# ------------------------------------------------------------------ research
@app.command()
def features() -> None:
    """List the registered feature groups."""
    from . import features as F

    reg = F.registry()
    df = pd.DataFrame(
        [
            {"group": n, "warmup": g.warmup, "tags": ", ".join(g.tags), "description": g.description}
            for n, g in sorted(reg.items())
        ]
    )
    _table(df, f"{len(reg)} feature groups")


@app.command()
def alphas() -> None:
    """List the alpha library with each alpha's stated economic rationale."""
    from . import alphas as A

    _table(A.describe(), f"{len(A.registry())} alphas")


@app.command()
def research(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    resample: Optional[str] = typer.Option(None, help="coarsen bars, e.g. 4h or 1D"),
    n_trials: int = typer.Option(20, help="configurations you have evaluated — used to deflate the Sharpe"),
) -> None:
    """Backtest the rule-based alpha ensemble against buy-and-hold, honestly costed."""
    import numpy as np

    from . import alphas as A
    from . import features as F
    from .backtest import BacktestConfig, buy_and_hold, compare, rule_backtest
    from .bars import bars_from_klines
    from .validation import bootstrap_returns, deflated_sharpe_ratio

    bars = _load_bars(symbol, venue, interval)
    if resample:
        bars = bars_from_klines(bars, resample)
        bars.index = pd.to_datetime(bars["ts"], unit="ms", utc=True)
        bars.index.name = "dt"

    bar_seconds = float(pd.Series(bars["ts"]).diff().median()) / 1000.0
    bars_per_year = 365 * 24 * 3600 / max(bar_seconds, 1.0)
    console.print(f"[cyan]{symbol}[/cyan] {bars.shape[0]} bars  {bars.index.min()} -> {bars.index.max()}")

    fm = F.build_features(bars, symbol=symbol)
    sig = A.compute_all(bars, fm.X, warn_missing=False)
    # Forward-return horizon for the IC: roughly one day of bars, whatever the
    # frequency. Hardcoding 24 would mean a 24-day horizon on daily bars.
    h = max(int(round(86_400 / max(bar_seconds, 1.0))), 1)
    fwd = np.log(bars["close"]).diff(h).shift(-h).reindex(fm.X.index)
    _table(A.alpha_report(sig, fwd, bars_per_year)[["alpha", "ic", "sharpe_gross", "hit_rate", "coverage"]],
           "alpha diagnostics (in-sample — orientation only)")

    combined, _ = A.combine(sig, fwd, A.EnsembleSpec(method="ic_weighted", window=720, shrinkage=0.5))
    bt_bars = bars.loc[fm.X.index]
    cfg = BacktestConfig(bars_per_year=bars_per_year)
    res = rule_backtest(bt_bars, combined, symbol=symbol, backtest_config=cfg)
    bench = buy_and_hold(bt_bars, cfg)

    tbl = compare({"ensemble": res, "buy_and_hold": bench}, bars_per_year).T
    keep = ["cagr", "annual_vol", "sharpe", "sortino", "max_drawdown", "turnover_annual",
            "cost_share_of_gross", "n_trades", "avg_slippage_bps", "total_return"]
    out = tbl.loc[[r for r in keep if r in tbl.index]].reset_index().rename(columns={"index": "metric"})
    _table(out, "performance")

    dsr = deflated_sharpe_ratio(res.returns, n_trials=n_trials, sr_variance=0.25, periods_per_year=bars_per_year)
    console.print(
        f"\n[bold]Deflated Sharpe[/bold]: sharpe={dsr['sharpe']:.2f}  "
        f"luck benchmark over {n_trials} trials={dsr['benchmark_sharpe']:.2f}  "
        f"DSR={dsr['deflated_sharpe']:.3f} -> [yellow]{dsr['verdict']}[/yellow]"
    )
    bs = bootstrap_returns(res.returns, n_samples=300, periods_per_year=bars_per_year)
    if not bs.sharpe.empty:
        console.print(
            f"bootstrap sharpe 5/50/95%: {bs.sharpe.quantile(.05):.2f} / "
            f"{bs.sharpe.quantile(.5):.2f} / {bs.sharpe.quantile(.95):.2f}   "
            f"max DD 5/50/95%: {bs.max_drawdown.quantile(.05):.1%} / "
            f"{bs.max_drawdown.quantile(.5):.1%} / {bs.max_drawdown.quantile(.95):.1%}"
        )


@app.command()
def walkforward(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    train_bars: int = typer.Option(8760),
    test_bars: int = typer.Option(2160),
    horizon: int = typer.Option(24, help="label horizon in bars"),
) -> None:
    """Retrain-and-trade simulation: the closest thing to a verdict this system gives."""
    from . import features as F
    from .backtest import BacktestConfig, buy_and_hold, compare
    from .backtest.walkforward import WalkForwardSpec, walk_forward
    from .labels import LabelSpec
    from .models import ModelSpec

    bars = _load_bars(symbol, venue, interval)
    bar_seconds = float(pd.Series(bars["ts"]).diff().median()) / 1000.0
    bars_per_year = 365 * 24 * 3600 / max(bar_seconds, 1.0)
    fm = F.build_features(bars, symbol=symbol)
    bt_bars = bars.loc[fm.X.index]

    console.print(f"[cyan]walk-forward[/cyan] {symbol}: train={train_bars} test={test_bars} bars")
    wf = walk_forward(
        bt_bars, fm.X,
        label_spec=LabelSpec(horizon_bars=horizon, pt_sl=(2.0, 1.0)),
        model_spec=ModelSpec(kind="lgbm", calibrate=False),
        wf_spec=WalkForwardSpec(train_bars=train_bars, test_bars=test_bars, embargo_bars=horizon * 2),
        backtest_config=BacktestConfig(bars_per_year=bars_per_year),
        symbol=symbol,
    )
    _table(wf.windows, "walk-forward windows")
    tbl = compare({"walkforward_ml": wf.backtest, "buy_and_hold": buy_and_hold(bt_bars)}, bars_per_year).T
    keep = ["cagr", "annual_vol", "sharpe", "max_drawdown", "turnover_annual",
            "cost_share_of_gross", "n_trades", "total_return"]
    _table(tbl.loc[[r for r in keep if r in tbl.index]].reset_index().rename(columns={"index": "metric"}),
           "performance")


@app.command()
def train(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    horizon: int = typer.Option(24),
    name: Optional[str] = typer.Option(None),
    importance: bool = typer.Option(False, help="also run MDA feature importance (slow)"),
) -> None:
    """Train a model on all available history and store it in the registry."""
    from . import features as F
    from .labels import LabelSpec, make_labels
    from .models import ModelRegistry, ModelSpec, QuantModel, build_dataset
    from .models.importance import mda_importance

    bars = _load_bars(symbol, venue, interval)
    fm = F.build_features(bars, symbol=symbol)
    labels = make_labels(bars.loc[fm.X.index], LabelSpec(horizon_bars=horizon, pt_sl=(2.0, 1.0)))
    ds = build_dataset(fm.X, labels, symbol)
    console.print(json.dumps(ds.summary(), indent=2, default=str))

    model = QuantModel(ModelSpec(kind="lgbm", calibrate=True)).fit(ds)
    rec = ModelRegistry().save(model, name=name or f"{symbol.lower()}-{interval}", symbol=symbol)
    console.print(f"[green]saved[/green] {rec.model_id} -> {rec.path}")

    if importance:
        console.print("[cyan]computing MDA importance (purged CV)...[/cyan]")
        imp = mda_importance(ds, n_splits=4, n_repeats=2)
        _table(imp.head(25), "top features by mean decrease accuracy")


@app.command()
def models() -> None:
    """List models in the registry."""
    from .models import ModelRegistry

    _table(ModelRegistry().table(), "model registry")


# ---------------------------------------------------------------------- live
@app.command()
def paper(
    venue: str = typer.Option("coinbase_ws", help="coinbase_ws | hyperliquid | coinbase | kraken"),
    symbols: str = typer.Option("BTC-USD"),
    interval: str = typer.Option("1m"),
    strategy: str = typer.Option("alpha_ensemble", help="alpha_ensemble | model | flat"),
    model_id: Optional[str] = typer.Option(None),
    equity: float = typer.Option(100_000.0),
    max_bars: Optional[int] = typer.Option(None, help="stop after N bars (useful for a smoke test)"),
    warmup: int = typer.Option(300, help="bars of history required before trading"),
) -> None:
    """Run the paper-trading loop. This system never places a real order."""
    from .live import AlphaEnsembleStrategy, FlatStrategy, LoopConfig, ModelStrategy, PaperTradingLoop, make_feed
    from .models import ModelRegistry

    syms = tuple(s.strip() for s in symbols.split(",") if s.strip())
    feed = make_feed(venue, syms, interval)

    if strategy == "model":
        if not model_id:
            raise typer.BadParameter("--model-id is required for the model strategy")
        model, _ = ModelRegistry().load(model_id)
        strat = ModelStrategy(model=model, warmup_bars=warmup)
    elif strategy == "flat":
        strat = FlatStrategy()
    else:
        strat = AlphaEnsembleStrategy(warmup_bars=warmup)

    cfg = LoopConfig(symbols=syms, interval=interval, starting_equity=equity)
    loop = PaperTradingLoop(feed, strat, cfg)
    console.print(f"[green]paper trading[/green] run_id={loop.run_id} venue={venue} symbols={syms}")
    console.print("[dim]PAPER ONLY — no exchange credentials exist in this codebase[/dim]")
    status = asyncio.run(loop.run(max_bars=max_bars))
    console.print(json.dumps(status, indent=2, default=str))


@app.command()
def replay(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    bars: int = typer.Option(2000, help="how many recent bars to replay"),
    strategy: str = typer.Option("alpha_ensemble"),
    warmup: int = typer.Option(1000),
) -> None:
    """Replay historical bars through the live loop — the live stack's integration test."""
    from .live import AlphaEnsembleStrategy, FlatStrategy, LoopConfig, PaperTradingLoop, ReplayFeed

    full = _load_bars(symbol, venue, interval)
    hist = full.tail(bars + warmup)
    seed, play = hist.iloc[:warmup], hist.iloc[warmup:]

    strat = FlatStrategy() if strategy == "flat" else AlphaEnsembleStrategy(warmup_bars=warmup)
    cfg = LoopConfig(symbols=(symbol,), interval=interval, verbose=False)
    loop = PaperTradingLoop(ReplayFeed(play, symbol), strat, cfg)
    # Backfill the warm-up window instead of replaying it bar by bar: identical state,
    # and it skips hundreds of feature computations that could only ever return 0.
    loop.seed_history(symbol, seed)

    console.print(
        f"[cyan]replaying[/cyan] {len(play)} bars of {symbol} through the live loop "
        f"(seeded with {len(seed)} bars of history)"
    )
    status = asyncio.run(loop.run())
    console.print(json.dumps(status, indent=2, default=str))


@app.command()
def serve(host: str = typer.Option("0.0.0.0"), port: int = typer.Option(8000)) -> None:
    """Serve the read-only monitoring API (and the dashboard, if built)."""
    import uvicorn

    console.print(f"[green]serving[/green] http://{host}:{port}")
    uvicorn.run("qt.api.server:app", host=host, port=port, log_level="info")


@app.command()
def status(run_id: Optional[str] = typer.Option(None)) -> None:
    """Summarise a paper-trading run from the state database."""
    from .live.state import Store

    st = Store(CONFIG.state_db)
    rid = run_id or st.latest_run_id()
    if rid is None:
        console.print("[yellow]no runs recorded[/yellow]")
        return
    _table(st.runs(), "runs")
    _table(st.positions_frame(rid), f"positions — {rid}")
    _table(st.fills(rid, 20), f"recent fills — {rid}")
    eq = st.equity_curve(rid)
    if not eq.empty:
        console.print(
            f"equity: start={eq['equity'].iloc[0]:,.0f} now={eq['equity'].iloc[-1]:,.0f} "
            f"({eq['equity'].iloc[-1] / eq['equity'].iloc[0] - 1:+.2%})  "
            f"max drawdown={eq['drawdown'].min():.2%}"
        )


# ------------------------------------------------------- quantitative methods
def _load_panel(symbols: str, interval: str, venue: str, resample: Optional[str]) -> pd.DataFrame:
    """Build a close-price panel from the lake."""
    syms = [x.strip().upper() for x in symbols.split(",") if x.strip()]
    closes = {}
    for sym in syms:
        bars = _load_bars(sym, venue, interval)
        closes[sym.replace("USDT", "")] = bars["close"]
    panel = pd.DataFrame(closes).dropna()
    if resample:
        panel = panel.resample(resample).last().dropna()
    return panel


@app.command()
def diagnose(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
) -> None:
    """Econometric diagnosis of one series: stationarity, memory, volatility structure."""
    import numpy as np

    from . import econometrics as E

    bars = _load_bars(symbol, venue, interval)
    close = bars["close"]
    ret = np.log(close).diff().dropna()
    console.print(f"[cyan]{symbol}[/cyan] {len(close)} bars {close.index.min()} -> {close.index.max()}")

    rep = E.stationarity_report(np.log(close))
    console.print(f"\n[bold]Stationarity of log price[/bold]: [yellow]{rep['verdict']}[/yellow]")
    console.print(f"  ADF p={rep['adf']['pvalue']:.4g}  KPSS p={rep['kpss']['pvalue']:.4g}")
    console.print(f"  {rep['advice']}")

    ffd = E.find_min_ffd(close)
    console.print(f"\n[bold]Fractional differencing[/bold]: {ffd['advice']}")

    rows = []
    for q in (2, 4, 8, 24):
        vr = E.variance_ratio_test(close, q=q)
        rows.append({"q": q, "variance_ratio": vr.statistic, "pvalue": vr.pvalue,
                     "reading": vr.interpretation})
    _table(pd.DataFrame(rows), "variance ratio (>1 trending, <1 mean-reverting)")

    console.print("\n[bold]Conditional volatility models[/bold]")
    cmp = E.compare_models(ret)
    keep = [c for c in ("model", "persistence", "half_life_of_shock_bars",
                        "long_run_annual_vol", "long_run_reliable", "bic") if c in cmp.columns]
    _table(cmp[keep], "GARCH family (lower BIC is better)")


@app.command()
def pairs(
    symbols: str = typer.Option("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,DOGEUSDT,LTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    resample: Optional[str] = typer.Option("1D", help="coarsen before testing"),
    cost: float = typer.Option(0.0012, help="round-trip cost as a decimal"),
    max_half_life: float = typer.Option(60.0, help="in bars of the resampled frequency"),
) -> None:
    """Screen every pair for cointegration, then ask whether it is tradeable after costs."""
    from . import strategies as St

    panel = _load_panel(symbols, interval, venue, resample)
    console.print(f"[cyan]panel[/cyan] {panel.shape[1]} assets x {len(panel)} bars")

    res = St.screen_and_analyse(panel, round_trip_cost=cost, max_half_life=max_half_life)
    n_tests = res.attrs.get("n_tests")
    corrected = res.attrs.get("corrected_alpha")
    console.print(
        f"tested {n_tests} pairs -> Bonferroni-corrected alpha = {corrected:.5f}"
    )
    cols = [c for c in ("pair", "pvalue", "passes_corrected", "half_life_bars",
                        "entry_z", "expected_annual_return", "tradeable") if c in res.columns]
    _table(res[cols].head(15), "pair screen")
    console.print(
        f"\n[bold]cointegrated:[/bold] {int(res['passes_corrected'].sum())}  "
        f"[bold]tradeable after costs:[/bold] {int(res['tradeable'].sum())}"
    )
    if int(res["tradeable"].sum()) == 0 and "reasons" in res.columns:
        console.print("\n[dim]why every candidate was rejected:[/dim]")
        for reason, count in res["reasons"].value_counts().head(4).items():
            console.print(f"  [dim]{count:2d}x {str(reason)[:100]}[/dim]")


@app.command()
def allocate(
    symbols: str = typer.Option("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,DOGEUSDT,LTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
) -> None:
    """Compare portfolio optimisers and decompose the risk of the resulting books."""
    import numpy as np

    from . import portfolio as P

    panel = _load_panel(symbols, interval, venue, None)
    rets = np.log(panel).diff().dropna()
    console.print(f"[cyan]panel[/cyan] {rets.shape[1]} assets x {len(rets)} bars")

    rep = P.covariance_report(rets, annualise=365 * 24)
    _table(rep["table"], "covariance estimators")
    console.print(
        f"Ledoit-Wolf shrinkage {rep['shrinkage_intensity']:.3f} | "
        f"{rep['n_significant_factors']} of {rep['n_assets']} eigenvalues exceed the "
        f"Marchenko-Pastur noise band | market factor = {rep['market_factor_share']:.1%} of variance"
    )

    cov, _ = P.ledoit_wolf_covariance(rets, annualise=365 * 24)
    _table(P.compare_optimisers(rets, cov).reset_index().round(4), "optimisers")

    ew = P.equal_weight(cov.index)
    rr = P.risk_report(ew, cov, rets, periods_per_year=365 * 24)
    console.print(
        f"\n[bold]Equal-weight book:[/bold] {rr['n_positions']} positions, but only "
        f"[yellow]{rr['effective_n_bets']:.2f} effective bets[/yellow] "
        f"(diversification ratio {rr['diversification_ratio']:.2f})"
    )
    console.print(
        f"  annual vol {rr['portfolio_vol_annual']:.1%} | VaR95 {rr['var_historical']:.2%} | "
        f"CVaR {rr['cvar']:.2%} | tail fatness {rr.get('tail_fatness', float('nan')):.2f}x"
    )
    st = P.stress_test(ew, rets)
    if not st.empty:
        _table(st.round(4), "historical stress scenarios")


@app.command()
def execution(
    quantity: float = typer.Option(1000.0),
    n_steps: int = typer.Option(20),
    volatility: float = typer.Option(1.0, help="price sd per step"),
    impact: float = typer.Option(1e-3, help="temporary impact per unit per step"),
) -> None:
    """Almgren-Chriss optimal execution frontier: expected cost against its variance."""
    import numpy as np

    from . import execution as X

    frontier = X.efficient_frontier(
        quantity, n_steps, volatility=volatility, temporary_impact=impact,
        risk_aversions=np.logspace(-6, -1, 10),
    )
    _table(frontier.round(4), "execution efficient frontier")
    console.print(
        "[dim]risk aversion 0 gives TWAP; higher aversion front-loads the trade, "
        "paying more expected cost to remove variance[/dim]"
    )


@app.command()
def vol_surface(
    spot: float = typer.Option(100.0),
    expiry_days: float = typer.Option(90.0),
    atm_vol: float = typer.Option(0.6),
    skew: float = typer.Option(-0.18, help="negative = downside skew"),
) -> None:
    """Fit SVI, Heston and Merton to a smile and compare what each explains."""
    import numpy as np

    from . import derivatives as D

    T = expiry_days / 365.0
    k = np.linspace(-0.4, 0.4, 15)
    market = atm_vol + 0.35 * k**2 + skew * k

    svi = D.fit_svi(k, market, T)
    console.print(f"[bold]SVI[/bold]  ATM {svi.implied_vol(0.0):.4f}  skew {svi.skew(0.0):+.4f}")
    console.print(f"  arbitrage-free: {svi.is_arbitrage_free()['arbitrage_free']}")
    console.print(f"  variance-swap fair vol (±1.5 wings): {D.variance_swap_strike(svi, width=1.5):.4f}")

    strikes = spot * np.exp(k)
    heston = D.calibrate_heston(strikes, market, spot, T, 0.0)
    _table(pd.DataFrame([{k2: round(v, 4) if isinstance(v, float) else v
                          for k2, v in heston.to_dict().items()}]), "Heston parameters")

    merton = D.calibrate_merton(strikes, market, spot, T, 0.0)
    _table(pd.DataFrame([{k2: round(v, 4) if isinstance(v, float) else v
                          for k2, v in merton.to_dict().items()}]), "Merton jump parameters")
    console.print(
        "[dim]rho drives skew (Heston); jump intensity drives the short-dated wings "
        "that a pure diffusion cannot reach[/dim]"
    )


# ------------------------------------------------------- deep history & sizing
@app.command()
def deep_history(
    symbols: str = typer.Option("BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,ADAUSDT,LTCUSDT,DOGEUSDT,SOLUSDT,AVAXUSDT,LINKUSDT"),
    interval: str = typer.Option("1d"),
    bitstamp: bool = typer.Option(True, help="also pull Bitstamp, which reaches back to 2011"),
    macro: bool = typer.Option(True, help="also pull cross-asset context from Stooq"),
) -> None:
    """Download EVERY bar each venue has, back to each symbol's listing date.

    The default 'from 2021' is a quiet methodological choice and a bad one: a model
    validated on 2021-2024 has seen exactly one regime transition.
    """
    from .data import Catalog, coverage_report, ingest_deep_crypto, ingest_full_history, ingest_macro

    CONFIG.ensure_dirs()
    cat = Catalog()
    syms = [x.strip().upper() for x in symbols.split(",") if x.strip()]

    console.print(f"[cyan]probing listing dates and downloading[/cyan] {len(syms)} symbols at {interval}")
    _table(ingest_full_history(cat, syms, interval=interval), "Binance, from listing")

    if bitstamp:
        console.print("[cyan]Bitstamp[/cyan] — the deepest free crypto history (2011+)")
        _table(ingest_deep_crypto(cat, interval=interval), "Bitstamp")
    if macro:
        console.print("[cyan]Stooq[/cyan] — cross-asset context")
        _table(ingest_macro(cat), "macro")

    _table(coverage_report(cat), "coverage — read the `years` column before trusting a backtest")


@app.command()
def import_tradingview(
    path: str = typer.Argument(..., help="a CSV exported from a TradingView chart, or a directory"),
    interval: str = typer.Option("1d"),
) -> None:
    """Import chart data you exported from your own TradingView account.

    TradingView publishes no free historical API — it licenses most of its data and
    cannot redistribute it. Exporting from your own charts is the legitimate route;
    for depth, `qt deep-history` reaches further than TradingView's own coverage.
    """
    from pathlib import Path as _Path

    from .data import Catalog
    from .data.sources import tradingview as tv

    cat = Catalog()
    target = _Path(path)
    if target.is_dir():
        _table(tv.import_directory(target, cat, interval=interval), "imported")
    else:
        df = tv.read_csv(target, catalog=cat, interval=interval)
        console.print(f"[green]imported[/green] {len(df)} bars from {target.name}")


@app.command()
def sizing(
    win_rate: float = typer.Option(0.50, help="probability of a winning bet"),
    payoff: float = typer.Option(1.0, help="average win divided by average loss"),
    n_bets: int = typer.Option(1000),
    n_paths: int = typer.Option(2000),
) -> None:
    """Measure what every bet-sizing progression actually does. Martingale included.

    Read `ruin_rate` and `p05_final`, not the median — every progression looks fine at
    the median, and the gap between the median and the 5th percentile is the subject.
    """
    from . import sizing as Z

    console.print("[bold]Martingale capital requirement[/bold] (100-unit base)")
    table = Z.martingale_capital_table(base_unit=100.0, max_losses=12)
    _table(
        table[["n_consecutive_losses", "next_stake", "capital_required",
               "probability_at_50pct", "days_until_expected_at_20_per_day"]],
        "capital needed vs how often you need it",
    )

    edge = win_rate * payoff - (1 - win_rate)
    console.print(
        f"\n[bold]Monte Carlo[/bold]: win rate {win_rate:.0%}, payoff {payoff}, "
        f"edge per bet {edge:+.4f} over {n_bets} bets x {n_paths} paths"
    )
    res = Z.compare_progressions(win_rate=win_rate, payoff=payoff, n_bets=n_bets, n_paths=n_paths)
    _table(res.reset_index().round(4), "progressions")

    k = Z.kelly_fraction(win_rate, payoff)
    if k["full_kelly"] and k["full_kelly"] > 0:
        console.print(
            f"\n[bold]Kelly[/bold]: full {k['full_kelly']:.3f}, quarter {k['fractional_kelly']:.3f} "
            f"(keeps {k['growth_retained']:.0%} of the growth)"
        )
        _table(Z.sizing_report(win_rate, payoff).round(4), "how much to bet")
    else:
        console.print(
            "\n[yellow]No edge: Kelly is zero or negative. No sizing rule creates edge — "
            "sizing scales outcomes, it does not manufacture them.[/yellow]"
        )


@app.command()
def regimes(
    symbol: str = typer.Argument("BTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    n_states: int = typer.Option(2),
) -> None:
    """Fit a Markov-switching model and show what the market's regimes actually are."""
    import numpy as np

    from . import econometrics as E

    bars = _load_bars(symbol, venue, interval)
    ret = np.log(bars["close"]).diff().dropna()
    console.print(f"[cyan]{symbol}[/cyan] {len(ret)} returns")

    fit = E.fit_regimes(ret, n_states=n_states)
    _table(fit.summary().reset_index().rename(columns={"index": "state"}).round(6),
           f"{n_states} fitted regimes")
    _table(fit.transition_matrix.round(4).reset_index().rename(columns={"index": "from"}),
           "transition matrix")
    console.print(
        f"converged={fit.converged}  loglik={fit.loglikelihood:.0f}  "
        f"current state={fit.labels.get(fit.current_state(), fit.current_state())}"
    )


@app.command()
def allocate_backtest(
    symbols: str = typer.Option("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,DOGEUSDT,LTCUSDT"),
    interval: str = typer.Option("1h"),
    venue: str = typer.Option("binance"),
    lookback: int = typer.Option(720),
    rebalance_every: int = typer.Option(168),
) -> None:
    """Trade every portfolio optimiser through the engine, with costs.

    The column that decides the winner is not `sharpe` but `turnover_annual` next to
    `cost_share_of_gross`. An optimiser that wins before costs and churns has not won.
    """
    from .backtest import AllocationSpec, BacktestConfig, compare_allocations

    syms = [x.strip().upper() for x in symbols.split(",") if x.strip()]
    prices = {}
    for sym in syms:
        prices[sym.replace("USDT", "")] = _load_bars(sym, venue, interval)

    bar_seconds = float(pd.Series(next(iter(prices.values()))["ts"]).diff().median()) / 1000.0
    bars_per_year = 365 * 24 * 3600 / max(bar_seconds, 1.0)

    console.print(f"[cyan]panel[/cyan] {len(prices)} assets x {len(next(iter(prices.values())))} bars")
    spec = AllocationSpec(lookback=lookback, rebalance_every=rebalance_every)
    table = compare_allocations(prices, spec=spec, config=BacktestConfig(bars_per_year=bars_per_year))
    _table(table.reset_index().round(4), "allocators, traded, after costs")


if __name__ == "__main__":
    app()
