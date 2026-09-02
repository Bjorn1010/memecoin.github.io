"""Load macro and funding context out of the lake, ready for the feature pipeline.

`build_features` accepts `macro=` and `funding=` arguments, but nothing was filling
them, so five alphas in the library — funding carry, funding crowding, the volatility
risk premium, macro beta and the risk-appetite tilt — computed on empty inputs and
returned a flat zero series for every bar. They were not broken; they were unplugged.

That failure mode is the one to watch for in this codebase: an alpha that returns zeros
does not raise, does not warn, and does not fail a test. It just quietly reduces the
strategy to whatever the remaining signals say, while the summary still reports fifteen
alphas as if fifteen were running. `qt.alphas.base` now warns when a required feature is
missing (see the `_MISSING` tracking there); this module is the other half of the fix —
the part that actually supplies the data.

Everything here is a *backward* as-of join at read time. A daily macro series joined
onto an hourly bar index is a step function, and that is correct: S&P close data is not
knowable during the session. `external.asof_join` enforces direction="backward", so no
value is ever visible before it was published.
"""

from __future__ import annotations

import pandas as pd

from ..data import schemas

# (venue, lake symbol, short name), tried in order — the first venue holding a series
# wins that short name. The short names are what `qt.alphas.library` looks up
# (spx_ret_20d, vix_z, dxy_ret_20d, ...), so renaming one silently unplugs an alpha.
#
# FRED comes first because Stooq now answers every request with a JavaScript
# browser-verification challenge; the Stooq rows below are kept only so a lake filled
# before that change still resolves. See qt.data.sources.fred for the full account.
MACRO_SOURCES = [
    ("fred", "spx", "spx"),
    ("fred", "ndx", "ndx"),
    ("fred", "vix", "vix"),
    ("fred", "dxy", "dxy"),
    ("fred", "ust10", "ust10"),
    ("fred", "curve", "curve"),
    ("fred", "hyg", "hyg"),
    ("fred", "oil", "oil"),
    ("fred", "ffr", "ffr"),
    # Legacy Stooq layout.
    ("stooq", "idx_spx", "spx"),
    ("stooq", "idx_ndx", "ndx"),
    ("stooq", "idx_vix", "vix"),
    ("stooq", "dxy", "dxy"),
    ("stooq", "hyg.us", "hyg"),
]

# Every short name the loader can produce — used by context_report to name what is
# missing rather than only listing what happens to be present.
MACRO_NAMES = tuple(dict.fromkeys(name for _, _, name in MACRO_SOURCES))

# Deribit's DVOL index — 30-day implied vol for crypto. Needed for the variance risk
# premium (implied minus realised); without it `vrp` is absent, not zero.
DVOL_SYMBOLS = {"BTC": "DVOLBTC", "ETH": "DVOLETH"}

MACRO_VENUE = "fred"
DVOL_VENUE = "deribit"
PERP_VENUE = "binance-um"


def load_macro(
    catalog,
    *,
    start=None,
    end=None,
    sources: list[tuple[str, str, str]] | None = None,
    dvol_for: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Read the cross-asset context series from the lake.

    Returns a `{short_name: frame}` dict shaped for `external.macro_features`. Series
    absent from the lake are skipped rather than returned empty, because an empty frame
    produces an all-NaN feature column that survives to the model as noise.

    `dvol_for` names a crypto asset ("BTC"/"ETH"); when its DVOL history is present the
    result gains a "dvol" entry, which is what turns on the variance-risk-premium
    feature. Pass the *asset*, not the pair: "BTCUSDT" resolves to BTC.
    """
    out: dict[str, pd.DataFrame] = {}
    for venue, lake_symbol, name in (sources or MACRO_SOURCES):
        if name in out:
            continue  # an earlier venue already supplied this series
        df = catalog.read(schemas.EOD, venue, lake_symbol, start=start, end=end)
        if not df.empty:
            out[name] = df

    if dvol_for:
        asset = _asset_of(dvol_for)
        lake_symbol = DVOL_SYMBOLS.get(asset)
        if lake_symbol:
            df = catalog.read(schemas.EOD, DVOL_VENUE, lake_symbol, start=start, end=end)
            if not df.empty:
                out["dvol"] = df
    return out


def load_funding(catalog, symbols, *, start=None, end=None, venue: str = PERP_VENUE
                 ) -> dict[str, pd.DataFrame]:
    """Read realised perpetual funding prints for each symbol.

    Spot symbols are looked up under their perp ticker, which on Binance is the same
    string — BTCUSDT spot and BTCUSDT perp share a name across two venues. That is why
    the venue is explicit here: reading funding from the "binance" venue silently
    returns nothing, and nothing is exactly what the inert alphas were getting.
    """
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = catalog.read(schemas.FUNDING, venue, symbol, start=start, end=end)
        if not df.empty:
            out[symbol] = df
    return out


def load_context(catalog, symbols, *, start=None, end=None, dvol: bool = True) -> dict:
    """One call for everything `build_panel` needs beyond the bars themselves.

    Returns `{"macro": {...}, "funding": {...}}`, ready to splat:

        ctx = load_context(cat, symbols, start=start, end=end)
        mats = build_panel(panel, **ctx)
    """
    symbols = list(symbols)
    return {
        "macro": load_macro(
            catalog, start=start, end=end,
            dvol_for=symbols[0] if (dvol and symbols) else None,
        ),
        "funding": load_funding(catalog, symbols, start=start, end=end),
    }


def context_report(catalog, symbols, *, start=None, end=None) -> pd.DataFrame:
    """What context is actually available, per series — the check before a research run.

    Reports coverage rather than presence: a macro series that stops in 2023 will join
    forward onto 2026 bars without complaint and hold a stale value for three years.
    The `end` column is what catches that.
    """
    rows = []
    ctx = load_context(catalog, symbols, start=start, end=end)
    for kind, series in (("macro", ctx["macro"]), ("funding", ctx["funding"])):
        for name, df in series.items():
            idx = pd.to_datetime(df["ts"], unit="ms", utc=True)
            rows.append({
                "kind": kind,
                "series": name,
                "rows": len(df),
                "start": idx.min(),
                "end": idx.max(),
            })
    missing_macro = sorted(set(MACRO_NAMES) - set(ctx["macro"]))
    missing_funding = sorted(set(symbols) - set(ctx["funding"]))
    for name in missing_macro:
        rows.append({"kind": "macro", "series": name, "rows": 0, "start": pd.NaT, "end": pd.NaT})
    for name in missing_funding:
        rows.append({"kind": "funding", "series": name, "rows": 0, "start": pd.NaT, "end": pd.NaT})
    return pd.DataFrame(rows).sort_values(["kind", "rows"], ascending=[True, False]).reset_index(drop=True)


def _asset_of(symbol: str) -> str:
    """BTCUSDT -> BTC, BTCUSD -> BTC, BTC -> BTC."""
    s = symbol.upper()
    for quote in ("USDT", "USDC", "BUSD", "USD", "EUR"):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)]
    return s
