"""Scalping at retail size — simulated with the frictions that decide the outcome.

Most backtests model cost as a fraction of notional. At institutional size that is right.
At €40 a trade it is wrong in a way that inverts the answer, because three frictions that
scale with the *order* rather than the notional dominate everything:

**1. The per-order commission.** A flat €1 fee on a €40 position is 2.5%, and 5% for the
round trip. QQQ moves 0.08% in ten minutes. You would need the price to move sixty times
its typical amount just to reach breakeven. This single term is why retail scalping fails
before any signal is considered, and it is the term a percentage-based cost model makes
invisible.

**2. Whole shares.** With €40 you cannot buy one share of QQQ at $707, or SPY at $764.
The order is not expensive — it is impossible. A simulator that trades fractional notional
silently assumes an account feature many brokers do not offer and produces trades that
could never have been placed.

**3. The spread in cents, not basis points.** A one-cent spread is 0.14bp on a $707 share
and 1.7bp on a $59 share. Quoting it as a percentage of notional hides a twelve-fold
difference between instruments in the same book.

Everything here is deliberately pessimistic where the data cannot settle the question:
entry at the next bar's open plus half the spread, exit likewise, an ambiguous bar
resolved against the position, and no holding across a session boundary. A scalping
result that survives those is worth reading. One that needs any of them relaxed is a
description of a simulator, not of a market.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Broker:
    """Retail execution terms. The defaults are a zero-commission US broker.

    `commission_per_order` is the field that decides whether small-size scalping is
    possible at all. Set it to a European broker's €1-5 and the arithmetic closes: at €40
    a trade there is no signal strong enough to overcome 5% a round trip.
    """

    commission_per_order: float = 0.0     # flat fee per side, in account currency
    commission_pct: float = 0.0           # proportional fee per side
    min_commission: float = 0.0
    spread_cents: float = 0.01            # full quoted spread, in price units
    fractional_shares: bool = False       # most brokers outside the US do not offer it
    slippage_cents: float = 0.0           # beyond the half-spread, for a fast market

    def shares_for(self, notional: float, price: float) -> float:
        """How many shares a given notional actually buys."""
        if price <= 0:
            return 0.0
        raw = notional / price
        return raw if self.fractional_shares else float(np.floor(raw))

    def fee(self, notional: float) -> float:
        return max(self.commission_per_order + notional * self.commission_pct,
                   self.min_commission)

    def fill_price(self, reference: float, side: int) -> float:
        """Marketable order: buy at the ask, sell at the bid, plus any slippage."""
        edge = self.spread_cents / 2.0 + self.slippage_cents
        return reference + side * edge


# A few real brokers, for the comparison that matters more than any signal.
BROKERS = {
    "US sans commission": Broker(commission_per_order=0.0, spread_cents=0.01,
                                 fractional_shares=True),
    "US sans commission, actions entières": Broker(commission_per_order=0.0,
                                                   spread_cents=0.01,
                                                   fractional_shares=False),
    "courtier européen 1 €": Broker(commission_per_order=1.0, spread_cents=0.01,
                                    fractional_shares=False),
    "courtier européen 3 €": Broker(commission_per_order=3.0, spread_cents=0.01,
                                    fractional_shares=False),
    "courtier européen 5 €": Broker(commission_per_order=5.0, spread_cents=0.02,
                                    fractional_shares=False),
}


@dataclass
class ScalpSpec:
    """A scalping rule set, in the terms a scalper actually thinks in."""

    position_eur: float = 40.0        # notional per trade
    capital_eur: float = 500.0
    target_eur: float = 20.0          # profit to take
    stop_eur: float = 10.0            # loss to accept
    max_hold_bars: int = 2            # 2 bars of 5 minutes = 10 minutes
    leverage: float = 1.0

    # Signal
    entry_threshold: float = 1.0
    signal_window: int = 12           # bars for the z-score
    vol_window: int = 24

    # Frequency
    max_trades_per_session: int = 8
    cooldown_bars: int = 1
    allow_short: bool = True

    def target_pct(self) -> float:
        """The price move the target implies. Usually the number that ends the debate."""
        exposure = self.position_eur * self.leverage
        return self.target_eur / exposure if exposure > 0 else float("inf")

    def stop_pct(self) -> float:
        exposure = self.position_eur * self.leverage
        return self.stop_eur / exposure if exposure > 0 else float("inf")

    def to_meta(self) -> dict:
        return {
            "position_eur": self.position_eur, "capital_eur": self.capital_eur,
            "target_eur": self.target_eur, "stop_eur": self.stop_eur,
            "leverage": self.leverage, "max_hold_bars": self.max_hold_bars,
            "mouvement_requis_pct": round(self.target_pct() * 100, 3),
            "perte_acceptee_pct": round(self.stop_pct() * 100, 3),
        }


def feasibility(spec: ScalpSpec, bars: pd.DataFrame, bar_minutes: int = 5) -> dict:
    """Before simulating: can the target even be reached by this instrument?

    A target of €20 on €40 needs a 50% move. Comparing that to the distribution of moves
    the instrument actually makes over the holding period answers the question in one
    line, and no amount of signal work changes the answer. This runs first because a
    simulation of an impossible trade still produces a tidy table.
    """
    close = bars["close"].astype("float64")
    horizon = max(spec.max_hold_bars, 1)
    moves = close.pct_change(horizon).abs().dropna()

    needed = spec.target_pct()
    reachable = float((moves >= needed).mean())

    return {
        "mouvement_requis": f"{needed * 100:.2f}%",
        "duree": f"{horizon * bar_minutes} minutes",
        "mouvement_median": f"{moves.median() * 100:.3f}%",
        "mouvement_99e_pct": f"{moves.quantile(0.99) * 100:.3f}%",
        "mouvement_max_observe": f"{moves.max() * 100:.2f}%",
        "part_des_fenetres_atteignant_la_cible": f"{reachable * 100:.3f}%",
        # Even a perfect forecast can only capture what the instrument does. This is the
        # ceiling on the strategy, before costs, before signal, before anything.
        "plafond_par_trade_si_prevision_parfaite":
            round(spec.position_eur * spec.leverage * float(moves.quantile(0.99)), 2),
        "verdict": ("atteignable" if reachable > 0.01
                    else "hors de portée de cet instrument sur cette durée"),
    }


def _zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=max(window // 3, 3)).mean()
    std = series.rolling(window, min_periods=max(window // 3, 3)).std(ddof=0)
    return (series - mean) / std.replace(0.0, np.nan)


def scalp_signal(bars: pd.DataFrame, spec: ScalpSpec | None = None) -> pd.Series:
    """Short-horizon mean reversion, the only intraday effect with a real literature.

    A move of a few bars is part liquidity absorption and part information. The
    absorption reverts; the information does not. On a five-minute bar the absorption
    share is larger than at any longer horizon, which is the entire case for scalping
    existing as an activity.
    """
    spec = spec or ScalpSpec()
    close = bars["close"].astype("float64")
    move = np.log(close).diff(spec.signal_window)
    return -_zscore(move, spec.vol_window * 2)


@dataclass
class ScalpResult:
    trades: pd.DataFrame
    spec: ScalpSpec
    broker: Broker
    diagnostics: dict = field(default_factory=dict)


def run_scalping(
    bars: pd.DataFrame,
    spec: ScalpSpec | None = None,
    broker: Broker | None = None,
    *,
    symbol: str = "",
    bar_minutes: int = 5,
) -> ScalpResult:
    """Simulate the rule with whole shares, per-order fees and session boundaries.

    The position is closed at the last bar of each session whatever its state. A scalper
    who holds overnight is not scalping, and the overnight gap is most of an ETF's daily
    variance — booking it as an intraday result would flatter the strategy enormously.
    """
    spec = spec or ScalpSpec()
    broker = broker or Broker()

    signal = scalp_signal(bars, spec)
    opens = bars["open"].astype("float64").to_numpy()
    highs = bars["high"].astype("float64").to_numpy()
    lows = bars["low"].astype("float64").to_numpy()
    closes = bars["close"].astype("float64").to_numpy()
    session = (bars["session_id"].to_numpy() if "session_id" in bars.columns
               else pd.to_datetime(bars.index).normalize().astype("int64").to_numpy())
    index = bars.index
    sig = signal.to_numpy()

    trades: list[dict] = []
    position = 0
    entry_i = -1
    entry_price = shares = entry_fee = 0.0
    cooldown_until = 0
    per_session: dict = {}
    rejected_too_expensive = 0

    exposure = spec.position_eur * spec.leverage

    for i in range(1, len(bars) - 1):
        last_of_session = session[i] != session[i + 1]

        # ------------------------------------------------------------- manage
        if position != 0:
            stop_price = entry_price * (1 - position * spec.stop_pct())
            target_price = entry_price * (1 + position * spec.target_pct())

            hit_stop = (lows[i] <= stop_price) if position > 0 else (highs[i] >= stop_price)
            hit_target = (highs[i] >= target_price) if position > 0 else (lows[i] <= target_price)
            timed_out = (i - entry_i) >= spec.max_hold_bars

            reason, reference = "", 0.0
            if hit_stop:
                # A bar touching both is read as the stop. Without tick data the
                # pessimistic reading is the only honest one, and the optimistic one is
                # how intraday backtests manufacture their edge.
                reason, reference = "stop", stop_price
            elif hit_target:
                reason, reference = "cible", target_price
            elif timed_out:
                reason, reference = "temps", closes[i]
            elif last_of_session:
                reason, reference = "clôture", closes[i]

            if reason:
                exit_price = broker.fill_price(reference, -position)
                exit_notional = shares * exit_price
                exit_fee = broker.fee(exit_notional)
                gross = position * shares * (exit_price - entry_price)
                net = gross - entry_fee - exit_fee
                trades.append({
                    "symbole": symbol, "sens": "long" if position > 0 else "short",
                    "entree": index[entry_i], "sortie": index[i],
                    "prix_entree": round(entry_price, 4), "prix_sortie": round(exit_price, 4),
                    "actions": shares, "notionnel": round(shares * entry_price, 2),
                    "minutes": (i - entry_i) * bar_minutes, "raison": reason,
                    "brut_eur": round(gross, 4), "frais_eur": round(entry_fee + exit_fee, 4),
                    "net_eur": round(net, 4),
                })
                position = 0
                cooldown_until = i + spec.cooldown_bars
            continue

        # -------------------------------------------------------------- enter
        if last_of_session or i < cooldown_until or not np.isfinite(sig[i]):
            continue
        if per_session.get(session[i], 0) >= spec.max_trades_per_session:
            continue
        if abs(sig[i]) < spec.entry_threshold:
            continue

        direction = 1 if sig[i] > 0 else -1
        if direction < 0 and not spec.allow_short:
            continue

        reference = opens[i + 1]
        if not np.isfinite(reference) or reference <= 0:
            continue
        price = broker.fill_price(reference, direction)
        qty = broker.shares_for(exposure, price)
        if qty <= 0:
            # With €40 you cannot buy one share of a $707 ETF. Not expensive: impossible.
            rejected_too_expensive += 1
            continue

        entry_i = i + 1
        entry_price = price
        shares = qty
        entry_fee = broker.fee(shares * price)
        position = direction
        per_session[session[i]] = per_session.get(session[i], 0) + 1

    frame = pd.DataFrame(trades) if trades else pd.DataFrame(columns=[
        "symbole", "sens", "entree", "sortie", "prix_entree", "prix_sortie", "actions",
        "notionnel", "minutes", "raison", "brut_eur", "frais_eur", "net_eur",
    ])
    return ScalpResult(frame, spec, broker,
                       _diagnose(frame, spec, broker, bars, rejected_too_expensive,
                                 bar_minutes))


def _diagnose(trades: pd.DataFrame, spec: ScalpSpec, broker: Broker,
              bars: pd.DataFrame, rejected: int, bar_minutes: int) -> dict:
    sessions = (bars["session_id"].nunique() if "session_id" in bars.columns
                else max(len(bars) * bar_minutes / (60 * 6.5), 1))
    hours = len(bars) * bar_minutes / 60.0

    if trades.empty:
        return {
            "trades": 0, "heures": round(hours, 1),
            "ordres_impossibles": rejected,
            "note": ("aucun trade — position trop petite pour une action entière"
                     if rejected else "aucun signal n'a franchi le seuil"),
        }

    net = trades["net_eur"]
    gross = trades["brut_eur"]
    fees = trades["frais_eur"]
    wins = net > 0

    return {
        "trades": int(len(trades)),
        "heures": round(hours, 1),
        "trades_par_heure": round(len(trades) / max(hours, 1e-9), 2),
        "gain_brut_eur": round(float(gross.sum()), 2),
        "frais_eur": round(float(fees.sum()), 2),
        "gain_net_eur": round(float(net.sum()), 2),
        "net_par_heure_eur": round(float(net.sum()) / max(hours, 1e-9), 4),
        "taux_reussite": round(float(wins.mean()), 4),
        "gain_moyen_eur": round(float(net[wins].mean()), 3) if wins.any() else 0.0,
        "perte_moyenne_eur": round(float(net[~wins].mean()), 3) if (~wins).any() else 0.0,
        "minutes_moyennes": round(float(trades["minutes"].mean()), 1),
        "raisons_de_sortie": trades["raison"].value_counts().to_dict(),
        # The share of the gross edge the broker takes. Above 100% the strategy is a fee
        # generator whatever the signal does.
        "part_des_frais_sur_le_brut": (round(float(fees.sum() / abs(gross.sum())), 3)
                                       if gross.sum() != 0 else None),
        "ordres_impossibles": rejected,
    }
