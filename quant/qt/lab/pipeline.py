"""One research cycle: hypotheses in, recorded decisions out.

Order of operations (each stage only sees the survivors of the previous one):

    A. audit every dataset, record it
    B. for each (hypothesis × asset class): run the declared grid on the research
       window, record every configuration as a trial, walk-forward select, apply the
       PROMISING gate
    C. Reality Check / SPA over every strategy of each class (the "best of N" test)
    D. for PROMISING survivors: robustness, Monte Carlo, regimes, capacity, DSR (from
       the database's cumulative trial count), PBO, score; then — only if every
       pre-test gate passes — the TEST period, then the HOLDOUT, each consulted once
    E. portfolio, sizing, ML and prop-firm stages on whatever survived

The unit of decision is (strategy × asset class), evaluated on an equal-risk basket of
the class's instruments. Per-instrument results are reported, never used to choose:
picking "RSI on USDCAD" because USDCAD is where it worked is selecting the best curve.

Full-history return streams are computed once per configuration (all signals are
causal, so slicing them is equivalent to re-running per window) and the test and
holdout slices are held in a `Vault` that only opens through the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from ..validation.statistics import deflated_sharpe_ratio, probability_of_backtest_overfitting
from . import hypotheses as HY
from . import strategies as ST
from .capacity import capacity_table
from .data_audit import audit_bars
from .database import ResearchDB
from .markets import AssetClass, content_hash, load_class
from .metrics import by_year_sharpe, compute, sharpe
from .montecarlo import block_monte_carlo, trade_monte_carlo
from .regimes import class_index, label_regimes, regime_performance
from .robustness import run_robustness
from .scoring import research_score
from .significance import reality_check_spa
from .simulate import simulate, simulate_weights, vol_target_size

REJECTED, PROMISING, PAPER_TEST, LIVE_CANDIDATE = "REJECTED", "PROMISING", "PAPER_TEST", "LIVE_CANDIDATE"


@dataclass
class ClassRun:
    returns: pd.Series
    trades: pd.DataFrame
    by_symbol: pd.DataFrame
    exposure: pd.Series
    worst: pd.Series


@dataclass
class Candidate:
    hypothesis: HY.Hypothesis
    market: str
    config_runs: dict[str, ClassRun]
    configs: list[dict]
    wf: dict
    candidate_cfg: dict
    research_metrics: dict
    stage: str = "grid"
    decision: str = REJECTED
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def _drop_rows(w: pd.DataFrame, rng: np.random.Generator, rate: float) -> pd.DataFrame:
    """Signal noise for a weight book: a random share of rebalance days is missed and
    yesterday's book is kept instead."""
    keep = rng.random(len(w)) >= rate
    mask = pd.DataFrame(np.repeat(keep[:, None], w.shape[1], axis=1), index=w.index, columns=w.columns)
    return w.where(mask).ffill().fillna(0.0)


def cfg_key(cfg: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(cfg.items()))


class EmptyPeriod(RuntimeError):
    pass


class Vault:
    """Holds full-history streams; test and holdout slices open only through the ledger."""

    def __init__(self, db: ResearchDB, cycle_id: int, periods: dict, resume: bool = False) -> None:
        self.db, self.cycle_id, self.resume = db, cycle_id, resume
        self.research_end = pd.Timestamp(periods["research_end"], tz="UTC")
        self.test = (pd.Timestamp(periods["test_start"], tz="UTC"), pd.Timestamp(periods["test_end"], tz="UTC"))
        self.holdout_start = pd.Timestamp(periods["holdout_start"], tz="UTC")

    def research(self, r: pd.Series) -> pd.Series:
        return r.loc[:self.research_end]

    def open(self, period: str, r: pd.Series, *, strategy: str, market: str, ppy: int,
             trades: pd.DataFrame | None = None) -> tuple[pd.Series, dict]:
        lo, hi = self.test if period == "test" else (self.holdout_start, r.index.max())
        sl = r.loc[lo:hi]
        if len(sl) < 60:
            # Nothing to look at: do not burn the ledger entry on an empty period.
            raise EmptyPeriod(f"période {period} : {len(sl)} barres")
        tr = None
        if trades is not None and len(trades):
            tr = trades[(trades["exit_ts"] >= lo) & (trades["exit_ts"] <= hi)]
        m = compute(sl, tr, ppy)
        if self.resume and self.db.was_consulted(period=period, strategy=strategy, market=market):
            row = self.db.conn.execute(
                "SELECT cycle_id FROM holdout_ledger WHERE period=? AND strategy=? AND market=?",
                (period, strategy, market)).fetchone()
            if row and row[0] == self.cycle_id:
                # Resuming the same cycle after a crash: the look already happened and is
                # on the ledger; recomputing the identical number adds no information.
                return sl, m
        self.db.consult(period=period, strategy=strategy, market=market, cycle_id=self.cycle_id, result=m)
        return sl, m


