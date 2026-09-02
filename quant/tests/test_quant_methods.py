"""Tests for the quantitative-methods layer.

Each test is built around a case where the *right answer is known analytically*, so the
test checks correctness rather than merely that the code runs:

* a random walk must fail an ADF test; its differences must pass one;
* two series built to be cointegrated must be detected as such, two independent random
  walks must not;
* a GARCH fit on data simulated from known parameters must recover them;
* Heston with vol-of-vol driven to zero must reproduce Black-Scholes exactly;
* Almgren-Chriss with zero risk aversion must reduce to TWAP;
* risk contributions must sum to one, and equal-risk-contribution weights must produce
  equal contributions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------- econometrics
def test_random_walk_is_non_stationary_but_its_returns_are():
    from qt.econometrics import stationarity_report

    rng = np.random.default_rng(0)
    walk = pd.Series(np.cumsum(rng.standard_normal(2000)) + 100)

    assert stationarity_report(walk)["verdict"] in ("non-stationary", "inconclusive")
    assert stationarity_report(walk.diff().dropna())["verdict"] == "stationary"


def test_variance_ratio_detects_trending_and_mean_reverting_series():
    from qt.econometrics import variance_ratio_test

    rng = np.random.default_rng(1)
    n = 4000

    # Trending: positively autocorrelated increments.
    shocks = rng.standard_normal(n)
    trend = np.zeros(n)
    for i in range(1, n):
        trend[i] = 0.4 * trend[i - 1] + shocks[i]
    trending = pd.Series(np.exp(np.cumsum(trend) * 0.01) * 100)

    # Mean-reverting: negatively autocorrelated increments.
    rev = np.zeros(n)
    for i in range(1, n):
        rev[i] = -0.4 * rev[i - 1] + shocks[i]
    reverting = pd.Series(np.exp(np.cumsum(rev) * 0.01) * 100)

    assert variance_ratio_test(trending, q=4).statistic > 1.0
    assert variance_ratio_test(reverting, q=4).statistic < 1.0


def test_half_life_recovers_a_known_ar1_decay():
    from qt.econometrics import half_life

    rng = np.random.default_rng(2)
    phi = 0.95  # implies half-life = ln(0.5)/ln(0.95) ~= 13.5
    x = np.zeros(5000)
    for i in range(1, x.size):
        x[i] = phi * x[i - 1] + rng.standard_normal() * 0.1

    expected = np.log(0.5) / np.log(phi)
    assert half_life(pd.Series(x)) == pytest.approx(expected, rel=0.15)


def test_cointegration_found_when_present_and_not_when_absent():
    from qt.econometrics import engle_granger

    rng = np.random.default_rng(3)
    n = 1500
    common = np.cumsum(rng.standard_normal(n)) * 0.01 + 5.0

    # a and b share a stochastic trend => cointegrated.
    a = pd.Series(np.exp(common + rng.standard_normal(n) * 0.01), name="A")
    b = pd.Series(np.exp(common * 0.7 + rng.standard_normal(n) * 0.01), name="B")
    assert engle_granger(a, b, name_a="A", name_b="B").cointegrated

    # Independent random walks => not cointegrated. Tested over 20 independent draws
    # because the test has a genuine false-positive rate: asserting on a single pair
    # would make this suite flaky rather than correct. With the two-orientation
    # Bonferroni correction in place, false positives must stay near the 5% nominal
    # rate rather than the ~10% an uncorrected min-of-two would give.
    false_positives = 0
    for _ in range(20):
        c = pd.Series(np.exp(np.cumsum(rng.standard_normal(n)) * 0.01 + 5), name="C")
        d = pd.Series(np.exp(np.cumsum(rng.standard_normal(n)) * 0.01 + 5), name="D")
        if engle_granger(c, d, name_a="C", name_b="D").cointegrated:
            false_positives += 1
    assert false_positives <= 4, f"{false_positives}/20 spurious cointegrations — correction is not working"


def test_cointegration_result_rejects_the_wrong_asset_order():
    """The orientation guard: silently building the wrong spread must be impossible."""
    from qt.econometrics import engle_granger

    rng = np.random.default_rng(4)
    common = np.cumsum(rng.standard_normal(800)) * 0.01 + 5
    a = pd.Series(np.exp(common + rng.standard_normal(800) * 0.01), name="A")
    b = pd.Series(np.exp(common * 0.7 + rng.standard_normal(800) * 0.01), name="B")

    res = engle_granger(a, b, name_a="A", name_b="B")
    frame = pd.DataFrame({"A": a, "B": b})
    spread = res.spread(frame)  # by name: always correct, whatever the orientation
    assert spread.notna().any()
    assert np.isfinite(res.raw_pvalue) and res.pvalue >= res.raw_pvalue

    wrong_first = frame[res.asset_b]  # deliberately the wrong leg first
    wrong_second = frame[res.asset_a]
    with pytest.raises(ValueError):
        res.spread(wrong_first, wrong_second)


def test_garch_recovers_known_simulated_parameters():
    from qt.econometrics import fit_garch

    rng = np.random.default_rng(5)
    omega, alpha, beta = 0.05, 0.10, 0.85
    n = 20_000
    var = np.zeros(n)
    ret = np.zeros(n)
    var[0] = omega / (1 - alpha - beta)
    for t in range(1, n):
        var[t] = omega + alpha * ret[t - 1] ** 2 + beta * var[t - 1]
        ret[t] = np.sqrt(var[t]) * rng.standard_normal()

    # The fitter rescales by 100 internally, so simulate in the same (percent) units.
    fit = fit_garch(pd.Series(ret / 100.0))
    assert fit.converged
    assert fit.params["alpha"] == pytest.approx(alpha, abs=0.05)
    assert fit.params["beta"] == pytest.approx(beta, abs=0.05)
    assert fit.persistence == pytest.approx(alpha + beta, abs=0.03)


def test_garch_beats_ewma_on_qlike_for_garch_data():
    """A fitted model should beat the no-parameter benchmark on data it truly generated."""
    from qt.econometrics import fit_ewma, fit_garch, volatility_forecast_score

    rng = np.random.default_rng(6)
    n = 15_000
    var = np.zeros(n)
    ret = np.zeros(n)
    var[0] = 1.0
    for t in range(1, n):
        var[t] = 0.05 + 0.12 * ret[t - 1] ** 2 + 0.83 * var[t - 1]
        ret[t] = np.sqrt(var[t]) * rng.standard_normal()
    series = pd.Series(ret / 100.0)

    garch = volatility_forecast_score(series, fit_garch(series))["qlike"]
    ewma = volatility_forecast_score(series, fit_ewma(series))["qlike"]
    assert garch < ewma, f"GARCH qlike {garch:.4f} should beat EWMA {ewma:.4f} on GARCH data"


def test_kalman_hedge_is_smoother_than_rolling_ols():
    from qt.econometrics import KalmanHedge, rolling_ols_beta

    rng = np.random.default_rng(7)
    n = 3000
    x = np.cumsum(rng.standard_normal(n)) * 0.01 + 5
    beta_true = 0.8 + 0.2 * np.sin(np.arange(n) / 500)  # a genuinely drifting relationship
    y = beta_true * x + rng.standard_normal(n) * 0.02

    xs, ys = pd.Series(x, name="x"), pd.Series(y, name="y")
    kalman = KalmanHedge(delta=1e-4).run(ys, xs).beta["slope"]
    rolling = rolling_ols_beta(ys, xs, window=200)

    # Both track the true beta, but the Kalman path is far less jumpy.
    assert kalman.diff().std() < rolling.diff().std()


def test_ou_fit_recovers_known_parameters():
    from qt.econometrics import fit_ou

    rng = np.random.default_rng(8)
    theta, mu, sigma = 0.05, 2.0, 0.3
    n = 20_000
    x = np.zeros(n)
    x[0] = mu
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + sigma * rng.standard_normal()

    fit = fit_ou(pd.Series(x))
    assert fit.is_mean_reverting
    assert fit.mu == pytest.approx(mu, abs=0.3)
    assert fit.theta == pytest.approx(theta, rel=0.25)
    assert fit.half_life == pytest.approx(np.log(2) / theta, rel=0.25)


def test_optimal_thresholds_refuses_when_costs_exceed_the_opportunity():
    from qt.econometrics import fit_ou, optimal_thresholds

    rng = np.random.default_rng(9)
    # A tiny-amplitude spread: no threshold can clear a 1% round trip.
    x = np.zeros(5000)
    for t in range(1, x.size):
        x[t] = x[t - 1] + 0.1 * (0.0 - x[t - 1]) + 0.0001 * rng.standard_normal()

    fit = fit_ou(pd.Series(x))
    result = optimal_thresholds(fit, cost=0.01)
    assert not result["viable"]
    # And nothing enticing is reported alongside the rejection.
    assert not np.isfinite(result["expected_annual_return"])


# ------------------------------------------------------------------- portfolio
def test_risk_contributions_sum_to_one():
    from qt.portfolio import risk_contributions

    rng = np.random.default_rng(10)
    rets = pd.DataFrame(rng.standard_normal((500, 4)) * 0.01, columns=list("ABCD"))
    cov = rets.cov()
    w = pd.Series([0.4, 0.3, 0.2, 0.1], index=list("ABCD"))
    assert risk_contributions(w, cov).sum() == pytest.approx(1.0, abs=1e-9)


def test_risk_parity_equalises_risk_contributions():
    from qt.portfolio import risk_contributions, risk_parity

    rng = np.random.default_rng(11)
    # Deliberately unequal volatilities, so equal weights would NOT be equal risk.
    scales = np.array([0.005, 0.02, 0.04, 0.01])
    rets = pd.DataFrame(rng.standard_normal((2000, 4)) * scales, columns=list("ABCD"))
    cov = rets.cov()

    w = risk_parity(cov)
    rc = risk_contributions(w, cov)
    assert rc.max() - rc.min() < 0.01, f"risk contributions not equalised: {rc.to_dict()}"
    # The high-vol asset must get the smallest weight.
    assert w.idxmin() == "C"


def test_effective_number_of_bets_collapses_when_assets_are_correlated():
    from qt.portfolio import effective_number_of_bets, equal_weight

    rng = np.random.default_rng(12)
    n = 3000
    common = rng.standard_normal(n)

    # Nearly identical assets: 5 tickers, one bet.
    correlated = pd.DataFrame(
        {f"A{i}": common * 0.99 + rng.standard_normal(n) * 0.14 for i in range(5)}
    )
    # Independent assets with DISTINCT volatilities: 5 tickers, five bets. The
    # volatilities must differ, otherwise the covariance is isotropic, the eigenbasis
    # is arbitrary and the measure is undefined (see effective_number_of_bets).
    scales = np.array([0.5, 0.8, 1.0, 1.3, 1.7])
    independent = pd.DataFrame(
        {f"B{i}": rng.standard_normal(n) * scales[i] for i in range(5)}
    )

    w_corr = equal_weight(correlated.columns)
    w_ind = equal_weight(independent.columns)
    bets_corr = effective_number_of_bets(w_corr, correlated.cov())
    bets_ind = effective_number_of_bets(w_ind, independent.cov())

    assert bets_corr < 2.0, f"correlated book should be ~1 bet, got {bets_corr:.2f}"
    # Not exactly 5: equal *capital* weights on unequal volatilities are not equal
    # *risk* weights, so some entropy is lost even with zero correlation.
    assert bets_ind > 3.5, f"independent book should be close to 5 bets, got {bets_ind:.2f}"
    assert bets_ind > 2 * bets_corr


def test_minimum_variance_has_the_lowest_variance():
    from qt.portfolio import equal_weight, minimum_variance, portfolio_volatility, risk_parity

    rng = np.random.default_rng(13)
    scales = np.array([0.004, 0.01, 0.03, 0.02, 0.008])
    rets = pd.DataFrame(rng.standard_normal((3000, 5)) * scales, columns=list("ABCDE"))
    cov = rets.cov()

    mv = portfolio_volatility(minimum_variance(cov), cov)
    assert mv <= portfolio_volatility(equal_weight(cov.index), cov) + 1e-12
    assert mv <= portfolio_volatility(risk_parity(cov), cov) + 1e-12


def test_hrp_produces_valid_weights_on_a_correlated_panel():
    from qt.portfolio import hierarchical_risk_parity

    rng = np.random.default_rng(14)
    n = 2000
    block1 = rng.standard_normal(n)
    block2 = rng.standard_normal(n)
    rets = pd.DataFrame(
        {
            "A1": block1 + rng.standard_normal(n) * 0.3,
            "A2": block1 + rng.standard_normal(n) * 0.3,
            "B1": block2 + rng.standard_normal(n) * 0.3,
            "B2": block2 + rng.standard_normal(n) * 0.3,
        }
    )
    w = hierarchical_risk_parity(rets.cov())
    assert w.sum() == pytest.approx(1.0, abs=1e-9)
    assert (w >= 0).all()
    # Two clusters of two: each cluster should get roughly half the capital.
    assert abs((w["A1"] + w["A2"]) - 0.5) < 0.15


def test_black_litterman_without_views_returns_the_market_portfolio():
    from qt.portfolio import black_litterman

    rng = np.random.default_rng(15)
    rets = pd.DataFrame(rng.standard_normal((1000, 4)) * 0.01, columns=list("ABCD"))
    cov = rets.cov()
    market = pd.Series([0.5, 0.25, 0.15, 0.10], index=list("ABCD"))

    result = black_litterman(cov, market, views=None)
    assert np.allclose(result.weights.to_numpy(), market.to_numpy(), atol=1e-9)
    assert np.allclose(result.tilt().to_numpy(), 0.0, atol=1e-9)


def test_black_litterman_view_tilts_the_portfolio_in_its_direction():
    from qt.portfolio import View, black_litterman

    rng = np.random.default_rng(16)
    rets = pd.DataFrame(rng.standard_normal((1000, 3)) * 0.01, columns=list("ABC"))
    cov = rets.cov()
    market = pd.Series([0.5, 0.3, 0.2], index=list("ABC"))

    view = View({"B": 1.0, "A": -1.0}, value=0.10, confidence=0.8)
    result = black_litterman(cov, market, [view], allow_short=True)

    # B is expected to outperform A, so B's posterior return must exceed its
    # equilibrium return and A's must fall.
    assert result.posterior_returns["B"] > result.equilibrium_returns["B"]
    assert result.posterior_returns["A"] < result.equilibrium_returns["A"]


def test_cvar_is_worse_than_var():
    from qt.portfolio import conditional_value_at_risk, value_at_risk

    rng = np.random.default_rng(17)
    returns = pd.Series(rng.standard_t(df=3, size=5000) * 0.01)
    var = value_at_risk(returns, 0.95, "historical")
    cvar = conditional_value_at_risk(returns, 0.95)
    assert cvar < var, "expected shortfall must be worse than the VaR threshold"


def test_denoising_finds_the_planted_factor_structure():
    from qt.portfolio import denoise_covariance

    rng = np.random.default_rng(18)
    n, k = 2000, 12
    factor = rng.standard_normal(n)
    # One strong common factor plus idiosyncratic noise.
    data = pd.DataFrame(
        {f"A{i}": factor * 0.8 + rng.standard_normal(n) * 0.6 for i in range(k)}
    )
    out = denoise_covariance(data)
    assert out["n_factors"] >= 1
    assert out["market_factor_share"] > 0.3


# ----------------------------------------------------------------- derivatives
def test_put_call_parity_holds_for_black_scholes():
    from qt.derivatives import black_scholes_price, put_call_parity_check

    S, K, T, r, sigma = 100.0, 95.0, 0.5, 0.03, 0.5
    call = black_scholes_price(S, K, T, r, sigma, "call")
    put = black_scholes_price(S, K, T, r, sigma, "put")
    assert put_call_parity_check(call, put, S, K, T, r)["holds"]


def test_implied_vol_inverts_the_pricer_exactly():
    from qt.derivatives import black_scholes_price, implied_volatility

    S, T, r = 100.0, 0.4, 0.02
    for K in (70, 100, 140):
        for sigma in (0.2, 0.6, 1.2):
            price = black_scholes_price(S, K, T, r, sigma, "call")
            assert implied_volatility(price, S, K, T, r, "call") == pytest.approx(sigma, abs=1e-6)


def test_implied_vol_returns_nan_for_arbitrage_violating_prices():
    from qt.derivatives import implied_volatility

    # A call cannot be worth more than the spot.
    assert np.isnan(implied_volatility(150.0, 100.0, 100.0, 0.5, 0.0, "call"))


def test_heston_reduces_to_black_scholes_as_vol_of_vol_vanishes():
    """The decisive correctness test for the Fourier pricer."""
    from qt.derivatives import HestonParams, black_scholes_price, heston_price

    S, T, r, vol = 100.0, 0.5, 0.0, 0.6
    params = HestonParams(v0=vol**2, kappa=3.0, theta=vol**2, sigma=1e-4, rho=0.0)
    for K in (80, 100, 120):
        heston = heston_price(S, K, T, r, params, "call")
        bs = black_scholes_price(S, K, T, r, vol, "call")
        assert heston == pytest.approx(bs, abs=1e-3), f"K={K}: heston={heston} bs={bs}"


def test_heston_rho_controls_the_direction_of_skew():
    from qt.derivatives import HestonParams, heston_implied_vol

    S, T, r = 100.0, 0.5, 0.0
    forward = S

    def wing_gap(rho: float) -> float:
        p = HestonParams(v0=0.36, kappa=2.0, theta=0.36, sigma=0.8, rho=rho)
        down = heston_implied_vol(S, forward * np.exp(-0.2), T, r, p)
        up = heston_implied_vol(S, forward * np.exp(0.2), T, r, p)
        return down - up

    assert wing_gap(-0.7) > 0.01, "negative rho must produce downside skew"
    assert wing_gap(0.7) < -0.01, "positive rho must produce upside skew"


def test_merton_jumps_lift_short_dated_wings_more_than_long_dated():
    """The phenomenon a pure diffusion cannot reproduce."""
    from qt.derivatives import MertonJumpParams, merton_implied_vol

    S, r = 100.0, 0.0
    params = MertonJumpParams(sigma=0.5, lam=2.0, mu_j=-0.10, sigma_j=0.15)

    def wing_lift(T: float) -> float:
        atm = merton_implied_vol(S, 100.0, T, r, params)
        wing = merton_implied_vol(S, 70.0, T, r, params)
        return wing - atm

    assert wing_lift(7 / 365) > wing_lift(90 / 365) + 0.05


def test_variance_swap_strike_equals_flat_vol_on_a_flat_smile():
    """The identity the replication must satisfy."""
    from qt.derivatives import fit_svi, variance_swap_strike

    T, vol = 0.25, 0.6
    k = np.linspace(-0.5, 0.5, 15)
    smile = fit_svi(k, np.full_like(k, vol), T)
    assert variance_swap_strike(smile, width=1.5) == pytest.approx(vol, abs=0.01)


def test_svi_fit_recovers_a_known_smile():
    from qt.derivatives import fit_svi

    T = 0.25
    k = np.linspace(-0.4, 0.4, 15)
    true = 0.6 + 0.3 * k**2 - 0.15 * k
    svi = fit_svi(k, true, T)
    assert np.sqrt(np.mean((svi.implied_vol(k) - true) ** 2)) < 0.005
    assert svi.skew(0.0) < 0  # downside skew, as constructed


# ------------------------------------------------------------------- execution
def test_almgren_chriss_reduces_to_twap_at_zero_risk_aversion():
    from qt.execution import almgren_chriss, twap_schedule

    sched = almgren_chriss(
        1000.0, 10, volatility=0.5, temporary_impact=1e-4, risk_aversion=0.0
    )
    twap = twap_schedule(1000.0, 10)
    assert np.allclose(sched.trades.to_numpy(), twap.to_numpy(), rtol=1e-9)


def test_higher_risk_aversion_front_loads_execution():
    from qt.execution import almgren_chriss

    def front_loading(lam: float) -> float:
        s = almgren_chriss(1000.0, 20, volatility=1.0, temporary_impact=1e-3, risk_aversion=lam)
        return s.summary()["front_loading"]

    assert front_loading(1e-2) > front_loading(1e-6) + 0.05


def test_execution_frontier_trades_cost_against_certainty():
    from qt.execution import efficient_frontier

    frontier = efficient_frontier(
        1000.0, 20, volatility=1.0, temporary_impact=1e-3,
        risk_aversions=np.logspace(-6, -1, 12),
    )
    # More risk aversion => lower cost variance, higher expected cost. A real frontier.
    assert frontier["cost_std"].is_monotonic_decreasing
    assert frontier["expected_cost"].iloc[-1] > frontier["expected_cost"].iloc[0]


def test_pov_schedule_respects_the_participation_cap():
    from qt.execution import pov_schedule

    volume = pd.Series([1000.0] * 20)
    out = pov_schedule(500.0, volume, participation_rate=0.1)
    assert (out["participation"] <= 0.1 + 1e-9).all()
    assert out.attrs["completed"]


def test_implementation_shortfall_separates_delay_from_execution():
    from qt.execution import implementation_shortfall

    fills = pd.DataFrame({"price": [101.0, 101.5], "quantity": [50.0, 50.0]})
    out = implementation_shortfall(fills, decision_price=100.0, arrival_price=100.8, side=1)
    assert out["delay_cost_bps"] == pytest.approx(80.0, abs=1e-6)
    assert out["execution_cost_bps"] == pytest.approx(45.0, abs=1e-6)
    assert out["total_shortfall_bps"] == pytest.approx(125.0, abs=1e-6)


def test_inventory_skew_bounds_a_market_maker_position():
    """The whole point of Avellaneda-Stoikov: symmetric quoting lets inventory run."""
    from qt.execution import simulate_market_making

    rng = np.random.default_rng(19)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.standard_normal(1500) * 0.002)))

    skewed = simulate_market_making(prices, gamma=0.5, seed=1, symmetric=False)
    symmetric = simulate_market_making(prices, gamma=0.5, seed=1, symmetric=True)
    assert skewed["max_abs_inventory"] <= symmetric["max_abs_inventory"]


def test_reservation_price_leans_against_inventory():
    from qt.execution import avellaneda_stoikov_quotes

    long_book = avellaneda_stoikov_quotes(100.0, inventory=10.0, volatility=1.0)
    short_book = avellaneda_stoikov_quotes(100.0, inventory=-10.0, volatility=1.0)
    assert long_book.reservation_price < 100.0  # long => keen to sell
    assert short_book.reservation_price > 100.0  # short => keen to buy


# -------------------------------------------------------------------- statarb
def test_statarb_rejects_an_uncointegrated_pair():
    from qt.strategies import PairSpec, analyse_pair

    rng = np.random.default_rng(20)
    n = 1200
    prices = pd.DataFrame(
        {
            "A": np.exp(np.cumsum(rng.standard_normal(n)) * 0.01 + 5),
            "B": np.exp(np.cumsum(rng.standard_normal(n)) * 0.01 + 5),
        }
    )
    analysis = analyse_pair(prices, PairSpec("A", "B"))
    assert not analysis.tradeable
    assert analysis.reasons


def test_statarb_detects_a_constructed_tradeable_pair():
    from qt.strategies import PairSpec, analyse_pair

    rng = np.random.default_rng(21)
    n = 3000
    common = np.cumsum(rng.standard_normal(n)) * 0.01 + 5
    # A fast-reverting spread with meaningful amplitude: this one should pass.
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = spread[t - 1] + 0.15 * (0.0 - spread[t - 1]) + 0.05 * rng.standard_normal()

    prices = pd.DataFrame({"A": np.exp(common + spread), "B": np.exp(common)})
    analysis = analyse_pair(prices, PairSpec("A", "B", round_trip_cost=0.0005, max_half_life=100))
    assert analysis.cointegrated
    assert np.isfinite(analysis.half_life) and analysis.half_life < 100


def test_pair_signal_is_causal():
    """Truncating the price history must not change any earlier signal value."""
    from qt.strategies import PairSpec, pair_signal

    rng = np.random.default_rng(22)
    n = 2000
    common = np.cumsum(rng.standard_normal(n)) * 0.01 + 5
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = spread[t - 1] + 0.1 * (0.0 - spread[t - 1]) + 0.05 * rng.standard_normal()
    prices = pd.DataFrame({"A": np.exp(common + spread), "B": np.exp(common)})

    spec = PairSpec("A", "B", lookback=300, refit_every=100)
    full = pair_signal(prices, spec)
    partial = pair_signal(prices.iloc[:1400], spec)

    shared = partial.index
    np.testing.assert_allclose(
        full.loc[shared, "position_a"].to_numpy(),
        partial["position_a"].to_numpy(),
        equal_nan=True,
    )
