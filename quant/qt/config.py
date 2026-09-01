"""Central configuration.

Everything is resolved from environment variables with sane defaults so the whole
system runs out of the box with zero setup and zero paid API keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class CostModel:
    """Trading costs. Defaults are deliberately pessimistic.

    A backtest that only survives with optimistic costs is not a strategy, it is a
    rounding error. These numbers are public retail-tier taker/maker fees, not the
    VIP rates a fund would get.
    """

    taker_fee_bps: float = 5.0  # 0.05% — Binance/Bybit spot & perp retail taker
    maker_fee_bps: float = 2.0  # 0.02%
    # Half-spread paid on every aggressive fill, expressed in basis points.
    half_spread_bps: float = 1.0
    # Square-root market impact, in the standard form used on real trading desks:
    #     impact_bps = impact_coeff * bar_volatility_bps * sqrt(participation)
    # where participation = order notional / notional traded in that bar. Impact must
    # be scaled by volatility: the same participation rate costs far more in a violent
    # market than a calm one, and a volatility-free constant gets both regimes wrong.
    # A coefficient near 1.0 is the empirically calibrated value across venues.
    impact_coeff: float = 1.0
    # Funding is applied to perp positions from the real funding series when present.
    apply_funding: bool = True
    # Borrow cost for shorts on spot-like instruments, annualised.
    short_borrow_annual: float = 0.03


@dataclass(frozen=True)
class RiskLimits:
    """Hard limits. Enforced in the lowest layer of the engine.

    No strategy, model or allocator can widen these — they can only ask for less.
    """

    target_annual_vol: float = 0.20  # volatility targeting objective
    max_gross_leverage: float = 2.0
    max_position_weight: float = 0.35  # per instrument, fraction of equity
    max_daily_loss: float = 0.03  # -3% on the day -> flat + halt until next session
    max_drawdown: float = 0.20  # -20% peak-to-trough -> kill switch, manual restart
    kelly_fraction: float = 0.25  # never full Kelly
    max_positions: int = 10
    min_trade_notional: float = 10.0


@dataclass(frozen=True)
class Config:
    repo_root: Path = _REPO_ROOT
    data_dir: Path = field(default_factory=lambda: _env_path("QT_DATA_DIR", _REPO_ROOT / "data"))
    http_timeout: float = field(default_factory=lambda: _env_float("QT_HTTP_TIMEOUT", 60.0))
    http_retries: int = field(default_factory=lambda: _env_int("QT_HTTP_RETRIES", 4))
    user_agent: str = "qt-research/1.0 (+https://github.com/bjorn1010)"
    costs: CostModel = field(default_factory=CostModel)
    risk: RiskLimits = field(default_factory=RiskLimits)
    # Paper trading only. There is no live-execution adapter in this codebase by design.
    paper_starting_equity: float = field(default_factory=lambda: _env_float("QT_EQUITY", 100_000.0))

    @property
    def lake_dir(self) -> Path:
        return self.data_dir / "lake"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def state_db(self) -> Path:
        return self.data_dir / "paper.db"

    def ensure_dirs(self) -> None:
        for d in (self.lake_dir, self.cache_dir, self.models_dir, self.runs_dir):
            d.mkdir(parents=True, exist_ok=True)


CONFIG = Config()

# Annualisation factors by bar frequency, used everywhere Sharpe/vol are computed.
SECONDS_PER_YEAR = 365 * 24 * 3600
TRADING_DAYS_PER_YEAR = 252
CRYPTO_DAYS_PER_YEAR = 365
