"""Walk-forward: the only backtest that answers the question you actually care about.

Cross-validation tells you whether a signal carries information. Walk-forward tells you
what would have happened if you had actually run this — retraining on a schedule,
trading the model's live output, paying costs, with the risk limits armed. They are not
substitutes: CV is diagnostic, walk-forward is the verdict.

The loop, per window:

1. train on bars [t-train_bars, t);
2. predict on bars [t, t+test_bars) — a period the model has never seen, and whose
   labels do not overlap the training set (enforced by the embargo);
3. concatenate the out-of-sample predictions into one continuous signal;
4. run the backtester over that signal, once, end to end.

Point 3 matters: the signal series is stitched from many models, exactly as a live
system's history would be. Point 4 matters too — the equity curve is continuous across
retraining boundaries, so a model that only works right after a retrain has nowhere to
hide.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..labels.build import LabelSet, LabelSpec, make_labels
from ..models.dataset import build_dataset
from ..models.model import ModelSpec, QuantModel
from .engine import BacktestConfig, BacktestResult, run_backtest


@dataclass
class WalkForwardSpec:
    train_bars: int = 8760  # ~1 year of hourly bars
    test_bars: int = 2160  # ~3 months
    step_bars: int | None = None  # defaults to test_bars (non-overlapping tests)
    anchored: bool = False  # False = rolling window, True = expanding
    embargo_bars: int = 48  # gap between train end and test start
    min_train_events: int = 200
    signal_on_events_only: bool = True
    signal_hold_bars: int | None = None  # defaults to the label horizon

    def to_meta(self) -> dict:
        return {
            "train_bars": self.train_bars,
            "test_bars": self.test_bars,
            "step_bars": self.step_bars or self.test_bars,
            "anchored": self.anchored,
            "embargo_bars": self.embargo_bars,
            "signal_on_events_only": self.signal_on_events_only,
        }


@dataclass
class WalkForwardResult:
    signal: pd.Series
    backtest: BacktestResult
    windows: pd.DataFrame
    spec: WalkForwardSpec
    model_meta: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {**self.backtest.metrics, "n_windows": int(len(self.windows))}


def walk_forward(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    *,
    label_spec: LabelSpec | None = None,
    model_spec: ModelSpec | None = None,
    wf_spec: WalkForwardSpec | None = None,
    backtest_config: BacktestConfig | None = None,
    symbol: str = "ASSET",
    funding: pd.Series | None = None,
) -> WalkForwardResult:
    """Retrain-and-trade simulation over the whole sample."""
    label_spec = label_spec or LabelSpec()
    model_spec = model_spec or ModelSpec()
    wf_spec = wf_spec or WalkForwardSpec()
    backtest_config = backtest_config or BacktestConfig()

    labels: LabelSet = make_labels(bars, label_spec)
    if labels.events.empty:
        raise ValueError("no labelled events: check the CUSUM threshold and sample length")

    index = features.index
    step = wf_spec.step_bars or wf_spec.test_bars
    hold = wf_spec.signal_hold_bars or label_spec.horizon_bars

    signal = pd.Series(0.0, index=index, name="signal")
    windows: list[dict] = []
    model_meta: list[dict] = []

    start = 0
    while True:
        train_end = start + wf_spec.train_bars
        test_start = train_end + wf_spec.embargo_bars
        test_end = min(test_start + wf_spec.test_bars, len(index))
        if test_start >= len(index) or test_end - test_start < 10:
            break

        train_slice = index[(0 if wf_spec.anchored else start) : train_end]
        test_slice = index[test_start:test_end]

        train_features = features.loc[train_slice]
        train_labels_idx = labels.events.index.intersection(train_slice)
        # Purge: drop training labels whose outcome resolves after the test begins.
        resolved = labels.events.loc[train_labels_idx, "t1"] < test_slice[0]
        train_labels_idx = train_labels_idx[resolved.to_numpy()]

        window = {
            "window": len(windows),
            "train_start": train_slice[0] if len(train_slice) else pd.NaT,
            "train_end": train_slice[-1] if len(train_slice) else pd.NaT,
            "test_start": test_slice[0],
            "test_end": test_slice[-1],
            "n_train_events": int(len(train_labels_idx)),
            "trained": False,
        }

        if len(train_labels_idx) >= wf_spec.min_train_events:
            sub = LabelSet(
                labels.events.loc[train_labels_idx],
                labels.weights.loc[train_labels_idx],
                labels.volatility,
                labels.spec,
            )
            ds = build_dataset(train_features, sub, symbol)
            if len(ds) >= 50 and ds.y.nunique() >= 2:
                model = QuantModel(model_spec).fit(ds)
                edges = model.edge(features.loc[test_slice])
                if wf_spec.signal_on_events_only:
                    # Only act where the event filter fired, then hold the position for
                    # the label's horizon — the model was trained on exactly those
                    # conditions, so scoring every bar would be a distribution shift.
                    event_mask = features.loc[test_slice].index.isin(labels.events.index)
                    masked = edges.where(event_mask)
                    edges = masked.ffill(limit=max(hold - 1, 0)).fillna(0.0)
                signal.loc[test_slice] = edges.to_numpy()
                window["trained"] = True
                window["mean_abs_edge"] = float(np.abs(edges).mean())
                model_meta.append({**model.meta, "window": window["window"]})

        windows.append(window)
        start += step
        if wf_spec.anchored and start + wf_spec.train_bars >= len(index):
            break

    prices = {symbol: bars}
    signals = pd.DataFrame({symbol: signal})
    funding_map = {symbol: funding} if funding is not None else None
    bt = run_backtest(prices, signals, backtest_config, funding=funding_map)

    return WalkForwardResult(signal, bt, pd.DataFrame(windows), wf_spec, model_meta)


def rule_backtest(
    bars: pd.DataFrame,
    signal: pd.Series,
    *,
    symbol: str = "ASSET",
    backtest_config: BacktestConfig | None = None,
    funding: pd.Series | None = None,
) -> BacktestResult:
    """Backtest a rule-based signal (an alpha or an ensemble) with no training step.

    No walk-forward is needed because there is nothing fitted — but the result is still
    in-sample in the sense that matters: the rule was chosen by a human who has seen
    this data. Treat the Sharpe as an upper bound and check it with
    `validation.statistics.deflated_sharpe_ratio`, counting every variant considered.
    """
    signals = pd.DataFrame({symbol: signal.reindex(bars.index).fillna(0.0)})
    funding_map = {symbol: funding} if funding is not None else None
    return run_backtest({symbol: bars}, signals, backtest_config or BacktestConfig(), funding=funding_map)
