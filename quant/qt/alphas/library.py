"""The alpha library.

Each entry states the economic reason it should work. That discipline is the point:
a rule with a mechanism can be argued about, monitored, and retired when the mechanism
stops applying. A rule found by search has nothing to say when it stops working, and
you will not know whether to size it down or wait it out.

Families included:

* **momentum / trend** — under-reaction to information and flow-driven trend
  persistence; the most replicated anomaly across every asset class and century tested.
* **reversal** — short-horizon liquidity provision: when a move is driven by an
  impatient trader rather than news, the price concession reverts.
* **breakout** — the same trend premium expressed through range structure, where stops
  and triggers cluster.
* **carry / funding** — perpetual funding is a direct payment for holding a position;
  extreme funding also measures crowding, which is when cascades happen.
* **flow** — signed aggressive volume is the most immediate observable of pressure.
* **volatility** — vol is persistent and mean-reverting at different horizons;
  compression precedes expansion far more reliably than direction is predictable.
* **seasonal** — session and weekend structure in a market whose participants sleep.
* **cross-sectional** — relative strength within the universe, market-beta removed.

None of these is expected to be profitable alone after costs. They are inputs, and the
combination step (ensemble.py) plus the risk engine is what turns them into a book.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import feature_col, gate, register_alpha, squash


# ---------------------------------------------------------------- momentum
@register_alpha(
    "tsmom",
    family="momentum",
    rationale=(
        "Time-series momentum: markets under-react to slowly-diffusing information, and "
        "trend-following flows extend moves. Documented across 100+ years and every liquid "
        "asset class (Moskowitz/Ooi/Pedersen)."
    ),
    horizon_bars=48,
)
def tsmom(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    # Average of several lookbacks, each scaled by its own realised vol. Blending
    # horizons is what stops the signal from being a bet on one arbitrary window.
    close = bars["close"].astype("float64")
    log_close = np.log(close)
    vol = log_close.diff().ewm(span=168, min_periods=48).std()
    parts = []
    for h in (24, 72, 168, 336):
        parts.append((log_close.diff(h) / (vol * np.sqrt(h))).clip(-4, 4))
    raw = pd.concat(parts, axis=1).mean(axis=1)
    return squash(raw, scale=1.5)


@register_alpha(
    "trend_quality",
    family="momentum",
    rationale=(
        "Trend strength conditioned on path efficiency: a move that travelled in a straight "
        "line reflects sustained one-way demand, while the same net move achieved by chopping "
        "reflects noise. Only the former persists."
    ),
    horizon_bars=48,
)
def trend_quality(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    direction = np.sign(feature_col(features, "mom_ema_fast_slow"))
    efficiency = feature_col(features, "regime_efficiency_72")
    adx = feature_col(features, "trend_adx_48")
    strength = (efficiency.fillna(0.0) * 0.5 + adx.fillna(0.0) * 0.5).clip(0, 1)
    return (direction * strength).fillna(0.0)


# ---------------------------------------------------------------- reversal
@register_alpha(
    "st_reversal",
    family="reversion",
    rationale=(
        "Short-horizon reversal: an impatient liquidation moves price beyond fair value and "
        "pays liquidity providers to absorb it. The premium is real but only in the absence of "
        "news, so it is gated off when volatility is exploding."
    ),
    horizon_bars=12,
)
def st_reversal(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    z = feature_col(features, "rev_z_24")
    raw = -squash(z, scale=1.5)
    # Stand aside when vol is in its top third: a violent regime usually means the move
    # is information, and fading information is how mean-reversion books die.
    calm = feature_col(features, "regime_vol_pct") < 0.67
    return gate(raw.fillna(0.0), calm, weight_when_false=0.25)


@register_alpha(
    "vwap_reversion",
    family="reversion",
    rationale=(
        "Distance from volume-weighted average price measures how far the marginal trade sits "
        "from where the bulk of size actually changed hands. Execution algorithms anchored to "
        "VWAP mechanically pull price back toward it."
    ),
    horizon_bars=12,
)
def vwap_reversion(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    dev = feature_col(features, "rev_px_over_vwap24")
    if dev.isna().all():
        dev = feature_col(features, "rev_px_over_vwap")
    scale = feature_col(features, "atr_24").replace(0.0, np.nan)
    return -squash((dev / scale).fillna(0.0), scale=2.0)


# ---------------------------------------------------------------- breakout
@register_alpha(
    "donchian_breakout",
    family="breakout",
    rationale=(
        "Range breakouts concentrate stop orders and trigger systematic entries, so the first "
        "move past a well-watched level tends to extend. Requires a volatility expansion filter: "
        "breakouts inside a compressed range are overwhelmingly false."
    ),
    horizon_bars=72,
)
def donchian_breakout(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    pos_55 = feature_col(features, "band_donchian_pos_55")
    brk = feature_col(features, "band_donchian_break_55").fillna(0.0)
    expanding = feature_col(features, "regime_vol_expanding") > 0.5
    raw = (brk * 0.6 + squash(pos_55, scale=0.8) * 0.4).fillna(0.0)
    return gate(raw, expanding, weight_when_false=0.3)


@register_alpha(
    "squeeze_release",
    family="volatility",
    rationale=(
        "Volatility is strongly autocorrelated and mean-reverting in level: compressed ranges "
        "resolve into expansion. Direction comes from the flow that breaks the compression, not "
        "from the compression itself."
    ),
    horizon_bars=48,
)
def squeeze_release(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    squeeze = feature_col(features, "band_bb_squeeze_72")  # percentile of bandwidth
    flow = feature_col(features, "flow_ofi_24")
    compressed = (squeeze < 0.2).astype("float64")
    return (compressed * squash(flow, scale=0.25)).fillna(0.0)


# -------------------------------------------------------------------- flow
@register_alpha(
    "order_flow",
    family="flow",
    rationale=(
        "Signed aggressive volume is the most direct observable of buying vs selling pressure. "
        "Informed traders split orders, so imbalance is autocorrelated and partially predictive "
        "of the next interval's move."
    ),
    horizon_bars=12,
)
def order_flow(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    ofi = feature_col(features, "flow_ofi_24")
    persistence = feature_col(features, "flow_ofi_autocorr_72").fillna(0.0).clip(0, 1)
    return squash(ofi * (0.5 + persistence), scale=0.3).fillna(0.0)


@register_alpha(
    "flow_divergence",
    family="flow",
    rationale=(
        "Price rising on negative net aggressive flow is a move without support — it is being "
        "carried by passive buying or thin books, and reverts more often than it extends."
    ),
    horizon_bars=24,
)
def flow_divergence(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    ret = np.log(bars["close"].astype("float64")).diff(24)
    ofi = feature_col(features, "flow_ofi_24")
    divergence = np.sign(ret) * (np.sign(ret) != np.sign(ofi)).astype("float64")
    strength = squash(ret.abs() / ret.abs().rolling(336, min_periods=72).mean(), scale=1.0)
    return (-divergence * strength).fillna(0.0)


@register_alpha(
    "illiquidity_fade",
    family="flow",
    rationale=(
        "When depth collapses (Kyle's lambda spikes), a given amount of flow moves price much "
        "further than the information it carries justifies. Those moves retrace once depth "
        "returns."
    ),
    horizon_bars=24,
)
def illiquidity_fade(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    lam_z = feature_col(features, "liq_kyle_lambda_z_168")
    ret_z = feature_col(features, "jump_ret_over_vol")
    thin = (lam_z > 1.0).astype("float64")
    return (-thin * squash(ret_z, scale=2.0)).fillna(0.0)


# ------------------------------------------------------------------- carry
@register_alpha(
    "funding_carry",
    family="carry",
    rationale=(
        "Perpetual funding is a cash flow paid by the crowded side. Being paid to hold a "
        "position is a direct expected return, and extreme funding additionally marks crowding "
        "that resolves violently against the crowd."
    ),
    horizon_bars=72,
    tags=("perp",),
)
def funding_carry(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    z = feature_col(features, "funding_z")
    if z.isna().all():
        return pd.Series(0.0, index=bars.index)
    # Fade extreme funding: high positive funding => longs crowded => lean short.
    return -squash(z, scale=2.0).fillna(0.0)


@register_alpha(
    "vol_risk_premium",
    family="volatility",
    rationale=(
        "Implied volatility exceeds subsequent realised volatility on average — the variance "
        "risk premium. A wide premium indicates well-paid hedging demand and, historically, a "
        "supportive environment for holding directional risk."
    ),
    horizon_bars=168,
    tags=("macro",),
)
def vol_risk_premium(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    vrp_z = feature_col(features, "vrp_z")
    if vrp_z.isna().all():
        return pd.Series(0.0, index=bars.index)
    trend = np.sign(feature_col(features, "mom_ema_fast_slow")).fillna(0.0)
    return (squash(vrp_z, scale=2.0) * trend).fillna(0.0)


# ---------------------------------------------------------------- seasonal
@register_alpha(
    "session_effect",
    family="seasonal",
    rationale=(
        "Crypto trades continuously but its participants do not. Liquidity thins outside the "
        "US/Europe overlap, and the resulting moves are more often flow artefacts than "
        "information — so they mean-revert into the next liquid session."
    ),
    horizon_bars=12,
)
def session_effect(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    thin = feature_col(features, "cal_asia").fillna(0.0) * (1 - feature_col(features, "cal_europe").fillna(0.0))
    move = feature_col(features, "jump_ret_over_vol")
    return (-thin * squash(move, scale=2.0)).fillna(0.0)


# --------------------------------------------------------- cross-sectional
@register_alpha(
    "xs_momentum",
    family="cross_sectional",
    rationale=(
        "Relative strength within the universe, computed on market-beta-adjusted returns. "
        "Removing the common factor is what separates 'this asset is outperforming' from "
        "'everything is up'."
    ),
    horizon_bars=168,
    tags=("panel",),
)
def xs_momentum(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    rank = feature_col(features, "xs_resmom_rank_168")
    if rank.isna().all():
        rank = feature_col(features, "xs_mom_rank_168")
    if rank.isna().all():
        return pd.Series(0.0, index=bars.index)
    # Stand down when dispersion collapses: with everything correlated to 1 there is no
    # relative-value opportunity, only leverage on the market factor.
    dispersed = feature_col(features, "xs_avg_corr") < 0.85
    return gate(rank.fillna(0.0), dispersed, weight_when_false=0.3)


@register_alpha(
    "xs_reversal",
    family="cross_sectional",
    rationale=(
        "The mirror of cross-sectional momentum at short horizons: the biggest one-day relative "
        "mover is usually absorbing a liquidity shock rather than repricing on information."
    ),
    horizon_bars=24,
    tags=("panel",),
)
def xs_reversal(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    rank = feature_col(features, "xs_resmom_rank_24")
    if rank.isna().all():
        return pd.Series(0.0, index=bars.index)
    return -rank.fillna(0.0) * 0.8


# ------------------------------------------------------------------- macro
@register_alpha(
    "risk_appetite",
    family="macro",
    rationale=(
        "Crypto is a high-beta risk asset. Equity drawdowns and dollar strength drain it of "
        "marginal capital; a rising VIX in particular precedes crypto de-risking rather than "
        "following it."
    ),
    horizon_bars=336,
    tags=("macro",),
)
def risk_appetite(bars: pd.DataFrame, features: pd.DataFrame) -> pd.Series:
    spx = feature_col(features, "spx_ret_20d")
    vix = feature_col(features, "vix_z")
    dxy = feature_col(features, "dxy_ret_20d")
    if spx.isna().all() and vix.isna().all() and dxy.isna().all():
        return pd.Series(0.0, index=bars.index)
    score = (
        squash(spx.fillna(0.0), scale=0.05) * 0.4
        - squash(vix.fillna(0.0), scale=1.5) * 0.4
        - squash(dxy.fillna(0.0), scale=0.02) * 0.2
    )
    return score.fillna(0.0)
