"""The research machinery: trial accounting, sealed periods, best-of-N tests, pipeline."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qt.lab.database import HoldoutAlreadyConsulted, ResearchDB
from qt.lab.markets import AssetClass, CostProfile, load_markets, load_protocol, prepare_bars
from qt.lab.montecarlo import block_monte_carlo, trade_monte_carlo
from qt.lab.pipeline import Lab
from qt.lab.regimes import label_regimes
from qt.lab.robustness import perturb_params
from qt.lab.significance import reality_check_spa

ROOT = Path(__file__).resolve().parents[1]


def test_trials_accumulate_and_nothing_can_be_deleted():
    db = ResearchDB()
    c1 = db.start_cycle("p", "m")
    for i in range(3):
        db.record_experiment(cycle_id=c1, stage="grid", strategy="s", family="f", market="m",
                             parameters={"i": i}, metrics={"sharpe": 0.1 * i})
    db.record_experiment(cycle_id=c1, stage="robustness", strategy="s", family="f", market="m",
                         parameters={}, metrics={"sharpe": 5.0}, counts_as_trial=False)
    c2 = db.start_cycle("p", "m")
    db.record_experiment(cycle_id=c2, stage="grid", strategy="t", family="f", market="m",
                         parameters={}, metrics={"sharpe": -0.2})
    assert db.n_trials() == 4  # cumulative across cycles, sensitivity runs excluded
    assert sorted(db.trial_sharpes()) == pytest.approx([-0.2, 0.0, 0.1, 0.2])
    assert not any(name.startswith("delete") for name in dir(db))


def test_holdout_can_be_consulted_once():
    db = ResearchDB()
    cid = db.start_cycle("p", "m")
    db.consult(period="holdout", strategy="s", market="fx", cycle_id=cid, result={"sharpe": 0.3})
    with pytest.raises(HoldoutAlreadyConsulted):
        db.consult(period="holdout", strategy="s", market="fx", cycle_id=cid, result={"sharpe": 0.9})
    # A later cycle cannot reuse it either.
    c2 = db.start_cycle("p", "m")
    with pytest.raises(HoldoutAlreadyConsulted):
        db.consult(period="holdout", strategy="s", market="fx", cycle_id=c2, result={})


def test_reality_check_does_not_reject_pure_noise():
    rng = np.random.default_rng(0)
    R = pd.DataFrame(rng.normal(0, 0.01, (1500, 20)))
    out = reality_check_spa(R, n_boot=300, seed=1)
    assert out["rc_pvalue"] > 0.10 and out["spa_pvalue"] > 0.05


def test_spa_detects_one_real_edge_among_noise():
    rng = np.random.default_rng(0)
    R = pd.DataFrame(rng.normal(0, 0.01, (1500, 20)))
    R[5] += 0.0015  # Sharpe ~2.4 annualised
    out = reality_check_spa(R, n_boot=300, seed=1)
    assert out["spa_pvalue"] < 0.05
    assert out["best_model"] == "5"


def test_param_perturbations_move_integers_and_skip_booleans():
    out = perturb_params({"n": 20, "k": 2.0, "use_atr": True}, 0.05)
    labels = [l for l, _ in out]
    assert all("use_atr" not in l for l in labels)
    ns = {cfg["n"] for _, cfg in out if cfg["n"] != 20}
    assert ns == {21, 19}


def test_monte_carlo_ruin_rises_with_leverage():
    rng = np.random.default_rng(0)
    t = pd.DataFrame({"gross": rng.normal(0.002, 0.02, 300), "cost": np.full(300, 0.0005)})
    lo = trade_monte_carlo(t, years=5, n_paths=300)
    hi = trade_monte_carlo(t.assign(gross=t.gross * 4, cost=t.cost * 4), years=5, n_paths=300)
    assert hi["prob_drawdown_beyond"]["25%"] >= lo["prob_drawdown_beyond"]["25%"]
    r = pd.Series(rng.normal(0.0003, 0.01, 2500))
    b = block_monte_carlo(r, ppy=252, n_paths=200)
    assert b["max_drawdown"][0.05] <= b["max_drawdown"][0.5]


def test_regime_labels_are_causal():
    rng = np.random.default_rng(0)
    p = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, 1500))),
                  index=pd.date_range("2000-01-01", periods=1500, freq="B"))
    full = label_regimes(p)
    cut = label_regimes(p.iloc[:1000])
    pd.testing.assert_frame_equal(full.iloc[:1000], cut)


def _synthetic_class(n_symbols=3, n=4000, seed=0, edge=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2005-01-03", periods=n, tz="UTC")
    data = {}
    for k in range(n_symbols):
        r = rng.normal(0, 0.01, n)
        if edge:
            # Momentum with a known edge: tomorrow's drift follows the sign of the last 20 days.
            s = np.sign(pd.Series(r).rolling(20).sum().shift(1).fillna(0)).to_numpy()
            r = r + edge * s
        close = 100 * np.exp(np.cumsum(r))
        open_ = np.concatenate([[100], close[:-1]])
        hi = np.maximum(open_, close) * 1.003
        lo = np.minimum(open_, close) * 0.997
        df = pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close,
                           "volume": rng.lognormal(12, 0.2, n), "adj_close": close}, index=idx)
        data[f"S{k}"] = prepare_bars(df, use_adjusted=False)
    return data


def _lab(data, hyps, open_sealed=False):
    ac = AssetClass("synthetic", tuple(data), CostProfile(0.5, 0.5, 0.5), 252, True)
    db = ResearchDB()
    cid = db.start_cycle("t", "t")
    lab = Lab(db, cid, load_protocol(), {"synthetic": ac}, hypotheses=hyps, data={"synthetic": data},
              log=lambda m: None, open_sealed=open_sealed)
    lab.audits["synthetic"] = {}
    return lab, db


def test_pipeline_rejects_noise():
    lab, db = _lab(_synthetic_class(seed=3), ["sma_cross", "rsi2", "donchian"])
    lab.screen()
    lab.best_of_n()
    lab.validate()
    assert db.n_trials() == sum(len(c.configs) for c in lab.candidates)
    assert all(c.decision != "PAPER_TEST" for c in lab.candidates)


def test_pipeline_finds_a_planted_edge_and_seals_test_periods():
    lab, db = _lab(_synthetic_class(seed=4, n=5600, edge=0.0015), ["tsmom"], open_sealed=True)
    lab.screen()
    c = lab.candidates[0]
    assert c.decision == "PROMISING", c.reasons
    lab.validate()
    assert c.decision == "PAPER_TEST", c.reasons
    assert db.was_consulted(period="test", strategy="tsmom", market="synthetic")
    assert db.was_consulted(period="holdout", strategy="tsmom", market="synthetic")
    with pytest.raises(HoldoutAlreadyConsulted):
        lab.vault.open("holdout", c.config_runs[next(iter(c.config_runs))].returns, strategy="tsmom",
                       market="synthetic", ppy=252)


def test_empty_holdout_does_not_reject_or_burn_the_ledger():
    lab, db = _lab(_synthetic_class(seed=4, n=4000, edge=0.0015), ["tsmom"], open_sealed=True)
    lab.screen()
    lab.validate()
    c = lab.candidates[0]
    assert c.decision == "PROMISING" and "holdout impossible" in c.reasons[0]
    assert not db.was_consulted(period="holdout", strategy="tsmom", market="synthetic")


def test_strategy_code_does_not_know_about_accounts_or_brokers():
    forbidden = ("qt.prop", "qt.brokers", "qt.oms", "..prop", "..brokers", "..oms")
    for f in ["qt/lab/strategies.py", "qt/lab/hypotheses.py", "qt/lab/simulate.py"]:
        tree = ast.parse((ROOT / f).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = ("." * node.level) + (node.module or "")
                assert not any(mod.startswith(x) or x in mod for x in forbidden), (f, mod)


def test_market_config_is_complete():
    m = load_markets()
    assert set(m) == {"fx", "indices", "futures", "equities", "crypto", "metals", "commodities"}
    for ac in m.values():
        assert ac.costs.per_side_bps > 0
        assert ac.symbols
    p = load_protocol()
    assert p["periods"]["research_end"] < p["periods"]["test_start"] <= p["periods"]["test_end"] < p["periods"]["holdout_start"]


def test_binance_timestamps_mixed_units_in_one_range():
    from qt.data.sources.binance_vision import _to_ms

    ms_2024 = 1_735_689_599_999          # 2024-12-31 in milliseconds
    us_2025 = 1_735_776_000_000_000      # 2025-01-02 in microseconds
    out = _to_ms(pd.Series([ms_2024, us_2025]))
    assert out.tolist() == [ms_2024, us_2025 // 1000]
