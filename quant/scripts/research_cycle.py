"""Run one research cycle end to end and write its report.

    python scripts/research_cycle.py                    # every asset class
    python scripts/research_cycle.py --classes fx,metals
    python scripts/research_cycle.py --dev              # never opens test / holdout

The research database is cumulative (reports/research.db): every cycle adds its trials
to the count that deflates the next cycle's Sharpe ratios.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qt.lab.database import ResearchDB  # noqa: E402
from qt.lab.ensemble import combine, select_diversifiers  # noqa: E402
from qt.lab.markets import CONFIG_DIR, file_hash, load_markets, load_protocol  # noqa: E402
from qt.lab.meta import compare_meta  # noqa: E402
from qt.lab.pipeline import Lab, cfg_key  # noqa: E402
from qt.lab.report import candidate_report, f, pct, summary  # noqa: E402
from qt.lab.sizing import compare_sizing  # noqa: E402
from qt.prop.challenge import challenge_monte_carlo  # noqa: E402
from qt.prop.rules import load_all  # noqa: E402


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classes", default=None)
    ap.add_argument("--hypotheses", default=None, help="liste de stratégies, séparées par des virgules")
    ap.add_argument("--db", default=str(ROOT / "reports" / "research.db"))
    ap.add_argument("--dev", action="store_true", help="ne jamais ouvrir les périodes test / holdout")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    t0 = time.time()
    protocol = load_protocol()
    markets = load_markets()
    db = ResearchDB(args.db)
    p_hash, m_hash = file_hash(CONFIG_DIR / "research_protocol.yaml"), file_hash(CONFIG_DIR / "markets.yaml")
    commit = git_commit()
    cycle_id = db.start_cycle(p_hash, m_hash, commit, args.notes or ("dev" if args.dev else ""))
    out_dir = ROOT / "reports" / f"cycle_{cycle_id:03d}{'_dev' if args.dev else ''}"
    (out_dir / "candidates").mkdir(parents=True, exist_ok=True)

    lab = Lab(db, cycle_id, protocol, markets, classes=args.classes.split(",") if args.classes else None,
              hypotheses=args.hypotheses.split(",") if args.hypotheses else None,
              open_sealed=not args.dev, log=lambda m: print(m, flush=True))
    lab.run()

    extras: dict = {}
    survivors = [c for c in lab.candidates if c.decision != "REJECTED"]
    ranked = sorted(survivors, key=lambda c: -c.details.get("score", {}).get("composite", 0))

    # Prop-firm compatibility on the research window (never on the sealed periods).
    firms = load_all(CONFIG_DIR / "prop_firms")
    programs = [(f"{fc.firm}/{p.name}", p) for fc in firms.values() for p in fc.programs if p.phase == "challenge"]
    prop_by_cand = {}
    for c in ranked[:6]:
        run = c.config_runs[cfg_key(c.candidate_cfg)]
        r = lab.vault.research(run.returns)
        w = lab.vault.research(run.worst)
        # Scales are expressed as target annual volatility: the research stream runs
        # at a few percent, far too slow for any challenge target, and "× 1.0" would
        # say nothing useful.
        vol = float(r.std() * np.sqrt(lab.markets[c.market].periods_per_year))
        targets = (0.05, 0.10, 0.15, 0.20, 0.30)
        tables = {}
        for name, prog in programs:
            t = challenge_monte_carlo(r, w, prog, scales=tuple(v / vol for v in targets), n_paths=1000,
                                      seed=protocol["monte_carlo"]["seed"])
            t["target_vol"] = targets
            tables[name] = t
        prop_by_cand[(c.market, c.hypothesis.name)] = tables
        print(f"  prop : {c.market}/{c.hypothesis.name}", flush=True)

    # Ensemble — only among strategies that reached PAPER TEST; otherwise an exploratory
    # look at the PROMISING ones, labelled as such.
    pool = [c for c in lab.candidates if c.decision == "PAPER_TEST"] or survivors
    label = "PAPER TEST" if any(c.decision == "PAPER_TEST" for c in lab.candidates) else "PROMISING (exploratoire)"
    if len(pool) >= 2:
        R = pd.DataFrame({f"{c.market}:{c.hypothesis.name}": c.wf["returns"] for c in pool if c.wf.get("ok")})
        R.index = R.index.normalize()
        R = R.groupby(level=0).sum().fillna(0.0)
        order = [f"{c.market}:{c.hypothesis.name}" for c in sorted(pool, key=lambda c: -c.details.get('score', {}).get('composite', 0))]
        members = select_diversifiers(R, [o for o in order if o in R], max_corr=0.7)
        ens = combine(R[members], ppy=252)
        lines = [f"Pool : {label}, {len(pool)} stratégies ; retenues pour diversification (|corrélation| < 0,7) : "
                 f"{len(members)}. Flux = walk-forward OOS (période de recherche).\n",
                 "| schéma | Sharpe | CAGR | volatilité | drawdown max |\n|---|---|---|---|---|"]
        for k, m in ens.get("schemes", {}).items():
            lines.append(f"| {k} | {f(m['sharpe'])} | {pct(m['cagr'])} | {pct(m['volatility'])} | {pct(m['max_drawdown'])} |")
        if "diversification_ratio" in ens:
            lines.append(f"\nRatio de diversification (inverse-vol) : {f(ens['diversification_ratio'], '{:.2f}')}. "
                         f"Corrélation moyenne entre membres : "
                         f"{f(float(np.nanmean(ens['correlation'].where(~np.eye(len(members), dtype=bool)).to_numpy())), '{:.2f}')}.")
        extras["ensemble"] = "\n".join(lines)
    else:
        extras["ensemble"] = "Moins de deux survivants : pas d'ensemble à construire."

    if ranked:
        top = ranked[0]
        ppy = lab.markets[top.market].periods_per_year
        sz = compare_sizing(top.wf["returns"], ppy)
        lines = [f"Sur {top.market}/{top.hypothesis.name} (flux walk-forward OOS, signal inchangé) :\n",
                 "| méthode | Sharpe | CAGR | drawdown max | levier moyen |\n|---|---|---|---|---|"]
        for k, m in sz.items():
            if isinstance(m, dict):
                lines.append(f"| {k} | {f(m['sharpe'])} | {pct(m['cagr'])} | {pct(m['max_drawdown'])} | {f(m['avg_leverage'], '{:.2f}')} |")
        lines.append(f"\n{sz['note']} Kelly plein non testé : il sur-parie dès que l'edge est mal estimé.")
        extras["sizing"] = "\n".join(lines)

    meta_lines = []
    for c in [c for c in lab.candidates if c.decision == "PAPER_TEST" and c.hypothesis.kind == "trade"]:
        run = c.config_runs[cfg_key(c.candidate_cfg)]
        tr = run.trades[run.trades["exit_ts"] <= lab.vault.research_end]
        res = compare_meta(tr, lab.data[c.market])
        for model in ("logistic", "gradient_boosting"):
            db.record_experiment(cycle_id=cycle_id, stage="meta_label", strategy=c.hypothesis.name,
                                 family=c.hypothesis.family, market=c.market, parameters={"model": model},
                                 metrics=res.get(model, {}), counts_as_trial=bool(res.get("ran")),
                                 decision=res.get("verdict"), reason=res.get("reason"))
        meta_lines.append(f"- {c.market}/{c.hypothesis.name} : {res.get('verdict') or res.get('reason')}")
    extras["meta"] = ("\n".join(meta_lines) if meta_lines else
                      "Non exécuté : aucun signal primaire n'a atteint PAPER TEST. Un filtre ML entraîné sur un signal "
                      "sans edge validé apprend le bruit, et son « amélioration » serait un artefact ajusté. "
                      "Le code (`qt/lab/meta.py`, régression logistique vs gradient boosting, walk-forward purgé) est prêt.")

    for c in survivors:
        text = candidate_report(c, lab, {"prop": prop_by_cand.get((c.market, c.hypothesis.name), {})})
        (out_dir / "candidates" / f"{c.market}__{c.hypothesis.name}.md").write_text(text)
    (out_dir / "README.md").write_text(summary(
        lab, extras, cycle_id=cycle_id, protocol_hash=p_hash, markets_hash=m_hash, git_commit=commit,
        n_trials=db.n_trials(), elapsed_min=(time.time() - t0) / 60))
    rows = [{"strategy": c.hypothesis.name, "market": c.market, "decision": c.decision, "stage": c.stage,
             "config": c.candidate_cfg, "wf_sharpe": c.wf.get("sharpe"), "reasons": "; ".join(c.reasons)}
            for c in lab.candidates]
    pd.DataFrame(rows).to_csv(out_dir / "decisions.csv", index=False)
    print(f"rapport : {out_dir}  ({(time.time() - t0) / 60:.1f} min, {db.n_trials()} essais)")


if __name__ == "__main__":
    main()
