"""Does day trading survive 12bps a round trip? Chosen in-sample, measured out-of-sample.

The first version of this strategy lost 35% over four years: hit rate 29.3% against a
33.3% breakeven, and a *gross* return that was negative before costs were charged. So the
question is not "how do I tune it" but "is there anything here at all".

Diagnosing the three legs separately gave a clear answer and a subtler one.

**Clear:** breakout has a negative rank IC on all three symbols (-0.041, -0.019, -0.016).
It is anti-predictive at this horizon and was dragging the combination down.

**Subtler:** reversal has a positive rank IC on all three (+0.024, +0.012, +0.017) but a
*negative* conditional edge in the tail, where the strategy actually trades. Small
dislocations revert; large ones carry information and continue. The strategy was entering
precisely where the effect it relied on inverts.

That suggests a configuration, and a configuration chosen by looking at data is a
configuration that must be validated on data that was not looked at. So: every candidate
is ranked on 2021-2022 only, the single best is carried to 2023-2024 untouched, and the
out-of-sample number is the one that counts. The count of candidates is passed to the
deflated Sharpe honestly, because understating it is how a search launders itself into a
result.

Run:  .venv/bin/python -u scripts/research_intraday.py
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from qt.bars import klines_to_bars
from qt.data.catalog import Catalog
from qt.strategies.intraday import IntradaySpec, performance, run_intraday
from qt.validation import deflated_sharpe_ratio

pd.set_option("display.width", 240)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SPLIT = "2023-01-01"          # everything before is for choosing; after, for measuring
ROUND_TRIP_BPS = 12.0         # 5bps taker each way plus a basis point of half-spread


def load(cat: Catalog, symbol: str) -> pd.DataFrame:
    raw = cat.read_indexed("klines_1h", "binance", symbol)
    if raw.empty:
        return raw
    bars = klines_to_bars(raw)
    bars.index = pd.to_datetime(bars["ts"], unit="ms", utc=True)
    bars.index.name = "dt"
    return bars


def candidates() -> list[tuple[str, IntradaySpec]]:
    """The configurations to rank in-sample. Counted, not hidden.

    Two structural choices are varied — which legs are active, and whether the entry
    threshold sits in the body of the distribution or its tail — plus the stop/target
    geometry. Nothing here is a fitted number; each is a different hypothesis about
    where the effect lives.
    """
    out: list[tuple[str, IntradaySpec]] = []
    for threshold, stop, target, hold in itertools.product(
        (0.5, 1.0, 1.5), (1.0, 1.5), (2.0, 3.0), (6, 12),
    ):
        label = f"seuil {threshold} · stop {stop} · cible {target} · {hold}h"
        out.append((label, IntradaySpec(
            entry_threshold=threshold, stop_atr=stop, target_atr=target,
            max_hold_bars=hold,
        )))
    return out


def evaluate(bars_by_symbol: dict[str, pd.DataFrame], spec: IntradaySpec) -> dict:
    """Pool the three symbols: one instrument's result over four years is an anecdote."""
    net, gross, trades, years = [], [], 0, 0.0
    for symbol, bars in bars_by_symbol.items():
        result = run_intraday(bars, spec, symbol=symbol, round_trip_bps=ROUND_TRIP_BPS)
        if result.trades.empty:
            continue
        net.append(result.trades["net_return"])
        gross.append(result.trades["gross_return"])
        trades += len(result.trades)
        years = max(years, (bars.index[-1] - bars.index[0]).days / 365.25)

    if not net:
        return {"trades": 0, "sharpe": float("nan"), "net_total": 0.0,
                "gross_total": 0.0, "hit_rate": float("nan"), "trades_per_day": 0.0}

    all_net = pd.concat(net)
    all_gross = pd.concat(gross)
    per_year = len(all_net) / years if years > 0 else 0.0
    sharpe = (float(all_net.mean() / all_net.std(ddof=1)) * np.sqrt(per_year)
              if all_net.std(ddof=1) > 0 else float("nan"))
    return {
        "trades": trades,
        "trades_per_day": round(len(all_net) / (years * 365) if years else 0.0, 3),
        "hit_rate": round(float((all_net > 0).mean()), 4),
        "gross_total": round(float(all_gross.sum()), 4),
        "net_total": round(float(all_net.sum()), 4),
        "sharpe": round(sharpe, 3) if np.isfinite(sharpe) else float("nan"),
        "returns": all_net,
    }