class Lab:
    def __init__(self, db: ResearchDB, cycle_id: int, protocol: dict, markets: dict[str, AssetClass], *,
                 classes: list[str] | None = None, hypotheses: list[str] | None = None,
                 data: dict[str, dict[str, pd.DataFrame]] | None = None, log: Callable[[str], None] = print,
                 open_sealed: bool = True, resume: bool = False) -> None:
        self.db, self.cycle_id, self.protocol = db, cycle_id, protocol
        self.hyps = [h for h in HY.HYPOTHESES if hypotheses is None or h.name in hypotheses]
        # Classes whose single strategies are screened, vs classes only loaded because a
        # combination needs them as members.
        self.screen_classes = set(markets) if classes is None else set(classes)
        needed = set(self.screen_classes)
        for h in self.hyps:
            if h.kind == "combo":
                needed |= HY.member_classes(h)
        self.markets = {k: v for k, v in markets.items() if k in needed}
        if any(h.kind == "combo" for h in self.hyps):
            from .markets import CostProfile

            # Costs are charged inside each member; the combination adds none of its own.
            self.markets["multi"] = AssetClass("multi", (), CostProfile(0.0, 0.0, 0.0), 252, True)
            self.screen_classes.add("multi")
        self.vault = Vault(db, cycle_id, protocol["periods"], resume=resume)
        # A resumed cycle re-runs deterministic stages without recording them twice:
        # double-counting trials would deflate every Sharpe for no reason.
        self.resume = resume
        self.log = log
        self.data: dict[str, dict[str, pd.DataFrame]] = data or {}
        self.audits: dict[str, dict] = {}
        self.candidates: list[Candidate] = []
        self.skipped: list[dict] = []
        self.significance: dict = {}
        # Debug and development runs must not look at the test or holdout periods: a
        # researcher who has seen them is no longer blind, whatever the ledger says.
        self.open_sealed = open_sealed
        self.sizing = protocol["sizing_for_research"]

    def _record(self, **kw) -> None:
        if self.resume:
            from .database import dumps

            row = self.db.conn.execute(
                "SELECT 1 FROM experiments WHERE cycle_id=? AND stage=? AND strategy=? AND market=? AND parameters=?",
                (self.cycle_id, kw["stage"], kw["strategy"], kw["market"], dumps(kw["parameters"]))).fetchone()
            if row:
                return
        self.db.record_experiment(**kw)

    # ------------------------------------------------------------------ A. data
    def load(self) -> None:
        for name, ac in self.markets.items():
            if name == "multi":
                self.data[name] = {}
                continue
            if name not in self.data:
                self.data[name] = load_class(ac)
            from .markets import fetch, fetch_daily

            self.audits[name] = {}
            for s in ac.symbols:
                raw = fetch(ac, s)
                proxy = fetch_daily(ac.roll_proxies[s]) if s in ac.roll_proxies else None
                a = audit_bars(s, raw, trades_weekends=ac.periods_per_year == 365, has_volume=ac.has_volume,
                               proxy=proxy, expected_adjusted=ac.use_adjusted)
                self.audits[name][s] = a.to_dict()
                b = self.data[name].get(s)
                self.db.record_dataset(f"{ac.source}:{s}:1d", symbol=s, asset_class=name, source=ac.source,
                                       first_ts=a.first, last_ts=a.last, n_bars=a.n_bars,
                                       content_hash=content_hash(b) if b is not None else None, audit=a.to_dict())
                if a.grade == "F" and s in self.data[name]:
                    del self.data[name][s]

    # ------------------------------------------------------------------ simulation
    def run_class(self, h: HY.Hypothesis, cfg: dict, ac: AssetClass, *, cost_mult: float = 1.0,
                  extra_slip: float = 0.0, entry_delay: int = 0, exit_delay: int = 0, noise: float = 0.0,
                  seed: int = 0) -> ClassRun:
        if h.kind == "combo":
            return self._run_combo(h, cfg, cost_mult=cost_mult, extra_slip=extra_slip, entry_delay=entry_delay,
                                   exit_delay=exit_delay, noise=noise, seed=seed)
        data = self.data[ac.name]
        costs = ac.costs.scaled(cost_mult, extra_slip)
        ppy = ac.periods_per_year
        rng = np.random.default_rng(seed)
        sz = self.sizing
        if h.kind == "trade":
            rets, expo, worst, trades = {}, {}, {}, []
            for s, b in data.items():
                out = h.func(b, **cfg)
                if noise > 0:
                    if out.target is not None:
                        mask = rng.random(len(out.target)) < noise
                        out.target = out.target.where(~mask, 0.0)
                    for attr in ("long_entry_offset", "short_entry_offset", "long_entry_level", "short_entry_level"):
                        ser = getattr(out, attr)
                        if ser is not None:
                            setattr(out, attr, ser.where(rng.random(len(ser)) >= noise))
                size = vol_target_size(b, target_vol=sz["target_vol_per_instrument"],
                                       lookback=sz["vol_lookback_days"], periods_per_year=ppy,
                                       max_leverage=sz["max_leverage_per_instrument"])
                res = simulate(b, out, costs, size=size, periods_per_year=ppy,
                               entry_delay=entry_delay, exit_delay=exit_delay)
                rets[s], expo[s], worst[s] = res.returns, res.position.abs(), res.worst_intrabar
                if len(res.trades):
                    t = res.trades.copy()
                    t["symbol"] = s
                    trades.append(t)
            R = pd.DataFrame(rets).sort_index()
            count = R.notna().sum(axis=1).replace(0, np.nan)
            cls = R.mean(axis=1, skipna=True).fillna(0.0)
            W = pd.DataFrame(worst).reindex(R.index)
            worst_cls = W.mean(axis=1, skipna=True).fillna(0.0)
            T = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(
                columns=["entry_ts", "exit_ts", "side", "size", "gross", "cost", "net", "bars", "symbol"])
            if len(T):
                scale = 1.0 / count.reindex(T["entry_ts"]).fillna(len(data)).to_numpy()
                for col in ("gross", "cost", "net", "size"):
                    T[col] = T[col] * scale
            E = pd.DataFrame(expo).reindex(R.index).mean(axis=1).fillna(0.0)
            return ClassRun(cls, T, R, E, worst_cls)

        # Portfolio strategies: build weights, simulate the book, then scale the book
        # to the research volatility causally (yesterday's estimate sizes today).
        streams, trade_frames = [], []
        if h.kind == "xs":
            closes = pd.DataFrame({s: b["close"] for s, b in data.items()}).sort_index()
            vols = np.log(closes).diff().rolling(60, min_periods=30).std() * np.sqrt(ppy)
            w = ST.xs_momentum_weights(closes.ffill(limit=5), vols, **cfg)
            if noise > 0:
                w = _drop_rows(w, rng, noise)
            res = simulate_weights(data, w, costs, periods_per_year=ppy, entry_delay=entry_delay)
            streams.append(res.returns)
            trade_frames.append(res.trades)
        elif h.kind == "pair":
            for a, bsym in ac.pairs:
                if a not in data or bsym not in data:
                    continue
                w = ST.pair_weights(data[a], data[bsym], **cfg).rename(columns={"A": a, "B": bsym})
                if noise > 0:
                    w = _drop_rows(w, rng, noise)
                res = simulate_weights({a: data[a], bsym: data[bsym]}, w, costs, periods_per_year=ppy,
                                       entry_delay=entry_delay)
                streams.append(res.returns.rename(f"{a}/{bsym}"))
                t = res.trades.copy()
                t["symbol"] = f"{a}/{bsym}"
                trade_frames.append(t)
        if not streams:
            empty = pd.Series(dtype="float64")
            return ClassRun(empty, pd.DataFrame(), pd.DataFrame(), empty, empty)
        R = pd.concat(streams, axis=1).sort_index()
        raw = R.mean(axis=1, skipna=True).fillna(0.0)
        vol = raw.rolling(60, min_periods=30).std().shift(1) * np.sqrt(ppy)
        scale = (sz["target_vol_per_instrument"] / vol).clip(upper=sz["max_leverage_per_instrument"]).fillna(0.0)
        cls = raw * scale
        T = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
        return ClassRun(cls, T, R, scale, cls.copy())

    def _run_combo(self, h: HY.Hypothesis, cfg: dict, **kw) -> ClassRun:
        """Equal-risk average of member streams, each run with its canonical parameters
        and its own class costs, then scaled to the research volatility with yesterday's
        estimate, the scale being revised once a month (a daily revision would trade
        every day for free)."""
        target = self.sizing["target_vol_per_instrument"]
        cap = self.sizing["max_leverage_per_instrument"]
        streams, trades = {}, []
        for strat, cls in cfg["members"]:
            mh = HY.by_name(strat)
            ac = self.markets[cls]
            run = self.run_class(mh, dict(mh.baseline), ac, **kw)
            r = run.returns
            if r.empty:
                continue
            # 24/7 markets: fold weekend returns into the next business day so every
            # member lives on one calendar and annualisation stays at 252.
            if ac.periods_per_year == 365:
                bday = r.index + pd.offsets.BDay(0)
                r = (1 + r).groupby(bday).prod() - 1
            vol = r.rolling(60, min_periods=30).std() * np.sqrt(252)
            scale = (target / vol).shift(1).clip(upper=cap)
            monthly = scale.groupby([scale.index.year, scale.index.month]).transform("first")
            key = f"{strat}@{cls}"
            streams[key] = r * monthly.fillna(0.0)
            if len(run.trades):
                t = run.trades.copy()
                t["symbol"] = key
                trades.append(t)
        if not streams:
            empty = pd.Series(dtype="float64")
            return ClassRun(empty, pd.DataFrame(), pd.DataFrame(), empty, empty)
        R = pd.DataFrame(streams).sort_index()
        cls_r = R.mean(axis=1, skipna=True).fillna(0.0)
        T = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
        if len(T):
            for col in ("gross", "cost", "net", "size"):
                T[col] = T[col] / len(streams)
        return ClassRun(cls_r, T, R, pd.Series(1.0, index=cls_r.index), cls_r.copy())

    # ------------------------------------------------------------------ B. grid + walk-forward
    def walk_forward(self, M: pd.DataFrame, configs: list[dict], ppy: int) -> dict:
        wfp = self.protocol["walk_forward"]
        active = M.abs().sum(axis=1) > 0
        first = M.index[active.to_numpy()].min() if active.any() else M.index.min()
        start_year = first.year + (1 if first.month > 1 else 0)
        end_year = self.vault.research_end.year
        keys = [cfg_key(c) for c in configs]
        chosen, oos = [], []
        baseline_oos = []
        for y in range(start_year + wfp["min_train_years"], end_year + 1):
            lo = max(start_year, y - wfp["train_years"])
            train = M[(M.index.year >= lo) & (M.index.year < y)]
            val = M[M.index.year == y]
            if len(val) == 0 or (y - lo) < wfp["min_train_years"]:
                continue
            scores = {k: sharpe(train[k], ppy) for k in keys}
            best = max(keys, key=lambda k: (np.nan_to_num(scores[k], nan=-9), k == keys[0]))
            chosen.append({"year": y, "train": f"{lo}-{y - 1}", "config": best, "train_sharpe": scores[best],
                           "oos_sharpe": sharpe(val[best], ppy)})
            oos.append(val[best])
            baseline_oos.append(val[keys[0]])
        if not oos:
            return {"ok": False}
        r = pd.concat(oos)
        years = pd.DataFrame(chosen)
        counts = years["config"].value_counts()
        modal = counts.index[0]
        if counts.iloc[0] == counts.get(keys[0], 0):
            modal = keys[0]
        return {
            "ok": True, "returns": r, "folds": years,
            "sharpe": sharpe(r, ppy),
            "positive_years": float((years["oos_sharpe"] > 0).mean()),
            "param_stability": float(counts.iloc[0] / len(years)),
            "modal_config": modal,
            "baseline_oos_sharpe": sharpe(pd.concat(baseline_oos), ppy),
            "is_oos_ratio": float(years["oos_sharpe"].mean() / years["train_sharpe"].mean())
            if years["train_sharpe"].mean() > 0 else float("nan"),
        }

    def screen(self) -> None:
        gates = self.protocol["gates"]
        for name, ac in self.markets.items():
            if not self.data.get(name) and name != "multi":
                continue
            ppy = ac.periods_per_year
            if name not in self.screen_classes:
                continue
            for h in self.hyps:
                if (h.kind == "combo") != (name == "multi"):
                    continue
                if h.kind == "deferred":
                    self.skipped.append({"strategy": h.name, "market": name, "status": "DEFERRED",
                                         "reason": h.deferred_reason})
                    continue
                if h.requires_volume and not ac.has_volume:
                    self.skipped.append({"strategy": h.name, "market": name, "status": "NOT_APPLICABLE",
                                         "reason": "exige du volume ; la classe n'en a pas"})
                    self._record(cycle_id=self.cycle_id, stage="screen", strategy=h.name,
                                              family=h.family, market=name, parameters=h.baseline, metrics={},
                                              counts_as_trial=False, decision="NOT_APPLICABLE",
                                              reason="pas de volume")
                    continue
                if h.kind == "pair" and not ac.pairs:
                    continue
                configs = h.configs()[: self.protocol["budget"]["max_configs_per_strategy"]]
                runs: dict[str, ClassRun] = {}
                for i, cfg in enumerate(configs):
                    run = self.run_class(h, cfg, ac)
                    if run.returns.empty:
                        continue
                    k = cfg_key(cfg)
                    runs[k] = run
                    rr = self.vault.research(run.returns)
                    tr = run.trades[run.trades["exit_ts"] <= self.vault.research_end] if len(run.trades) else run.trades
                    m = compute(rr, tr, ppy, run.exposure.loc[:self.vault.research_end])
                    self._record(
                        cycle_id=self.cycle_id, stage="grid", strategy=h.name, family=h.family, market=name,
                        parameters=cfg, metrics=m, is_baseline=(i == 0), counts_as_trial=True,
                        train_period=f"{rr.index.min().date()}..{rr.index.max().date()}",
                        cost_model=ac.costs.describe(), slippage_model="fixe par côté, × 2 sur stop")
                if not runs:
                    continue
                M = pd.DataFrame({k: self.vault.research(r.returns) for k, r in runs.items()}).fillna(0.0)
                wf = self.walk_forward(M, [c for c in configs if cfg_key(c) in runs], ppy)
                cand_key = wf.get("modal_config", cfg_key(configs[0]))
                cand_cfg = next(c for c in configs if cfg_key(c) == cand_key)
                run = runs[cand_key]
                rr = self.vault.research(run.returns)
                tr = run.trades[run.trades["exit_ts"] <= self.vault.research_end] if len(run.trades) else run.trades
                rm = compute(rr, tr, ppy, run.exposure.loc[:self.vault.research_end])
                c = Candidate(h, name, runs, configs, wf, cand_cfg, rm)
                c.details["config_matrix"] = M
                self.candidates.append(c)

                reasons = []
                n_tr = rm.get("n_trades", 0)
                if h.kind == "trade" and n_tr < gates["min_trades_research"]:
                    reasons.append(f"{n_tr} trades en recherche (< {gates['min_trades_research']})")
                if not wf.get("ok"):
                    reasons.append("walk-forward impossible (historique trop court)")
                else:
                    if not wf["sharpe"] > gates["promising"]["wf_oos_sharpe_min"]:
                        reasons.append(f"Sharpe walk-forward OOS {wf['sharpe']:+.2f} ≤ 0")
                    if wf["positive_years"] < gates["promising"]["wf_positive_years_min"]:
                        reasons.append(f"{wf['positive_years']:.0%} d'années OOS positives (< 50 %)")
                if not reasons:
                    stressed = self.run_class(h, cand_cfg, ac, cost_mult=1.5)
                    s15 = sharpe(self.vault.research(stressed.returns), ppy)
                    c.details["cost_x1_5_sharpe"] = s15
                    if not s15 > gates["promising"]["cost_x1_5_sharpe_min"]:
                        reasons.append(f"Sharpe avec coûts × 1,5 = {s15:+.2f} ≤ 0")
                self._record(
                    cycle_id=self.cycle_id, stage="walk_forward", strategy=h.name, family=h.family, market=name,
                    parameters=cand_cfg, metrics={k: v for k, v in wf.items() if k not in ("returns", "folds")},
                    counts_as_trial=False, validation_period="années glissantes ≤ " + str(self.vault.research_end.year),
                    decision=PROMISING if not reasons else REJECTED, reason="; ".join(reasons) or "porte PROMISING passée")
                c.reasons = reasons
                c.decision = PROMISING if not reasons else REJECTED
                c.stage = "promising_gate"
                self.log(f"  {name:12s} {h.name:20s} WF {wf.get('sharpe', float('nan')):+.2f} → {c.decision}"
                         + (f" ({reasons[0]})" if reasons else ""))

    # ------------------------------------------------------------------ C. best-of-N
    def best_of_n(self) -> None:
        by_class: dict[str, dict[str, pd.Series]] = {}
        for c in self.candidates:
            if c.wf.get("ok"):
                by_class.setdefault(c.market, {})[c.hypothesis.name] = c.wf["returns"]
        seed = self.protocol["monte_carlo"]["seed"]
        all_streams = {}
        for market, streams in by_class.items():
            R = pd.DataFrame(streams).fillna(0.0)
            self.significance[market] = reality_check_spa(R, n_boot=1000, seed=seed)
            for k, v in streams.items():
                all_streams[f"{market}:{k}"] = v
        if all_streams:
            R = pd.DataFrame(all_streams)
            R.index = R.index.normalize()
            R = R.groupby(level=0).sum().fillna(0.0)
            self.significance["_global"] = reality_check_spa(R, n_boot=1000, seed=seed)

    # ------------------------------------------------------------------ D. deep validation
    def validate(self) -> None:
        g = self.protocol["gates"]["paper_test"]
        mc = self.protocol["monte_carlo"]
        n_trials = self.db.n_trials()
        trial_sharpes = pd.Series(self.db.trial_sharpes())
        for c in [c for c in self.candidates if c.decision == PROMISING]:
            ac = self.markets[c.market]
            ppy = ac.periods_per_year
            h = c.hypothesis
            run = c.config_runs[cfg_key(c.candidate_cfg)]
            window = (run.returns.index.min(), self.vault.research_end)
            self.log(f"  validation approfondie : {c.market} / {h.name} {c.candidate_cfg}")

            def runner(params, cost_mult=1.0, extra_slip=0.0, entry_delay=0, exit_delay=0, noise=0.0, seed=0,
                       _h=h, _ac=ac):
                rr = self.run_class(_h, params, _ac, cost_mult=cost_mult, extra_slip=extra_slip,
                                    entry_delay=entry_delay, exit_delay=exit_delay, noise=noise, seed=seed)
                return rr.returns, rr.trades

            rob = run_robustness(c.candidate_cfg, runner, window, ppy, self.protocol["robustness"], seed=mc["seed"])
            for _, row in rob["table"].iterrows():
                self._record(cycle_id=self.cycle_id, stage="robustness", strategy=h.name,
                                          family=h.family, market=c.market, parameters={"perturbation": row["name"]},
                                          metrics={"sharpe": row["sharpe"]}, counts_as_trial=False,
                                          decision="PASS" if row["passed"] else "FAIL")
            tr_research = run.trades[run.trades["exit_ts"] <= self.vault.research_end] if len(run.trades) else run.trades
            years = len(self.vault.research(run.returns)) / ppy
            mc_trades = (trade_monte_carlo(tr_research, years=years, n_paths=mc["n_paths"], seed=mc["seed"],
                                           cost_range=tuple(mc["cost_multiplier_range"]),
                                           drop_rate=mc["trade_drop_rate"],
                                           noise_sd_fraction=mc["return_noise_sd_fraction"])
                         if h.kind == "trade" else {"n_paths": 0})
            mc_block = block_monte_carlo(self.vault.research(run.returns), ppy=ppy, n_paths=mc["n_paths"],
                                         seed=mc["seed"])
            # The gate reads the block bootstrap of the daily class stream: it keeps the
            # concurrency of trades running in parallel across instruments. The trade
            # resampling compounds trades one after another, which ignores that overlap,
            # so it is reported (order, missed trades, cost shocks) but does not gate.
            p25 = mc_block.get("prob_drawdown_beyond", {}).get("25%", 0.0)
            dd95 = mc_block.get("max_drawdown", {}).get(0.05, 0.0)

            labels = label_regimes(class_index(run.by_symbol))
            reg = regime_performance(c.wf["returns"], labels, ppy)
            cap = capacity_table(tr_research, self.data[c.market], self.protocol["capacity"]["sizes_usd"],
                                 n_symbols=max(len(self.data[c.market]), 1)) if h.kind == "trade" else {
                "measurable": False, "reason": "stratégie de portefeuille : capacité non estimée dans ce cycle"}
            dsr = deflated_sharpe_ratio(c.wf["returns"], n_trials=n_trials, trial_sharpes=trial_sharpes,
                                        periods_per_year=ppy)
            M = c.details["config_matrix"]
            pbo = probability_of_backtest_overfitting(M.loc[M.abs().sum(axis=1) > 0], n_splits=10,
                                                      periods_per_year=ppy) if M.shape[1] > 1 else {"pbo": float("nan")}
            base_s = rob["base_sharpe"]
            cost_ratio = c.details.get("cost_x1_5_sharpe", np.nan) / base_s if base_s and base_s > 0 else np.nan
            score = research_score(
                wf_sharpe=c.wf["sharpe"], positive_years=c.wf["positive_years"], robustness=rob["score"],
                mc_p95_dd=dd95, cost_ratio=cost_ratio, param_stability=c.wf["param_stability"],
                capacity_usd=cap.get("capacity_half_edge") if cap.get("measurable") else None,
                regime_diversity=reg.get("regime_diversity"), dsr=dsr.get("deflated_sharpe"))
            c.details.update({"robustness": rob, "mc_trades": mc_trades, "mc_block": mc_block, "regimes": reg,
                              "capacity": cap, "dsr": dsr, "pbo": pbo, "score": score, "prob_dd25": p25})
            reasons = []
            if not rob["score"] >= g["robustness_score_min"]:
                reasons.append(f"robustesse {rob['score']:.0%} (< {g['robustness_score_min']:.0%})")
            if rob["sharp_peak"]:
                reasons.append("optimum en pic : les paramètres voisins font moins de la moitié du Sharpe")
            d = dsr.get("deflated_sharpe", np.nan)
            if not (np.isfinite(d) and d >= g["dsr_min"]):
                reasons.append(f"Sharpe déflaté {d:.2f} sur {n_trials} essais (< {g['dsr_min']})")
            p = pbo.get("pbo", np.nan)
            if np.isfinite(p) and p > g["pbo_max"]:
                reasons.append(f"PBO {p:.2f} (> {g['pbo_max']})")
            if p25 > g["mc_prob_dd25_max"]:
                reasons.append(f"P(drawdown > 25 %) = {p25:.0%} au Monte Carlo (> {g['mc_prob_dd25_max']:.0%})")
            c.stage = "deep_validation"
            if reasons:
                c.reasons = reasons
                c.decision = PROMISING
                self.log(f"    → reste PROMISING : {reasons[0]}")
                continue
            # Every pre-test gate passed: the test period, once.
            if not self.open_sealed:
                c.reasons = ["portes pré-test passées ; périodes scellées non ouvertes (run de développement)"]
                c.decision = PROMISING
                continue
            try:
                sl, tm = self.vault.open("test", run.returns, strategy=h.name, market=c.market, ppy=ppy,
                                         trades=run.trades)
            except EmptyPeriod as exc:
                c.reasons, c.decision = [f"{exc} : test impossible"], PROMISING
                continue
            c.details["test"] = tm
            self._record(cycle_id=self.cycle_id, stage="test", strategy=h.name, family=h.family,
                                      market=c.market, parameters=c.candidate_cfg, metrics=tm, counts_as_trial=False,
                                      test_period=f"{self.vault.test[0].date()}..{self.vault.test[1].date()}")
            c.stage = "test"
            if not tm.get("sharpe", -1) > g["test_sharpe_min"]:
                c.reasons = [f"période de test : Sharpe {tm.get('sharpe', float('nan')):+.2f} ≤ 0"]
                c.decision = REJECTED
                continue
            try:
                sl, hm = self.vault.open("holdout", run.returns, strategy=h.name, market=c.market, ppy=ppy,
                                         trades=run.trades)
            except EmptyPeriod as exc:
                c.reasons, c.decision = [f"test passé ; {exc} : holdout impossible"], PROMISING
                continue
            c.details["holdout"] = hm
            self._record(cycle_id=self.cycle_id, stage="holdout", strategy=h.name, family=h.family,
                                      market=c.market, parameters=c.candidate_cfg, metrics=hm, counts_as_trial=False,
                                      test_period=f"{self.vault.holdout_start.date()}..")
            c.stage = "holdout"
            if not hm.get("sharpe", -1) > g["holdout_sharpe_min"]:
                c.reasons = [f"holdout : Sharpe {hm.get('sharpe', float('nan')):+.2f} ≤ 0"]
                c.decision = REJECTED
            else:
                c.reasons = ["toutes les portes de recherche passées ; LIVE_CANDIDATE exige un relevé papier"]
                c.decision = PAPER_TEST

    # ------------------------------------------------------------------ record
    def apply_invalidations(self, path=None) -> None:
        import yaml

        from .markets import CONFIG_DIR

        path = path or CONFIG_DIR / "invalidations.yaml"
        if not path.exists():
            return
        for inv in yaml.safe_load(path.read_text()) or []:
            if inv["cycle"] != self.cycle_id:
                continue
            targets = inv["strategies"]
            for c in self.candidates:
                name = c.hypothesis.name
                match = targets == "*" or name == targets or (isinstance(targets, list) and name in targets)
                if c.market == inv["market"] and match:
                    if not (c.reasons and c.reasons[0].startswith("INVALIDÉ")):
                        c.details["decision_before_invalidation"] = c.decision
                        c.decision = REJECTED
                        c.reasons = ["INVALIDÉ (données) : " + " ".join(inv["reason"].split())] + c.reasons

    def finalise(self) -> None:
        self.apply_invalidations()
        for c in self.candidates:
            self.db.record_decision(cycle_id=self.cycle_id, strategy=c.hypothesis.name, market=c.market,
                                    stage_reached=c.stage, decision=c.decision,
                                    score=c.details.get("score", {}), reason="; ".join(c.reasons))
        for s in self.skipped:
            self.db.record_decision(cycle_id=self.cycle_id, strategy=s["strategy"], market=s["market"],
                                    stage_reached="screen", decision=s["status"], score={}, reason=s["reason"])

    def run(self) -> None:
        self.log("A. données et audit")
        self.load()
        self.log("B. grille + walk-forward + porte PROMISING")
        self.screen()
        self.log("C. Reality Check / SPA")
        self.best_of_n()
        self.log("D. validation approfondie des survivants")
        self.validate()
        self.finalise()


def year_table(r: pd.Series, ppy: int) -> pd.Series:
    return by_year_sharpe(r, ppy)
