"""The autonomous scalping loop: fetch, analyse, compute a probability, decide, record.

One cycle, repeated during market hours. It fetches the last hours of the Nasdaq and
gold, computes a calibrated probability that the next move is up, and either takes a
position or explains why it did not.

## The gate, and why it exists

A probability is only actionable if it has been shown to *discriminate*. Measured on this
data, the model's does not: its resolution is 0.00085 on QQQ against an uncertainty of
0.249, and its Brier score is worse than always predicting the base rate. Its reliability
curve is the clearest statement of the problem — when it says 99.8% the market rises 25%
of the time, and when it says 2.3% it rises 45% of the time. It is not merely uninformed;
it is confidently wrong precisely where it is most confident, which is where position size
would be largest.

So `SkillGate` sits between the probability and the order. It refuses to trade unless,
on recent data the model did not train on, the probability beats the base rate and moves
away from it enough to matter. A bot that trades a signal it has not shown to work is not
autonomous, it is unsupervised.

The gate is not a safety blanket to be switched off when it is inconvenient. It is the
only part of this file that decides whether the rest of it should run.

## Execution

`PaperBroker` records what would have been done. **There is no real broker adapter in
this file or anywhere it imports, and no code path that can place an order with money.**
Adding one is a decision for the account holder, and the measurements above are what that
decision should be made against.

The `Execution` protocol is the seam where such an adapter would go, and it is written
down so that connecting one is a deliberate act rather than a configuration change.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

from ..data import schemas
from ..data.catalog import Catalog
from ..models.probability import (
    fit_calibrated,
    probability_report,
    required_probability,
)
from .state import Store

MARKETS = {
    "QQQ": "Nasdaq 100",
    "GLD": "or",
    "SPY": "S&P 500",
    "IWM": "petites capitalisations US",
}


@dataclass
class ScalpBotSpec:
    """What the bot watches, how much it risks, and what it demands before trading."""

    symbols: tuple[str, ...] = ("QQQ", "GLD")
    interval: str = "5m"
    # Hours of history analysed each cycle. Long enough for the volatility and z-score
    # windows to be defined, short enough that the estimate reflects today's market.
    lookback_hours: float = 40.0

    capital_eur: float = 500.0
    position_eur: float = 100.0
    max_positions: int = 1
    horizon_bars: int = 6              # 30 minutes at 5-minute bars
    stop_vol_multiple: float = 1.0
    target_vol_multiple: float = 1.5

    # Costs, per round trip, as a fraction of the position. 2bps is a US
    # zero-commission broker on a liquid ETF; a flat per-order fee would be far larger
    # at this size and is what `qt.strategies.scalping` models in full.
    round_trip_cost: float = 0.0002

    # --- the gate
    require_skill: bool = True
    min_resolution: float = 0.005      # below this the probability is a constant
    min_spread: float = 0.05           # 5th-to-95th percentile range of the probability
    min_brier_gain: float = 0.0        # must beat always predicting the base rate

    max_trades_per_session: int = 6

    def to_meta(self) -> dict:
        return {
            "symbols": list(self.symbols), "interval": self.interval,
            "lookback_hours": self.lookback_hours, "capital_eur": self.capital_eur,
            "position_eur": self.position_eur, "horizon_bars": self.horizon_bars,
            "require_skill": self.require_skill, "min_resolution": self.min_resolution,
            "min_spread": self.min_spread,
        }


class Execution(Protocol):
    """Where a broker would plug in. Only a paper implementation exists in this package."""

    def submit(self, symbol: str, side: int, notional: float, price: float,
               reason: str) -> dict: ...

    @property
    def is_paper(self) -> bool: ...


@dataclass
class PaperBroker:
    """Records intentions. Places nothing, anywhere, ever."""

    fills: list[dict] = field(default_factory=list)

    @property
    def is_paper(self) -> bool:
        return True

    def submit(self, symbol: str, side: int, notional: float, price: float,
               reason: str) -> dict:
        fill = {
            "symbole": symbol, "sens": "achat" if side > 0 else "vente",
            "montant_eur": round(notional, 2), "prix": round(price, 4),
            "raison": reason, "papier": True,
        }
        self.fills.append(fill)
        return fill


@dataclass
class SkillGate:
    """Has the probability shown it discriminates, on data the model did not train on?

    Three conditions, all necessary and none sufficient alone:

    * **Resolution** above a floor. This is the term that separates a model from a
      constant, and it is the one almost never reported. A perfectly calibrated model
      that always outputs the base rate scores flawlessly on calibration and has zero
      resolution.
    * **Spread** above a floor. A probability confined to 0.49-0.51 cannot produce a
      position however well calibrated it is.
    * **Brier better than the base rate.** If always saying "47%" scores better, the
      model has subtracted value, and no threshold on the other two terms rescues that.
    """

    spec: ScalpBotSpec

    def evaluate(self, diagnostics: dict) -> tuple[bool, str]:
        if not self.spec.require_skill:
            return True, "garde-fou désactivé explicitement"

        resolution = float(diagnostics.get("resolution", 0.0))
        spread = float(diagnostics.get("amplitude_5e_95e", 0.0))
        gain = float(diagnostics.get("gain_sur_le_taux_de_base", -1.0))

        if resolution < self.spec.min_resolution:
            return False, (
                f"aucune capacité à distinguer : resolution {resolution:.5f} "
                f"sous le seuil {self.spec.min_resolution}. La probabilité ne s'écarte "
                "pas du taux de base d'une manière qui porte de l'information."
            )
        if spread < self.spec.min_spread:
            return False, (
                f"probabilité trop plate : amplitude {spread:.4f} sous {self.spec.min_spread}"
            )
        if gain <= self.spec.min_brier_gain:
            return False, (
                f"moins bon que le taux de base : gain de Brier {gain:+.5f}. "
                "Un bot qui dirait toujours la même probabilité ferait mieux."
            )
        return True, f"resolution {resolution:.5f}, amplitude {spread:.3f}, gain {gain:+.5f}"


@dataclass
class ScalpDecision:
    """One market, one cycle: the analysis, the probability, and what was done."""

    symbol: str
    market: str
    price: float
    probability_up: float
    required: float
    edge: float
    action: str                  # ACHETER | VENDRE | ATTENDRE | BLOQUÉ
    reason: str
    bars_analysed: int
    volatility: float
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "marché": self.market, "code": self.symbol, "prix": round(self.price, 2),
            "probabilité_hausse": (round(self.probability_up, 4)
                                   if np.isfinite(self.probability_up) else None),
            "seuil_requis": round(self.required, 4),
            "espérance": round(self.edge, 5) if np.isfinite(self.edge) else None,
            "action": self.action, "raison": self.reason,
            "barres_analysées": self.bars_analysed,
        }


def analyse(bars: pd.DataFrame, spec: ScalpBotSpec) -> tuple[pd.Series, pd.Series, dict]:
    """Features, outcomes and the calibrated probability, from the recent window.

    The outcome is deliberately direction-only: up versus down, with the observations
    where nothing happened dropped. Including them makes the model predict "nothing",
    which it does well and which cannot be traded — the trap this whole file exists
    downstream of.
    """
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from research_prediction import features_for, triple_barrier  # noqa: PLC0415

    X = features_for(bars)
    labels = triple_barrier(bars, spec.horizon_bars)

    usable = X.notna().all(axis=1) & labels.notna() & (labels != 0)
    X, outcomes = X[usable], (labels[usable] > 0).astype(int)
    if len(X) < 400:
        return pd.Series(dtype="float64"), outcomes, {
            "note": f"seulement {len(X)} observations exploitables, il en faut 400"}

    probabilities, raw = fit_calibrated(X, outcomes, horizon=spec.horizon_bars, embargo=24)
    report = probability_report(probabilities, outcomes, raw)
    return probabilities, outcomes, report.diagnostics


def decide(bars: pd.DataFrame, symbol: str, spec: ScalpBotSpec,
           gate: SkillGate | None = None) -> ScalpDecision:
    """Analyse one market and say what to do about it."""
    gate = gate or SkillGate(spec)
    market = MARKETS.get(symbol, symbol)
    price = float(bars["close"].iloc[-1])
    returns = np.log(bars["close"].astype("float64")).diff()
    volatility = float(returns.rolling(24, min_periods=12).std(ddof=0).iloc[-1])

    payoff = spec.target_vol_multiple / max(spec.stop_vol_multiple, 1e-9)
    move = max(spec.stop_vol_multiple * volatility, 1e-9)
    cost_fraction = spec.round_trip_cost / move
    required = required_probability(payoff, cost_fraction)

    probabilities, _, diagnostics = analyse(bars, spec)
    if probabilities.empty or probabilities.dropna().empty:
        return ScalpDecision(symbol, market, price, float("nan"), required, float("nan"),
                             "ATTENDRE", diagnostics.get("note", "pas de probabilité"),
                             len(bars), volatility, diagnostics)

    allowed, why = gate.evaluate(diagnostics)
    p_up = float(probabilities.dropna().iloc[-1])
    edge_long = p_up * payoff - (1 - p_up) - cost_fraction
    edge_short = (1 - p_up) * payoff - p_up - cost_fraction
    edge = max(edge_long, edge_short)

    if not allowed:
        return ScalpDecision(symbol, market, price, p_up, required, edge,
                             "BLOQUÉ", why, len(bars), volatility, diagnostics)

    if edge_long > 0 and edge_long >= edge_short:
        action, reason = "ACHETER", f"espérance positive à l'achat ({edge_long:+.4f})"
    elif edge_short > 0:
        action, reason = "VENDRE", f"espérance positive à la vente ({edge_short:+.4f})"
    else:
        action = "ATTENDRE"
        reason = (f"probabilité {p_up:.3f}, il en faudrait {required:.3f} pour couvrir "
                  f"les coûts")

    return ScalpDecision(symbol, market, price, p_up, required, edge, action, reason,
                         len(bars), volatility, diagnostics)


@dataclass
class CycleReport:
    ts: pd.Timestamp
    decisions: list[ScalpDecision] = field(default_factory=list)
    fills: list[dict] = field(default_factory=list)
    status: str = "ok"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "horodatage": self.ts.isoformat(), "statut": self.status,
            "raison": self.reason,
            "décisions": [d.to_dict() for d in self.decisions],
            "ordres": self.fills,
        }


def run_cycle(spec: ScalpBotSpec | None = None, *, catalog: Catalog | None = None,
              broker: Execution | None = None, store: Store | None = None,
              run_id: str = "scalp", refresh: bool = True) -> CycleReport:
    """One complete pass. Never raises — a loop that stops is not autonomous."""
    spec = spec or ScalpBotSpec()
    catalog = catalog or Catalog()
    broker = broker or PaperBroker()
    stamp = schemas.to_utc(pd.Timestamp.now("UTC"))

    if not broker.is_paper:
        # Belt and braces: this package ships no real adapter, and if one is ever passed
        # in, the bot stops rather than discovering the fact by placing an order.
        return CycleReport(stamp, status="refusé",
                           reason="exécution non-papier fournie — ce module ne trade pas d'argent réel")

    try:
        from ..data.sources import yahoo

        report = CycleReport(stamp)
        for symbol in spec.symbols:
            if refresh:
                try:
                    fresh = yahoo.intraday(symbol, interval=spec.interval)
                    if not fresh.empty:
                        catalog.write(f"{schemas.EOD}_{spec.interval}", yahoo.VENUE,
                                      symbol, fresh)
                except Exception as exc:  # noqa: BLE001 — one bad symbol must not stop the cycle
                    report.reason = f"{symbol}: rafraîchissement échoué ({exc})"[:160]

            bars = catalog.read_indexed(f"{schemas.EOD}_{spec.interval}", "yahoo", symbol)
            if bars.empty:
                report.decisions.append(ScalpDecision(
                    symbol, MARKETS.get(symbol, symbol), float("nan"), float("nan"),
                    float("nan"), float("nan"), "ATTENDRE",
                    "aucune donnée pour ce marché", 0, float("nan")))
                continue

            decision = decide(bars, symbol, spec)
            report.decisions.append(decision)

            if decision.action in ("ACHETER", "VENDRE"):
                side = 1 if decision.action == "ACHETER" else -1
                fill = broker.submit(symbol, side, spec.position_eur, decision.price,
                                     decision.reason)
                report.fills.append(fill)

        _record(store, run_id, report, spec)
        return report

    except Exception as exc:  # noqa: BLE001
        return CycleReport(stamp, status="erreur",
                           reason=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-400:]}")


def _record(store: Store | None, run_id: str, report: CycleReport,
            spec: ScalpBotSpec) -> None:
    """Persist the decisions. Recording must never break the cycle."""
    if store is None:
        return
    try:
        ms = int(schemas.epoch_ms(pd.DatetimeIndex([report.ts])).iloc[0])
        for d in report.decisions:
            store.record_decision(
                run_id, ms, d.symbol,
                signal=d.probability_up if np.isfinite(d.probability_up) else None,
                target_weight=spec.position_eur / spec.capital_eur,
                allowed_weight=(spec.position_eur / spec.capital_eur
                                if d.action in ("ACHETER", "VENDRE") else 0.0),
                risk_scale=1.0 if d.action in ("ACHETER", "VENDRE") else 0.0,
                risk_reason=f"{d.action}: {d.reason}"[:200],
                equity=spec.capital_eur,
            )
    except Exception:  # noqa: BLE001
        pass
