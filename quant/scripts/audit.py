"""Hunt the failure this codebase keeps producing: a confident number instead of an error.

Every bug found in this project so far shared a shape. None raised. None logged. Each
returned something plausible — a zero, a NaN, a flat series, a rescaled book — and the
result was always more flattering than the truth. A test suite catches the code paths
someone thought to test; this catches the ones that quietly do nothing.

Four checks, run against the real lake rather than fixtures, because that is where the
silence lives:

1. **Dead features.** A column that is entirely NaN, or constant, on real data. It
   survives to the model as noise or as nothing, and the feature count still looks right.
2. **Dead alphas.** A signal that is zero everywhere. It appears in every report with a
   name and a rationale while contributing exactly nothing.
3. **Suppressed warnings.** The CLI silences RuntimeWarning and FutureWarning globally.
   This re-enables them and reports what was being hidden.
4. **Limit violations.** Any weight or gross exposure the live path produces that
   exceeds its own configured cap.

Run:  .venv/bin/python -u scripts/audit.py
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from qt.data.catalog import Catalog

pd.set_option("display.width", 220)


def _crypto_panel(cat: Catalog, symbols, bars: int = 6000) -> dict[str, pd.DataFrame]:
    from qt.bars import klines_to_bars

    panel = {}
    for symbol in symbols:
        raw = cat.read_indexed("klines_1h", "binance", symbol)
        if raw.empty:
            continue
        frame = klines_to_bars(raw)
        frame.index = pd.to_datetime(frame["ts"], unit="ms", utc=True)
        frame.index.name = "dt"
        panel[symbol] = frame.tail(bars)
    return panel


def audit_features(cat: Catalog) -> pd.DataFrame:
    """Columns that are all-NaN or constant on real data."""
    from qt import features as F

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    panel = _crypto_panel(cat, symbols)
    if not panel:
        return pd.DataFrame([{"check": "features", "status": "no crypto data in the lake"}])

    ctx = F.load_context(cat, symbols)
    matrices = F.build_panel(panel, **ctx)
    X = matrices[symbols[0]].X

    rows = []
    for col in X.columns:
        series = X[col]
        valid = series.dropna()
        if len(valid) == 0:
            rows.append({"column": col, "problem": "entirely NaN", "detail": ""})
        elif float(valid.std()) == 0.0:
            rows.append({"column": col, "problem": "constant",
                         "detail": f"value={float(valid.iloc[0]):.6g}"})
        elif len(valid) < len(series) * 0.05:
            rows.append({"column": col, "problem": "almost entirely NaN",
                         "detail": f"{len(valid)}/{len(series)} valid"})
    # Columns the pipeline itself dropped are reported too — they are not failures, but
    # a growing list means a venue or context source has gone missing.
    dropped = list(matrices[symbols[0]].dropped)
    for col in dropped:
        rows.append({"column": col, "problem": "dropped by the pipeline", "detail": ""})
    return pd.DataFrame(rows)


def audit_alphas(cat: Catalog) -> pd.DataFrame:
    """Alphas producing a flat zero — present in every report, contributing nothing."""
    from qt import alphas as A
    from qt import features as F

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    panel = _crypto_panel(cat, symbols)
    if not panel:
        return pd.DataFrame([{"alpha": "-", "coverage": np.nan, "problem": "no data"}])

    ctx = F.load_context(cat, symbols)
    matrices = F.build_panel(panel, **ctx)
    signal = A.compute_all(panel[symbols[0]], matrices[symbols[0]].X, warn_missing=False)

    rows = []
    for col in signal.columns:
        coverage = float((signal[col].fillna(0) != 0).mean())
        rows.append({
            "alpha": col,
            "coverage": round(coverage, 4),
            "problem": "INERT — always zero" if coverage == 0.0 else "",
        })
    return pd.DataFrame(rows).sort_values("coverage")


def audit_warnings(cat: Catalog) -> pd.DataFrame:
    """What the CLI's global warning filters are hiding.

    `warnings.filterwarnings("ignore", category=RuntimeWarning)` at import time silences
    every divide-by-zero, overflow and invalid-value warning numpy raises across the
    whole system. Most are benign; the ones that are not have historically been the
    interesting bugs — the log of a negative yield spread, for one.
    """
    from qt import features as F

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    panel = _crypto_panel(cat, symbols, bars=4000)
    if not panel:
        return pd.DataFrame([{"category": "-", "message": "no data", "count": 0}])

    caught: list[warnings.WarningMessage] = []
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        ctx = F.load_context(cat, symbols)
        F.build_panel(panel, **ctx)
        caught = list(record)

    counts: dict[tuple[str, str], int] = {}
    for item in caught:
        key = (item.category.__name__, str(item.message)[:90])
        counts[key] = counts.get(key, 0) + 1
    rows = [{"category": c, "message": m, "count": n} for (c, m), n in counts.items()]
    return pd.DataFrame(rows).sort_values("count", ascending=False) if rows else pd.DataFrame(
        [{"category": "-", "message": "none raised", "count": 0}])


def audit_limits(cat: Catalog) -> pd.DataFrame:
    """Does the live path ever exceed its own configured caps?"""
    from qt.live.orchestrator import DailySpec, load_prices, target_weights

    spec = DailySpec()
    prices = load_prices(cat, spec)
    if prices.empty:
        return pd.DataFrame([{"check": "limits", "status": "no equity data in the lake"}])

    weights = target_weights(prices, spec)
    if weights.empty:
        return pd.DataFrame([{"check": "limits", "status": "not enough history"}])

    per_name = weights.abs().to_numpy().max()
    gross = weights.abs().sum(axis=1).max()
    return pd.DataFrame([
        {"limit": "max_weight", "configured": spec.max_weight,
         "observed": round(float(per_name), 5),
         "breached": bool(per_name > spec.max_weight + 1e-9)},
        {"limit": "max_gross", "configured": spec.max_gross,
         "observed": round(float(gross), 5),
         "breached": bool(gross > spec.max_gross + 1e-9)},
    ])


def main() -> None:
    cat = Catalog()

    print("\n=== 1. dead features (all-NaN or constant on real data) ===\n")
    features = audit_features(cat)
    print(features.to_string(index=False) if not features.empty
          else "none — every feature varies")

    print("\n=== 2. inert alphas (always zero) ===\n")
    alphas = audit_alphas(cat)
    print(alphas.to_string(index=False))
    inert = alphas[alphas["problem"] != ""] if "problem" in alphas.columns else alphas
    print(f"\n{len(inert)} inert of {len(alphas)}")

    print("\n=== 3. what the global warning filters hide ===\n")
    print(audit_warnings(cat).to_string(index=False))

    print("\n=== 4. limit violations on the live path ===\n")
    print(audit_limits(cat).to_string(index=False))


if __name__ == "__main__":
    main()
