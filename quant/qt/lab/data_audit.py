"""Dataset audit — run before any strategy is allowed to see the data.

Every check returns a number, not a pass/fail flag, because the right threshold depends
on the use: three bad prints are irrelevant to a 200-day moving average and fatal to a
strategy that trades the previous day's high.

What is checked:

* duplicates and non-monotonic timestamps;
* missing sessions (gaps longer than the market calendar allows);
* invalid prices (non-positive, high < low, close outside [low, high]);
* outliers (moves beyond 10 robust standard deviations), the usual sign of a bad tick
  or an unadjusted corporate action;
* frozen series (identical close for many sessions: a dead feed, not a quiet market);
* weekend bars on markets that do not trade weekends;
* futures roll gaps, by comparing the continuous future with its cash index — on a
  roll date the future jumps by the carry while the index does not;
* dividend adjustment presence for ETFs.

Look-ahead and leakage are not properties of a dataset alone; they are enforced in the
simulator (next-open execution) and tested in tests/test_lab_simulate.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class AuditReport:
    symbol: str
    n_bars: int
    first: str
    last: str
    years: float
    duplicates: int
    non_monotonic: int
    invalid_prices: int
    ohlc_inconsistent: int
    max_gap_days: int
    long_gaps: int
    outliers: int
    frozen_runs: int
    weekend_bars: int
    zero_volume_share: float
    stale_open_share: float
    roll_jumps: int | None
    adjusted: bool
    grade: str
    issues: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def audit_bars(
    symbol: str,
    raw: pd.DataFrame,
    *,
    trades_weekends: bool = False,
    has_volume: bool = True,
    proxy: pd.DataFrame | None = None,
    expected_adjusted: bool = False,
) -> AuditReport:
    issues: list[str] = []
    notes: list[str] = []
    if raw is None or raw.empty:
        return AuditReport(
            symbol=symbol, n_bars=0, first="", last="", years=0.0, duplicates=0, non_monotonic=0,
            invalid_prices=0, ohlc_inconsistent=0, max_gap_days=0, long_gaps=0, outliers=0,
            frozen_runs=0, weekend_bars=0, zero_volume_share=1.0, stale_open_share=0.0,
            roll_jumps=None, adjusted=False, grade="F", issues=["aucune donnée"], notes=[],
        )

    idx = raw.index
    duplicates = int(idx.duplicated().sum())
    non_monotonic = int((np.diff(idx.asi8) < 0).sum())
    df = raw[~idx.duplicated(keep="last")].sort_index()

    px = df[["open", "high", "low", "close"]]
    invalid = int((~np.isfinite(px.to_numpy()) | (px.to_numpy() <= 0)).any(axis=1).sum())
    inconsistent = int(
        ((df["high"] < df["low"]) | (df["close"] > df["high"] * 1.0001) | (df["close"] < df["low"] * 0.9999)
         | (df["open"] > df["high"] * 1.0001) | (df["open"] < df["low"] * 0.9999)).sum()
    )

    gaps = pd.Series(df.index).diff().dt.days.dropna()
    max_gap = int(gaps.max()) if len(gaps) else 0
    # Longer than a long weekend plus a holiday: 5 days for 5-day markets, 2 for 24/7.
    long_gaps = int((gaps > (2 if trades_weekends else 5)).sum())

    r = np.log(df["close"]).diff().dropna()
    mad = (r - r.median()).abs().median() * 1.4826
    big = (r - r.median()).abs() > 10 * mad if mad > 0 else pd.Series(False, index=r.index)
    # A crash day is a 10-sigma move that stays; a bad tick is one that reverses the
    # next day. Only the second kind is a data error — counting October 1987 as a bad
    # print would downgrade the S&P 500 for having had a history.
    reverts = (r.shift(-1) * r < 0) & (r.shift(-1).abs() > 0.8 * r.abs())
    outliers = int((big & reverts).sum())
    extreme_days = int(big.sum())

    # Stale opens: an index computed before its constituents have traded prints an
    # "open" equal to yesterday's close. Any rule that trades the open is then trading
    # a price that never existed.
    stale_open = float(np.isclose(df["open"], df["close"].shift(1), rtol=1e-6)[1:].mean()) if len(df) > 1 else 0.0

    same = df["close"].diff().eq(0)
    run_id = (~same).cumsum()
    run_len = same.groupby(run_id).sum()
    frozen = int((run_len >= 5).sum())

    weekend = int((df.index.dayofweek >= 5).sum()) if not trades_weekends else 0
    zero_vol = float((df.get("volume", pd.Series(0, index=df.index)).fillna(0) <= 0).mean())

    roll_jumps = None
    if proxy is not None and not proxy.empty:
        rp = np.log(proxy["close"]).diff()
        joined = pd.concat([r.rename("f"), rp.rename("p")], axis=1).dropna()
        resid = joined["f"] - joined["p"]
        roll_jumps = int((resid.abs() > 0.01).sum())
        if roll_jumps:
            issues.append(f"{roll_jumps} jours où le future s'écarte de l'indice de plus de 1 % (rolls non ajustés probables)")

    adjusted = bool("adj_close" in df and not np.allclose(df["adj_close"], df["close"], rtol=1e-6, equal_nan=True))
    if expected_adjusted and not adjusted:
        notes.append("aucun ajustement de dividende dans les données (normal si l'actif ne distribue pas)")

    if duplicates:
        issues.append(f"{duplicates} horodatages en double")
    if invalid:
        issues.append(f"{invalid} barres avec prix invalides")
    if inconsistent:
        issues.append(f"{inconsistent} barres OHLC incohérentes (réparées : high/low recalculés)")
    if long_gaps:
        issues.append(f"{long_gaps} trous de plus de {2 if trades_weekends else 5} jours (max {max_gap})")
    if outliers:
        issues.append(f"{outliers} ticks suspects (saut > 10 écarts robustes annulé le lendemain)")
    if extreme_days:
        notes.append(f"{extreme_days} séances extrêmes (> 10 écarts robustes), conservées : ce sont des krachs réels tant qu'elles ne s'annulent pas")
    if frozen:
        issues.append(f"{frozen} séquences de ≥ 5 clôtures identiques")
    if stale_open > 0.10:
        issues.append(f"ouverture périmée : ouverture = clôture de la veille dans {stale_open:.0%} des séances")
    if weekend:
        issues.append(f"{weekend} barres le week-end sur un marché fermé le week-end")
    if has_volume and zero_vol > 0.05:
        issues.append(f"{zero_vol:.0%} des barres sans volume")

    years = (df.index[-1] - df.index[0]).days / 365.25
    bad = invalid + duplicates + non_monotonic
    serious = stale_open > 0.10 or bad > 0 or (roll_jumps or 0) > 20 or outliers > 5 or frozen > 5
    minor = inconsistent > 0.01 * len(df) or long_gaps > 10 or outliers > 0 or (roll_jumps or 0) > 0
    grade = "C" if serious else ("B" if minor else "A")
    if years < 8:
        notes.append(f"historique court ({years:.1f} ans) : peu de régimes de marché couverts")

    return AuditReport(
        symbol=symbol, n_bars=len(df), first=str(df.index[0].date()), last=str(df.index[-1].date()),
        years=round(years, 2), duplicates=duplicates, non_monotonic=non_monotonic,
        invalid_prices=invalid, ohlc_inconsistent=inconsistent, max_gap_days=max_gap,
        long_gaps=long_gaps, outliers=outliers, frozen_runs=frozen, weekend_bars=weekend,
        zero_volume_share=round(zero_vol, 4), stale_open_share=round(stale_open, 4), roll_jumps=roll_jumps, adjusted=adjusted,
        grade=grade, issues=issues, notes=notes,
    )
