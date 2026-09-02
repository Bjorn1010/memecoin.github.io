"""FRED — the Federal Reserve Bank of St. Louis economic database.

This module exists because Stooq broke. Stooq used to serve plain CSV over HTTP and now
answers every request with a JavaScript browser-verification challenge, so the macro
ingest returned zero rows for every series — quietly, with a success exit code, because
the source treated an unparseable response as "no data". The macro alphas then computed
on nothing and returned a flat zero. That is the failure mode this codebase keeps
running into: the pipeline reports success and the strategy silently loses signals.

FRED is a better foundation than a scraped quote site:

* It is the Federal Reserve's own publication. No anti-bot layer, no terms that forbid
  the use, no key required for the CSV endpoint.
* The histories are long — the VIX from 1990, the Nasdaq 100 from 1986, the 10-year
  Treasury yield from 1962 — which matters when the crypto history now reaches 2011.
* Revisions are published rather than silently overwritten.

The one caveat, and it is a real one: **FRED series are daily and released after the
fact.** `SP500` carries the previous close, and the observation dated 2026-09-02 is not
available at 09:00 on 2026-09-02. Every consumer of this data joins it *backward* only
(`qt.features.external.asof_join`), which is what keeps the point-in-time discipline.
Do not "improve" that to a nearest-value join.

Second caveat: FRED redistributes some vendor series under a licence that caps the
window. `SP500` gives ten years, not the full history, and the high-yield spread gives
about three. The long series below are chosen so that a truncated one is never the only
representative of its factor — Nasdaq Composite backs up the S&P, the VXN backs up the
VIX.
"""

from __future__ import annotations

import io

import pandas as pd

from .. import schemas
from ..http import get_text

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
VENUE = "fred"

# FRED series id -> the short name the feature layer will prefix its columns with.
# These names are what `qt.alphas.library` looks up (spx_ret_20d, vix_z, dxy_ret_20d,
# ...), so renaming the right-hand side unplugs an alpha without any error.
DEFAULT_CONTEXT = {
    "SP500": "spx",            # equity risk appetite (10-year licence window)
    "NASDAQCOM": "ndx",        # tech beta — the closest listed cousin of crypto, from 1971
    "VIXCLS": "vix",           # implied equity vol: the risk-off switch, from 1990
    "DTWEXBGS": "dxy",         # broad trade-weighted dollar — crypto's standing headwind
    "DGS10": "ust10",          # nominal 10-year yield, the discount rate for everything
    "T10Y2Y": "curve",         # 10y-2y slope: the recession gauge markets actually watch
    "BAMLH0A0HYM2": "hyg",     # high-yield OAS — credit stress leads equity stress
    "DCOILWTICO": "oil",       # WTI: the inflation impulse, from 1986
    "DFF": "ffr",              # effective fed funds — the policy rate itself
}

# Series quoted as a percentage or a rate rather than an index level. The feature layer
# takes log differences, which is meaningless for a spread that legitimately crosses
# zero (T10Y2Y inverts), so these are flagged for the caller.
RATE_LIKE = frozenset({"ust10", "curve", "hyg", "ffr", "vix"})


def series(series_id: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Fetch one FRED series as a canonical EOD frame.

    FRED writes missing observations as ".", not as an empty field — weekends, holidays
    and genuinely unpublished days all look the same. Coercing to NaN and dropping is
    correct: a forward-fill here would invent a print that the Fed never made, and the
    backward as-of join downstream already carries the last real value forward at the
    point of use, where it belongs.
    """
    text = get_text(URL, params={"id": series_id}, min_gap=0.5)
    if not text or "observation_date" not in text.split("\n", 1)[0]:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    raw = pd.read_csv(io.StringIO(text))
    value_col = [c for c in raw.columns if c != "observation_date"]
    if not value_col:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    value = pd.to_numeric(raw[value_col[0]], errors="coerce")
    dates = pd.to_datetime(raw["observation_date"], utc=True, errors="coerce")
    keep = value.notna() & dates.notna()
    value, dates = value[keep], dates[keep]
    if value.empty:
        return schemas.normalise(pd.DataFrame(), schemas.EOD)

    out = pd.DataFrame({
        "ts": schemas.epoch_ms(dates),
        # A FRED series is a single number per day. Presenting it as OHLC would imply
        # an intraday range that does not exist, so all four legs carry the same value
        # and only `close` should ever be read.
        "open": value.to_numpy(), "high": value.to_numpy(),
        "low": value.to_numpy(), "close": value.to_numpy(),
        "volume": 0.0,
    })
    out = schemas.normalise(out, schemas.EOD)
    if start is not None:
        out = out[out["ts"] >= int(schemas.to_utc(start).value // 10**6)]
    if end is not None:
        out = out[out["ts"] <= int(schemas.to_utc(end).value // 10**6)]
    return out.reset_index(drop=True)


def ingest(catalog, series_map: dict[str, str] | None = None, start: str | None = None,
           end: str | None = None) -> pd.DataFrame:
    """Download the macro context set and write it to the lake under the short names.

    Writing under the short name rather than the FRED id means the feature layer never
    has to know that "the dollar" is called DTWEXBGS, and swapping the underlying series
    later does not require a migration.
    """
    rows = []
    for series_id, name in (series_map or DEFAULT_CONTEXT).items():
        df = series(series_id, start=start, end=end)
        if not df.empty:
            catalog.write(schemas.EOD, VENUE, name, df)
        idx = pd.to_datetime(df["ts"], unit="ms", utc=True) if not df.empty else pd.Series(dtype="datetime64[ns, UTC]")
        rows.append({
            "fred_id": series_id, "name": name, "rows": len(df),
            "start": idx.min() if len(idx) else pd.NaT,
            "end": idx.max() if len(idx) else pd.NaT,
        })
    return pd.DataFrame(rows)