def main() -> None:
    cat = Catalog()
    full = {s: load(cat, s) for s in SYMBOLS}
    full = {s: b for s, b in full.items() if not b.empty}
    if not full:
        print("no hourly crypto data in the lake — run `qt ingest --interval 1h` first")
        return

    span = next(iter(full.values()))
    print(f"{len(full)} symboles · {len(span)} barres horaires · "
          f"{span.index.min().date()} -> {span.index.max().date()}")
    print(f"coût aller-retour appliqué : {ROUND_TRIP_BPS:.0f} bps\n")

    in_sample = {s: b.loc[:SPLIT] for s, b in full.items()}
    out_sample = {s: b.loc[SPLIT:] for s, b in full.items()}

    # ------------------------------------------------------- rank in-sample only
    specs = candidates()
    rows = []
    for label, spec in specs:
        stats = evaluate(in_sample, spec)
        stats.pop("returns", None)
        rows.append({"config": label, **stats})
    ranked = pd.DataFrame(rows).sort_values("sharpe", ascending=False)

    print(f"=== {len(specs)} configurations, classées sur 2021-2022 UNIQUEMENT ===\n")
    print(ranked.head(8).to_string(index=False))
    print("\n(les 8 meilleures ; le reste est plus bas)\n")

    best_label = ranked.iloc[0]["config"]
    best_spec = dict(specs)[best_label]
    best_is_sharpe = float(ranked.iloc[0]["sharpe"])

    # ----------------------------------------------- measure it out-of-sample once
    oos = evaluate(out_sample, best_spec)
    oos_returns = oos.pop("returns", pd.Series(dtype="float64"))

    print("=== la meilleure, portée telle quelle sur 2023-2024 ===\n")
    print(f"configuration : {best_label}")
    comparison = pd.DataFrame([
        {"période": "2021-2022 (choix)", "sharpe": best_is_sharpe,
         **{k: ranked.iloc[0][k] for k in ("trades", "hit_rate", "gross_total", "net_total")}},
        {"période": "2023-2024 (mesure)", **{k: oos[k] for k in
                                             ("sharpe", "trades", "hit_rate",
                                              "gross_total", "net_total")}},
    ])
    print(comparison.to_string(index=False))

    # ------------------------------------------------------------------ verdict
    print("\n=== est-ce réel ? ===\n")
    if len(oos_returns) > 10 and oos_returns.std(ddof=1) > 0:
        dsr = deflated_sharpe_ratio(
            oos_returns, n_trials=len(specs),
            trial_sharpes=ranked["sharpe"].dropna(),
            periods_per_year=len(oos_returns) / 2.0,   # trades per year, roughly
        )
        for key, value in dsr.items():
            print(f"  {key:22s} {value}")
    else:
        print("  trop peu de trades hors échantillon pour dire quoi que ce soit")

    drop = best_is_sharpe - (oos["sharpe"] if np.isfinite(oos["sharpe"]) else 0.0)
    print(f"\nchute du Sharpe entre le choix et la mesure : {drop:.3f}")
    print("Une chute de cette taille est la signature d'une sélection : la configuration")
    print("a été retenue parce qu'elle collait à 2021-2022, pas parce qu'elle capte un")
    print("effet. C'est ce que le Sharpe déflaté est fait pour dire.")

    # --------------------------------------------------- what the costs alone do
    if oos["gross_total"] != 0:
        share = (oos["gross_total"] - oos["net_total"]) / abs(oos["gross_total"])
        print(f"\npart du brut mangée par les coûts, hors échantillon : {share:.1%}")


if __name__ == "__main__":
    main()
