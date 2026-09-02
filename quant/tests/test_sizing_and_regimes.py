"""Tests for bet sizing, regime switching, portfolio backtesting and feed health.

The sizing tests are the ones worth reading. They do not assert an opinion about
martingale — they assert the *arithmetic*, measured by simulation:

* a fair coin plus a martingale ruins most accounts while keeping a mean above the
  starting capital, which is precisely how the system fools people;
* a martingale still ruins a large share of accounts even with a genuine winning edge;
* fixed-fractional betting cannot be ruined at all, because a fraction of a shrinking
  number shrinks with it;
* over-betting Kelly turns a positive edge into a loss.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ------------------------------------------------------------------ progressions
def test_martingale_doubles_after_loss_and_resets_after_win():
    from qt.sizing import Martingale

    m = Martingale(base_unit=100.0)
    state = m.initial_state()
    assert m.next_stake(state, won=False, equity=1e9) == 200.0
    assert m.next_stake(state, won=False, equity=1e9) == 400.0
    assert m.next_stake(state, won=False, equity=1e9) == 800.0
    assert m.next_stake(state, won=True, equity=1e9) == 100.0  # reset


def test_martingale_capital_requirement_is_geometric():
    from qt.sizing import martingale_capital_requirement

    # Surviving n losses needs 2^n - 1 units; the probability falls at the same rate.
    for n in (5, 10, 13):
        req = martingale_capital_requirement(base_unit=1.0, n_losses=n)
        assert req["capital_required"] == pytest.approx(2**n - 1)
        assert req["probability_at_50pct"] == pytest.approx(0.5**n)
        # Expected cost is the product, and it does not shrink with n.
        assert req["capital_required"] * req["probability_at_50pct"] == pytest.approx(
            (2**n - 1) * 0.5**n, rel=1e-9
        )


def test_martingale_ruins_most_accounts_on_a_fair_coin():
    """The headline: many small wins, converted into rare total loss."""
    from qt.sizing import compare_progressions

    res = compare_progressions(win_rate=0.5, payoff=1.0, n_bets=500, n_paths=400, seed=1)
    martingale = res.loc["martingale"]

    assert martingale["ruin_rate"] > 0.4, f"ruin rate was only {martingale['ruin_rate']:.1%}"
    assert martingale["median_final"] < martingale["mean_final"], (
        "the mean must exceed the median — that gap is how the system looks viable"
    )
    # Fixed fractional cannot be ruined: a fraction of a shrinking account shrinks too.
    assert res.loc["fixed_fractional", "ruin_rate"] == 0.0


def test_martingale_still_ruins_accounts_with_a_genuine_edge():
    """A real edge does not rescue the progression; it only postpones the arrival."""
    from qt.sizing import compare_progressions

    res = compare_progressions(win_rate=0.55, payoff=1.0, n_bets=500, n_paths=400, seed=2)
    assert res.loc["martingale", "ruin_rate"] > 0.1
    # While flat and fixed-fractional betting convert the same edge into no ruin at all.
    assert res.loc["flat", "ruin_rate"] < 0.02
    assert res.loc["fixed_fractional", "ruin_rate"] == 0.0


def test_anti_martingale_cannot_be_ruined_by_a_losing_streak():
    """The mirror image risks open profit, not capital."""
    from qt.sizing import AntiMartingale, simulate_progression

    losses = np.zeros(200, dtype=bool)  # every single bet loses
    res = simulate_progression(losses, AntiMartingale(base_unit=100.0), starting_equity=100_000.0)
    # Stakes never escalate, so a long losing run bleeds rather than detonates.
    assert res.max_stake == 100.0
    assert not res.ruined


def test_fixed_fractional_never_reaches_zero():
    from qt.sizing import FixedFractional, simulate_progression

    losses = np.zeros(500, dtype=bool)
    res = simulate_progression(losses, FixedFractional(0.02), starting_equity=100_000.0)
    assert res.final_equity > 0
    assert not res.ruined


def test_progression_stops_when_the_stake_exceeds_the_account():
    from qt.sizing import Martingale, simulate_progression

    losses = np.zeros(50, dtype=bool)
    res = simulate_progression(losses, Martingale(base_unit=1000.0), starting_equity=10_000.0)
    assert res.ruined
    # 1000+2000+4000 = 7000 affordable; the next 8000 stake is not.
    assert res.n_bets <= 4


def test_all_progressions_see_identical_draws():
    """The comparison must isolate the sizing rule, not luck."""
    from qt.sizing import compare_progressions

    a = compare_progressions(win_rate=0.5, n_bets=200, n_paths=100, seed=7)
    b = compare_progressions(win_rate=0.5, n_bets=200, n_paths=100, seed=7)
    pd.testing.assert_frame_equal(a, b)


# ------------------------------------------------------------------------ ruin
def test_no_edge_means_certain_ruin_regardless_of_bet_size():
    from qt.sizing import risk_of_ruin

    assert risk_of_ruin(0.5, 1.0, bet_fraction=0.001) == 1.0
    assert risk_of_ruin(0.45, 1.0, bet_fraction=0.001) == 1.0


def test_risk_of_ruin_falls_as_bets_get_smaller():
    from qt.sizing import risk_of_ruin

    big = risk_of_ruin(0.55, 1.0, bet_fraction=0.10)
    small = risk_of_ruin(0.55, 1.0, bet_fraction=0.01)
    assert small < big


def test_kelly_matches_the_closed_form():
    from qt.sizing import kelly_fraction

    # p=0.55, b=1 => f* = p - (1-p)/b = 0.10
    k = kelly_fraction(0.55, 1.0)
    assert k["full_kelly"] == pytest.approx(0.10, abs=1e-9)
    assert k["fractional_kelly"] == pytest.approx(0.025, abs=1e-9)
    # Quarter Kelly keeps a large share of the growth for a quarter of the stake.
    assert 0.3 < k["growth_retained"] < 0.6


def test_overbetting_kelly_destroys_a_winning_edge():
    """Past the Kelly peak, a positive edge compounds downward."""
    from qt.sizing import risk_of_ruin_simulation

    at_kelly = risk_of_ruin_simulation(0.55, 1.0, bet_fraction=0.10, n_paths=1500, n_bets=500, seed=3)
    over = risk_of_ruin_simulation(0.55, 1.0, bet_fraction=0.35, n_paths=1500, n_bets=500, seed=3)
    assert over["median_final"] < 1.0, "over-betting must lose despite the edge"
    assert over["median_final"] < at_kelly["median_final"]


def test_optimal_f_is_bounded_by_the_worst_trade():
    from qt.sizing import optimal_f

    rng = np.random.default_rng(4)
    trades = pd.Series(rng.normal(0.01, 0.05, 500))
    res = optimal_f(trades)
    assert 0 < res["optimal_f"] < 1
    assert res["worst_trade"] < 0
    assert res["quarter_f"] == pytest.approx(res["optimal_f"] / 4)


# -------------------------------------------------------------- regime switching
def test_regime_model_separates_planted_volatility_states():
    from qt.econometrics import fit_regimes

    rng = np.random.default_rng(5)
    calm = rng.normal(0.0, 0.005, 1500)
    wild = rng.normal(0.0, 0.030, 1500)
    # Blocks, not interleaved: a Markov chain needs persistence to identify states.
    series = pd.Series(np.concatenate([calm, wild, calm, wild]))

    fit = fit_regimes(series, n_states=2)
    assert fit.n_states == 2
    lo, hi = fit.volatilities.min(), fit.volatilities.max()
    assert hi / lo > 3.0, f"states not separated: {fit.volatilities.to_dict()}"
    # Transition rows are probabilities.
    assert np.allclose(fit.transition_matrix.to_numpy().sum(axis=0), 1.0, atol=1e-6)
    assert (fit.expected_durations > 1).all()


def test_regime_labels_are_by_property_not_by_index():
    """Labels must describe what a state IS, so they survive a refit reordering."""
    from qt.econometrics import fit_regimes

    rng = np.random.default_rng(6)
    series = pd.Series(
        np.concatenate([rng.normal(0, 0.004, 1200), rng.normal(0, 0.025, 1200)] * 2)
    )
    fit = fit_regimes(series, n_states=2)
    labels = set(fit.labels.values())
    assert any("calm" in x for x in labels)
    assert any("turbulent" in x for x in labels)
    # The calm label must attach to the genuinely lower-volatility state.
    calm_state = [k for k, v in fit.labels.items() if "calm" in v][0]
    assert fit.volatilities[calm_state] == fit.volatilities.min()


def test_regime_probabilities_are_causal():
    """Truncating the series must not change earlier regime labels."""
    from qt.econometrics import regime_probabilities

    rng = np.random.default_rng(7)
    series = pd.Series(
        np.concatenate([rng.normal(0, 0.004, 900), rng.normal(0, 0.02, 900)] * 2)
    )
    full = regime_probabilities(series, n_states=2, lookback=900, refit_every=600, min_train=600)
    part = regime_probabilities(series.iloc[:2400], n_states=2, lookback=900,
                                refit_every=600, min_train=600)

    shared = part.index[part["vol_rank"].notna()]
    if len(shared) == 0:
        pytest.skip("no labelled overlap on this sample")
    np.testing.assert_allclose(
        full.loc[shared, "vol_rank"].to_numpy(),
        part.loc[shared, "vol_rank"].to_numpy(),
        equal_nan=True,
    )


# ------------------------------------------------------------ portfolio backtest
def test_portfolio_weights_are_trailing_only(panel):
    """Weights at time t must not change when later prices are removed."""
    from qt.backtest import AllocationSpec, build_weights

    closes = pd.DataFrame({k: v["close"] for k, v in panel.items()})
    spec = AllocationSpec(lookback=300, rebalance_every=200, min_history=200)

    full, _ = build_weights(closes, spec)
    part, _ = build_weights(closes.iloc[:1000], spec)
    shared = part.index
    np.testing.assert_allclose(
        full.loc[shared].to_numpy(), part.to_numpy(), equal_nan=True, rtol=1e-9
    )


def test_portfolio_backtest_runs_and_respects_weight_caps(panel):
    from qt.backtest import AllocationSpec, BacktestConfig, run_portfolio_backtest

    spec = AllocationSpec(method="risk_parity", lookback=300, rebalance_every=200, min_history=200)
    res = run_portfolio_backtest(panel, spec, BacktestConfig(bars_per_year=365 * 24))

    assert not res.weights.empty
    assert res.weights.abs().sum(axis=1).max() <= 1.0 + 1e-6
    assert "sharpe" in res.metrics
    assert not res.diagnostics.empty


def test_allocator_comparison_covers_every_method(panel):
    from qt.backtest import ALLOCATORS, AllocationSpec, BacktestConfig, compare_allocations

    spec = AllocationSpec(lookback=300, rebalance_every=250, min_history=200)
    table = compare_allocations(panel, spec=spec, config=BacktestConfig(bars_per_year=365 * 24))
    assert set(table.index) == set(ALLOCATORS)
    assert "turnover_annual" in table.columns


# ---------------------------------------------------------------- feed health
def test_health_monitor_flags_a_silent_feed():
    import time

    from qt.live import HealthMonitor

    monitor = HealthMonitor(stale_after_seconds=0.05)
    monitor.record_data()
    assert monitor.trading_allowed

    time.sleep(0.1)
    status = monitor.status()
    assert not status.healthy
    assert "no data" in status.reason
    assert not monitor.trading_allowed


def test_health_monitor_flags_repeated_failures():
    from qt.live import HealthMonitor

    monitor = HealthMonitor(max_consecutive_failures=3)
    for _ in range(3):
        monitor.record_failure(ConnectionError("dropped"))
    assert not monitor.trading_allowed
    # A successful bar clears the streak.
    monitor.record_data()
    assert monitor.trading_allowed


def test_reconnect_backoff_grows_and_is_capped():
    from qt.live import ReconnectPolicy

    policy = ReconnectPolicy(initial_seconds=1.0, max_seconds=30.0, jitter=0.0)
    assert policy.delay(0) == pytest.approx(1.0)
    assert policy.delay(1) == pytest.approx(2.0)
    assert policy.delay(2) == pytest.approx(4.0)
    assert policy.delay(20) == pytest.approx(30.0)  # capped


def test_reconnect_jitter_desynchronises_clients():
    """Without jitter every client retries at the same instant and is refused again."""
    from qt.live import ReconnectPolicy

    policy = ReconnectPolicy(initial_seconds=10.0, jitter=0.3)
    delays = {policy.delay(1) for _ in range(50)}
    assert len(delays) > 40, "jitter is not producing distinct delays"


def test_cross_venue_check_flags_disagreement():
    from qt.live import CrossVenueCheck

    check = CrossVenueCheck(tolerance_bps=50.0)
    check.update("binance", 100.0)
    check.update("coinbase", 100.2)
    assert check.check()["agree"]

    check.update("coinbase", 105.0)  # 500bps apart: a bad print, not an arbitrage
    result = check.check()
    assert not result["agree"]
    assert result["spread_bps"] > 400


def test_cross_venue_check_needs_two_fresh_venues():
    from qt.live import CrossVenueCheck

    check = CrossVenueCheck()
    check.update("binance", 100.0)
    assert check.check()["agree"]  # cannot disagree with itself
    assert check.check()["n_venues"] == 1
