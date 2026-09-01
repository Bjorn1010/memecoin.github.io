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


if __name__ == "__main__":
    app()
