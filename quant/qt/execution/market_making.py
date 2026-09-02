"""Market making — Avellaneda-Stoikov optimal quoting.

A market maker earns the spread and is paid for providing liquidity. The risk is
inventory: quote symmetrically around the mid and you will accumulate a position in
whichever direction the market is moving, which is precisely the direction that hurts.
Every naive market maker dies the same way — picked off on one side, holding size into
a trend.

Avellaneda-Stoikov solves it in two steps that are worth separating because they answer
different questions:

* **Reservation price** — where *you* value the asset given the inventory you already
  hold, which is below the mid when you are long (you want to sell) and above when you
  are short. Quoting around the reservation price rather than the mid is what makes the
  strategy mean-revert its own inventory automatically.

      r = s - q * gamma * sigma^2 * (T - t)

* **Optimal spread** — how wide to quote, balancing the spread earned against the
  inventory risk taken and the probability of getting filled at all.

      delta = gamma * sigma^2 * (T-t) + (2/gamma) * ln(1 + gamma/k)

The parameters are interpretable: `gamma` is inventory aversion (higher = skew harder,
quote wider, hold less), and `k` describes how fill probability decays with distance
from the mid, which is estimable from your own fill history.

This is included as *analysis*, not as a live strategy: real market making needs
sub-millisecond quote updates and a maker-fee rebate schedule, neither of which this
paper system has. What it is genuinely useful for is understanding the other side of
every trade you pay a spread on — and for asking whether a spread you are being charged
is fair given the volatility.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Quotes:
    reservation_price: float
    bid: float
    ask: float
    spread: float
    skew: float  # how far the reservation price sits from the mid
    inventory: float

    @property
    def half_spread(self) -> float:
        return self.spread / 2.0

    def to_dict(self) -> dict:
        return {
            "reservation_price": self.reservation_price,
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "skew": self.skew,
            "inventory": self.inventory,
        }


def avellaneda_stoikov_quotes(
    mid_price: float,
    inventory: float,
    *,
    volatility: float,
    time_remaining: float = 1.0,
    gamma: float = 0.1,
    k: float = 1.5,
) -> Quotes:
    """Optimal bid/ask given current inventory.

    `volatility` is per-unit-time price standard deviation in *price* units (not
    returns), `time_remaining` is the fraction of the trading session left, `gamma` is
    inventory aversion and `k` the order-arrival decay.

    Reading the output: a long inventory pushes the reservation price below the mid, so
    both quotes shift down — the maker becomes keener to sell and less keen to buy,
    which unwinds the position through the natural flow rather than by crossing the
    spread.
    """
    variance_term = gamma * volatility**2 * time_remaining
    reservation = mid_price - inventory * variance_term
    spread = variance_term + (2.0 / gamma) * np.log(1.0 + gamma / k)

    return Quotes(
        reservation_price=float(reservation),
        bid=float(reservation - spread / 2.0),
        ask=float(reservation + spread / 2.0),
        spread=float(spread),
        skew=float(reservation - mid_price),
        inventory=float(inventory),
    )


def symmetric_quotes(mid_price: float, spread: float) -> Quotes:
    """Naive symmetric quoting around the mid — the thing to compare against.

    Simulate both and the difference is stark: the symmetric maker's inventory random-
    walks without limit and its PnL is dominated by whatever position it happened to be
    holding at the end.
    """
    return Quotes(mid_price, mid_price - spread / 2, mid_price + spread / 2, spread, 0.0, 0.0)


def simulate_market_making(
    prices: pd.Series,
    *,
    gamma: float = 0.1,
    k: float = 1.5,
    order_size: float = 1.0,
    fill_intensity: float = 1.0,
    max_inventory: float = 50.0,
    maker_fee_bps: float = -1.0,
    seed: int = 0,
    symmetric: bool = False,
) -> dict:
    """Simulate a quoting session against a historical price path.

    Fill model: the probability of a quote being hit in a bar decays exponentially with
    its distance from the mid, P(fill) = A * exp(-k * delta), which is the same
    assumption the closed-form solution is derived under. It is a model, not the order
    book — a real backtest needs queue position — but it is enough to show the
    mechanism, and specifically to show that the inventory skew is what keeps the
    position bounded.

    `maker_fee_bps` is negative when the venue pays a rebate, which is the usual case
    and is a meaningful part of the economics.
    """
    px = pd.Series(prices).dropna()
    n = len(px)
    if n < 10:
        return {"error": "need at least 10 price observations"}

    rng = np.random.default_rng(seed)
    returns = np.log(px).diff().dropna()
    sigma_price = float(returns.std(ddof=1) * px.mean())  # volatility in price units

    inventory = 0.0
    cash = 0.0
    rows = []

    for i, (ts, mid) in enumerate(px.items()):
        time_remaining = max(1.0 - i / n, 1e-6)

        if symmetric:
            base_spread = gamma * sigma_price**2 + (2.0 / gamma) * np.log(1.0 + gamma / k)
            q = symmetric_quotes(float(mid), base_spread)
        else:
            q = avellaneda_stoikov_quotes(
                float(mid), inventory, volatility=sigma_price,
                time_remaining=time_remaining, gamma=gamma, k=k,
            )

        # Fill probabilities decay with distance from the mid.
        dist_bid = max(mid - q.bid, 0.0)
        dist_ask = max(q.ask - mid, 0.0)
        p_bid = fill_intensity * np.exp(-k * dist_bid / max(sigma_price, 1e-9))
        p_ask = fill_intensity * np.exp(-k * dist_ask / max(sigma_price, 1e-9))

        bought = sold = 0.0
        if rng.random() < min(p_bid, 1.0) and inventory < max_inventory:
            bought = order_size
            cash -= q.bid * order_size * (1 + maker_fee_bps / 1e4)
            inventory += order_size
        if rng.random() < min(p_ask, 1.0) and inventory > -max_inventory:
            sold = order_size
            cash += q.ask * order_size * (1 - maker_fee_bps / 1e4)
            inventory -= order_size

        rows.append(
            {
                "ts": ts, "mid": float(mid), "bid": q.bid, "ask": q.ask,
                "reservation": q.reservation_price, "skew": q.skew, "spread": q.spread,
                "inventory": inventory, "cash": cash,
                "equity": cash + inventory * float(mid),
                "bought": bought, "sold": sold,
            }
        )

    df = pd.DataFrame(rows).set_index("ts")
    trades = int((df["bought"] > 0).sum() + (df["sold"] > 0).sum())
    equity = df["equity"]

    return {
        "path": df,
        "final_equity": float(equity.iloc[-1]),
        "n_trades": trades,
        "mean_inventory": float(df["inventory"].mean()),
        # The number that matters: an unskewed maker's inventory wanders without bound.
        "max_abs_inventory": float(df["inventory"].abs().max()),
        "inventory_std": float(df["inventory"].std(ddof=1)),
        "mean_spread": float(df["spread"].mean()),
        "mean_spread_bps": float((df["spread"] / df["mid"]).mean() * 1e4),
        "equity_vol": float(equity.diff().std(ddof=1)),
        "strategy": "symmetric" if symmetric else "avellaneda_stoikov",
    }


def estimate_fill_decay(fills: pd.DataFrame, mid_col: str = "mid", price_col: str = "price") -> dict:
    """Estimate `k` from observed fills: how fast fill probability decays with distance.

    Fit log(count) against distance from the mid across distance buckets. The slope is
    -k. Estimating this from your own fills rather than assuming a value is what makes
    the optimal spread mean anything for your venue and order type.
    """
    df = fills.replace([np.inf, -np.inf], np.nan).dropna(subset=[mid_col, price_col])
    if len(df) < 50:
        return {"k": np.nan, "n": len(df), "reason": "need >=50 fills"}

    distance = (df[price_col] - df[mid_col]).abs() / df[mid_col]
    buckets = pd.qcut(distance, q=min(10, len(df) // 10), duplicates="drop")
    counts = distance.groupby(buckets, observed=True).count()
    centres = distance.groupby(buckets, observed=True).mean()

    mask = counts > 0
    if mask.sum() < 3:
        return {"k": np.nan, "n": len(df), "reason": "too few populated buckets"}

    x = centres[mask].to_numpy()
    y = np.log(counts[mask].to_numpy())
    slope, intercept = np.polyfit(x, y, 1)
    return {
        "k": float(-slope),
        "intensity_A": float(np.exp(intercept)),
        "n": len(df),
        "r_squared": float(np.corrcoef(x, y)[0, 1] ** 2),
    }
