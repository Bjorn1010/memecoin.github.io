"""Research report: the cycle summary and, for every strategy that survived the first
gate, the 20-section report the protocol asks for.

The wording is fixed by the decision, never by the equity curve: REJECTED, PROMISING,
PAPER_TEST or LIVE_CANDIDATE — never "profitable".
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .hypotheses import HYPOTHESES
from .pipeline import Candidate, Lab, cfg_key

FORMULAS = {
    "sma_cross": "pos_t = sign(SMA_f(C)_t − SMA_s(C)_t)",
    "ema_cross": "pos_t = sign(EMA_f(C)_t − EMA_s(C)_t)",
    "donchian": "entrée long si C_t > max(H_{t−N..t−1}), sortie si C_t < min(L_{t−M..t−1}) ; symétrique ; stop 2·ATR14",
    "tsmom": "pos_t = sign(C_t / C_{t−L} − 1)",
    "adx_trend": "pos_t = 1{ADX_t > θ} · sign(+DI_t − −DI_t)",
    "rsi2": "long si RSI_n(C)_t < θ jusqu'à C_t > SMA5_t ; short si RSI_n > 100 − θ jusqu'à C_t < SMA5_t",
    "rsi2_trend": "rsi2 restreint au côté de la tendance : long seulement si C_t > SMA_T, short seulement si C_t < SMA_T",
    "bollinger_reversion": "long si C_t < SMA_n − k·σ_n jusqu'à C_t ≥ SMA_n ; symétrique",
    "pullback": "long si C_t = min(C_{t−N+1..t}) et C_t > SMA_T, sortie à max(C_{t−N+1..t}) ou 10 jours ; symétrique",
    "ibs": "IBS_t = (C_t − L_t)/(H_t − L_t) ; long si IBS < θ, short si IBS > 1 − θ ; détention h jours",
    "vol_breakout": "stop d'achat à O_{t+1} + k·R_t, de vente à O_{t+1} − k·R_t (R = range ou ATR5) ; sortie à C_{t+1}",
    "nr7": "si R_t = min(R_{t−n+1..t}) : stops à H_t et L_t pour t+1 ; détention h jours, stop 1·ATR",
    "prev_hl_breakout": "stops à H_t + b·ATR et L_t − b·ATR pour t+1 ; sortie à la clôture (h = 1) ou après h jours",
    "roc_accel": "long si ROC_n > 0 et ROC_n − ROC_n(t−m) > 0 ; short symétrique",
    "mtf_momentum": "long h jours si ROC_L > 0 et ROC_S < 0 (repli dans la tendance) ; symétrique",
    "xs_momentum": "chaque 21 j : rang de C_{t−s}/C_{t−s−L} ; long tiers haut, short tiers bas, inverse-vol, 50 % par jambe",
    "squeeze_breakout": "si largeur(Bollinger)_{t−1} ≤ quantile_q(126 j) et C_t hors bande : position h jours",
    "atr_breakout": "si |C_t − C_{t−1}| > k·ATR14_{t−1} : position dans le sens du mouvement h jours",
    "market_structure": "sommets/creux de swing confirmés après k barres ; long si HH & HL, short si LH & LL",
    "liquidity_sweep": "long h jours si L_t < min(L_{t−N..t−1}) et C_t > ce minimum ; symétrique",
    "rejection": "long h jours si mèche basse ≥ w·R_t au plus bas 20 j ; symétrique",
    "volume_spike": "long h jours si V_t / médiane(V)_{20} > k et C_t dans le quart haut du range ; symétrique",
    "volume_divergence": "short h jours si C_t = max N jours et V_t < médiane 20 j ; long symétrique",
    "mr_equity_basket": "r_t = moyenne_i( s_i,t · r_i,t ), s_i,t = min(0,10 / σ̂_i(60 j), 3) révisé chaque mois ; i ∈ {rsi2_trend, bollinger, pullback, ibs} × {indices, actions, futures}",
    "trend_multiclass": "r_t = moyenne_i( s_i,t · r_i,t ) ; i ∈ {tsmom 252, SMA 50/200, Donchian 20/10} × 7 classes ; même échelle mensuelle",
    "pairs": "β_t = cov/var glissants (W) de log A, log B ; z du spread ; long spread si z < −e jusqu'à z ≥ 0 ; symétrique",
}

DECISION_FR = {"REJECTED": "REJECTED", "PROMISING": "PROMISING", "PAPER_TEST": "PAPER TEST",
               "LIVE_CANDIDATE": "LIVE CANDIDATE"}


def f(x, fmt="{:+.2f}", na="n/a"):
    try:
        if x is None or (isinstance(x, float) and not math.isfinite(x)):
            return na
        return fmt.format(x)
    except (TypeError, ValueError):
        return str(x)


def pct(x, na="n/a"):
    return f(x, "{:.1%}", na)


def metrics_table(rows: dict[str, dict]) -> str:
    keys = [("sharpe", "Sharpe", f), ("cagr", "CAGR", pct), ("volatility", "volatilité", pct),
            ("max_drawdown", "drawdown max", pct), ("sortino", "Sortino", f), ("calmar", "Calmar", f),
            ("n_trades", "trades", lambda v: f(v, "{:.0f}")), ("win_rate", "taux de réussite", pct),
            ("profit_factor", "profit factor", lambda v: f(v, "{:.2f}")),
            ("expectancy", "espérance / trade", lambda v: f(v * 1e4 if v is not None else None, "{:+.1f} bp")),
            ("exposure", "exposition", pct), ("skew", "skew", f), ("kurtosis", "kurtosis", lambda v: f(v, "{:.1f}")),
            ("tail_loss_cvar5", "CVaR 5 %", pct), ("recovery_bars", "récupération max (jours)", lambda v: f(v, "{:.0f}")),
            ("years", "années", lambda v: f(v, "{:.1f}"))]
    head = "| métrique | " + " | ".join(rows) + " |\n|---|" + "---|" * len(rows) + "\n"
    body = ""
    for k, label, fmt in keys:
        body += f"| {label} | " + " | ".join(fmt(r.get(k)) for r in rows.values()) + " |\n"
    return head + body


def candidate_report(c: Candidate, lab: Lab, extras: dict) -> str:
    h = c.hypothesis
    ac = lab.markets[c.market]
    d = c.details
    ppy = ac.periods_per_year
    base_key = cfg_key(c.configs[0])
    base_run = c.config_runs.get(base_key)
    from .metrics import compute

    base_m = compute(lab.vault.research(base_run.returns), base_run.trades[base_run.trades["exit_ts"] <= lab.vault.research_end]
                     if len(base_run.trades) else base_run.trades, ppy,
                     base_run.exposure.loc[:lab.vault.research_end]) if base_run else {}
    wf = c.wf
    wf_m = compute(wf["returns"], None, ppy) if wf.get("ok") else {}
    rob = d.get("robustness", {})
    mc_t, mc_b = d.get("mc_trades", {}), d.get("mc_block", {})
    dsr, pbo = d.get("dsr", {}), d.get("pbo", {})
    reg = d.get("regimes", {})
    cap = d.get("capacity", {})
    sig = lab.significance.get(c.market, {})
    audits = lab.audits.get(c.market, {})
    L = []
    w = L.append
    w(f"# {h.name} — {c.market}\n")
    w(f"**Décision : {DECISION_FR[c.decision]}** — " + "; ".join(c.reasons) + "\n")
    w("> Ce rapport documente une tentative de falsification. Aucun chiffre ci-dessous n'est une prévision.\n")
    w("## 1. Hypothèse de marché\n")
    w(f"{h.claim}\n\n*Pourquoi cela pourrait marcher :* {h.rationale}\n")
    w("## 2. Stratégie retail\n")
    w(f"Famille **{h.family}**. Signal : {h.signal}. Condition : {h.condition}. Horizon : {h.horizon}. "
      f"Cible mesurée : {h.target}. Risque : {h.risk}.\n")
    w("## 3. Formulation mathématique\n")
    w(f"`{FORMULAS.get(h.name, '')}`\n\nExécution : décision sur la clôture de t, exécution à l'ouverture de t+1.\n")
    w("## 4. Implémentation quant\n")
    w(f"`qt/lab/strategies.py::{h.func.__name__ if h.func else h.name}` — baseline `{c.configs[0]}`, "
      f"candidat retenu par le walk-forward `{c.candidate_cfg}` (configuration la plus souvent choisie). "
      f"Dimensionnement de recherche : chaque instrument à {lab.sizing['target_vol_per_instrument']:.0%} de volatilité "
      f"(fenêtre {lab.sizing['vol_lookback_days']} j, levier max {lab.sizing['max_leverage_per_instrument']}), "
      "panier équipondéré en risque de la classe.\n")
    w("## 5. Données\n")
    w("| instrument | début | années | note d'audit | problèmes |\n|---|---|---|---|---|\n")
    for s, a in audits.items():
        w(f"| {s} | {a['first']} | {a['years']} | {a['grade']} | {'; '.join(a['issues'][:2]) or '—'} |\n")
    w("\n## 6. Backtest (période de recherche, après coûts)\n")
    cand_run = c.config_runs[cfg_key(c.candidate_cfg)]
    w(metrics_table({"baseline": base_m, "candidat": c.research_metrics}))
    w("\nLe candidat est choisi par le walk-forward, pas par ce tableau : ce tableau est in-sample.\n")
    w("## 7. Hors échantillon\n")
    rows = {"walk-forward OOS": wf_m}
    if "test" in d:
        rows["test 2020-2022"] = d["test"]
    if "holdout" in d:
        rows["holdout 2023→"] = d["holdout"]
    w(metrics_table(rows))
    if "test" not in d:
        w("\nPériodes test et holdout **non ouvertes** : la stratégie n'a pas passé toutes les portes pré-test.\n")
    w("## 8. Walk-forward\n")
    if wf.get("ok"):
        w(f"Sharpe OOS {f(wf['sharpe'])} ; années positives {pct(wf['positive_years'])} ; stabilité des paramètres "
          f"{pct(wf['param_stability'])} ; baseline sans sélection sur les mêmes années {f(wf['baseline_oos_sharpe'])} ; "
          f"ratio OOS/IS {f(wf['is_oos_ratio'])}.\n\n")
        w("| année OOS | fenêtre train | configuration choisie | Sharpe train | Sharpe OOS |\n|---|---|---|---|---|\n")
        for _, r in wf["folds"].iterrows():
            w(f"| {r['year']} | {r['train']} | {r['config']} | {f(r['train_sharpe'])} | {f(r['oos_sharpe'])} |\n")
    w("\n## 9. Robustesse\n")
    if rob:
        w(f"Score {pct(rob['score'])} sur {rob['n_perturbations']} perturbations ; ratio voisins/optimum "
          f"{f(rob['neighbour_ratio'])}{' — **optimum en pic**' if rob['sharp_peak'] else ''}.\n\n")
        w("| perturbation | type | Sharpe | tient ? |\n|---|---|---|---|\n")
        for _, r in rob["table"].iterrows():
            w(f"| {r['name']} | {r['kind']} | {f(r['sharpe'])} | {'oui' if r['passed'] else 'non'} |\n")
    w("\n## 10. Monte Carlo\n")
    if mc_b.get("n_paths"):
        w(f"Bootstrap par blocs de 21 jours ({mc_b['n_paths']} chemins) : drawdown max médian "
          f"{pct(mc_b['max_drawdown'][0.5])}, 5e centile {pct(mc_b['max_drawdown'][0.05])} ; CAGR médian "
          f"{pct(mc_b['cagr'][0.5])} [{pct(mc_b['cagr'][0.05])} ; {pct(mc_b['cagr'][0.95])}] ; P(perte) {pct(mc_b['prob_loss'])}. "
          f"P(drawdown au-delà de) : " + ", ".join(f"{k} → {pct(v)}" for k, v in mc_b["prob_drawdown_beyond"].items()) + ".\n")
    if mc_t.get("n_paths"):
        w(f"\nRééchantillonnage des trades (ordre, 10 % de trades manqués, coûts × U(1 ; 1,5), bruit) : "
          f"série perdante médiane {f(mc_t['losing_streak'][0.5], '{:.0f}')} trades, 95e centile "
          f"{f(mc_t['losing_streak'][0.95], '{:.0f}')} ; P(perte) {pct(mc_t['prob_loss'])}. "
          "(Compose les trades en série, donc ignore leur simultanéité : indicatif, ne décide pas.)\n")
    w("\n## 11. Significativité statistique\n")
    w(f"Sharpe déflaté **{f(dsr.get('deflated_sharpe'), '{:.3f}')}** sur {dsr.get('n_trials')} essais cumulés "
      f"(Sharpe attendu du meilleur essai par chance : {f(dsr.get('benchmark_sharpe'))}) — {dsr.get('verdict', '')}. "
      f"PBO de la grille : {f(pbo.get('pbo'), '{:.2f}')}. Reality Check / SPA sur les {sig.get('n_models', 'n/a')} "
      f"stratégies de la classe : p = {f(sig.get('rc_pvalue'), '{:.3f}')} / {f(sig.get('spa_pvalue'), '{:.3f}')} "
      f"(meilleure : {sig.get('best_model', 'n/a')}).\n")
    w("\n## 12. Capacité\n")
    if cap.get("measurable"):
        w(f"Edge net moyen {f(cap['edge_bps_per_trade'], '{:+.1f}')} bp par trade. Moitié de l'edge perdue en impact vers "
          f"{f(cap.get('capacity_half_edge'), '{:,.0f} $')}, edge nul vers {f(cap.get('capacity_zero_edge'), '{:,.0f} $')} "
          "(loi en racine carrée, coefficient 1).\n")
    else:
        w(f"{cap.get('reason', 'non mesurée')}\n")
    w("\n## 13. Coûts\n")
    w(f"Modèle : {ac.costs.describe()}. Part des coûts dans le résultat brut : "
      f"{pct(c.research_metrics.get('cost_share'))}. Sharpe avec coûts × 1,5 : {f(d.get('cost_x1_5_sharpe'))}.\n")
    w("\n## 14. Drawdown\n")
    w(f"Recherche : max {pct(c.research_metrics.get('max_drawdown'))}, moyen {pct(c.research_metrics.get('avg_drawdown'))}, "
      f"plus long passage sous l'eau {f(c.research_metrics.get('recovery_bars'), '{:.0f}')} jours. Walk-forward OOS : max "
      f"{pct(wf_m.get('max_drawdown'))}.\n")
    w("\n## 15. Dépendance aux régimes (sur l'OOS walk-forward)\n")
    for axis in ("direction", "volatility", "crisis", "character"):
        rows_ = reg.get(axis, {})
        if rows_:
            w(f"- **{axis}** : " + " ; ".join(f"{k} Sharpe {f(v['sharpe'])} ({pct(v['share_days'])} des jours)"
                                             for k, v in rows_.items()) + "\n")
    w(f"\nDépendance détectée : {', '.join(reg.get('dependency', [])) or 'aucune concentration > 80 % du PnL'}. "
      "Aucun filtre de régime n'est ajouté dans ce cycle : le protocole exige qu'il améliore l'OOS, ce sera un essai compté.\n")
    w("\n## 16. Risque de sur-apprentissage\n")
    w(f"{dsr.get('n_trials')} essais enregistrés dans la base ; grille de {len(c.configs)} configurations déclarée "
      f"avant exécution ; stabilité des paramètres {pct(wf.get('param_stability'))} ; PBO {f(pbo.get('pbo'), '{:.2f}')} ; "
      f"ratio OOS/IS {f(wf.get('is_oos_ratio'))}.\n")
    w("\n## 17. Exigences pour une mise en œuvre réelle\n")
    w("- données quotidiennes fiables à la clôture, exécution à l'ouverture suivante (ordres au marché ou stop) ;\n"
      "- spread et slippage réels mesurés en paper ≤ 1,5 × le modèle ;\n"
      f"- {f(c.research_metrics.get('trades_per_year'), '{:.0f}')} trades / an sur la classe ; exposition moyenne "
      f"{pct(c.research_metrics.get('exposure'))} ;\n"
      "- relevé papier ≥ 60 jours / 30 trades avant toute décision LIVE CANDIDATE.\n")
    w("\n## 18. Compatibilité prop firms (gabarits illustratifs, pas des firmes réelles)\n")
    pc = extras.get("prop", {})
    if pc:
        for name, table in pc.items():
            w(f"\n**{name}** — Monte Carlo sur un an (horizon 252 jours), flux de recherche remis à l'échelle :\n\n")
            w("| vol annuelle visée | levier vs recherche | P(réussite) | P(échec perte jour) | P(échec drawdown) | P(ni l'un ni l'autre) | jours médians |\n|---|---|---|---|---|---|---|\n")
            for _, r in table.iterrows():
                w(f"| {pct(r.get('target_vol'))} | × {r['risk_scale']:.2f} | {pct(r['p_pass'])} | {pct(r['p_fail_daily'])} | {pct(r['p_fail_drawdown'])} | "
                  f"{pct(r['p_timeout'])} | {f(r['median_days_to_pass'], '{:.0f}')} |\n")
    else:
        w("Non simulée.\n")
    w("\n## 19. Conditions d'échec\n")
    w(f"Attendues a priori : {h.falsification}\n")
    worst = []
    for axis in ("direction", "volatility", "character"):
        for k, v in reg.get(axis, {}).items():
            if np.isfinite(v["sharpe"]) and v["sharpe"] < 0:
                worst.append(f"{axis} = {k} (Sharpe {f(v['sharpe'])})")
    w(f"\nObservées sur l'OOS : {', '.join(worst) or 'aucun régime à Sharpe négatif'}.\n")
    w("\n## 20. Décision de recherche\n")
    w(f"**{DECISION_FR[c.decision]}**. " + " ".join(f"- {r}" for r in c.reasons) + "\n")
    score = d.get("score", {})
    if score:
        w("\nScore interne (organise la file de recherche ; **n'est pas une prévision de performance**) : "
          + ", ".join(f"{k} {v:.2f}" for k, v in score.items()) + "\n")
    return "".join(L)


def summary(lab: Lab, extras: dict, *, cycle_id: int, protocol_hash: str, markets_hash: str, git_commit: str,
            n_trials: int, elapsed_min: float) -> str:
    L = []
    w = L.append
    counts = pd.Series([c.decision for c in lab.candidates]).value_counts().to_dict()
    w(f"# Cycle de recherche {cycle_id:03d}\n\n")
    w(f"Protocole `{protocol_hash}` · marchés `{markets_hash}` · code `{git_commit}` · {n_trials} essais enregistrés · "
      f"{elapsed_min:.0f} min.\n\n")
    w("## Résultat en une phrase\n\n")
    paper = [c for c in lab.candidates if c.decision == "PAPER_TEST"]
    prom = [c for c in lab.candidates if c.decision == "PROMISING"]
    if paper:
        w(f"**{len(paper)} stratégie(s) au statut PAPER TEST**, {len(prom)} PROMISING, le reste rejeté. "
          "Aucune n'est LIVE CANDIDATE : ce statut exige un relevé papier, qui n'existe pas encore.\n\n")
    else:
        w(f"**Aucune stratégie n'atteint PAPER TEST.** {len(prom)} restent PROMISING (elles passent le walk-forward mais "
          "échouent à au moins une porte statistique ou de robustesse), toutes les autres sont rejetées.\n\n")
    w("| décision | nombre |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in counts.items()) + "\n")
    w("## Tableau des décisions (stratégie × classe d'actifs)\n\n")
    markets = list(lab.markets)
    w("| stratégie | " + " | ".join(markets) + " |\n|---|" + "---|" * len(markets) + "\n")
    grid = {(c.hypothesis.name, c.market): c for c in lab.candidates}
    skipped = {(s["strategy"], s["market"]): s for s in lab.skipped}
    abbrev = {"REJECTED": "✗", "PROMISING": "◐", "PAPER_TEST": "●", "NOT_APPLICABLE": "—", "DEFERRED": "…"}
    for h in HYPOTHESES:
        if h.kind == "deferred":
            continue
        cells = []
        for m in markets:
            c = grid.get((h.name, m))
            if c:
                wf = c.wf.get("sharpe")
                cells.append(f"{abbrev[c.decision]} {f(wf)}" if wf is not None else abbrev[c.decision])
            elif (h.name, m) in skipped:
                cells.append(abbrev[skipped[(h.name, m)]["status"]])
            else:
                cells.append("")
        w(f"| {h.name} | " + " | ".join(cells) + " |\n")
    w("\n✗ REJECTED · ◐ PROMISING · ● PAPER TEST · — non applicable · chiffre = Sharpe walk-forward OOS après coûts.\n\n")
    w("## Le meilleur de N : Reality Check (White) et SPA (Hansen)\n\n")
    w("| classe | stratégies | p RC | p SPA | meilleure | t |\n|---|---|---|---|---|---|\n")
    for m, s in lab.significance.items():
        w(f"| {m} | {s.get('n_models')} | {f(s.get('rc_pvalue'), '{:.3f}')} | {f(s.get('spa_pvalue'), '{:.3f}')} | "
          f"{s.get('best_model', '')} | {f(s.get('best_t_stat'))} |\n")
    w("\nLecture : p > 0,05 = le meilleur résultat de la classe est compatible avec ce que la recherche du meilleur "
      "parmi N stratégies sans edge produirait par chance.\n\n")
    w("## Survivants de la première porte\n\n")
    surv = sorted([c for c in lab.candidates if c.decision != "REJECTED"],
                  key=lambda c: -c.details.get("score", {}).get("composite", 0))
    if surv:
        w("| classe | stratégie | config | Sharpe WF | robustesse | DSR | PBO | P(DD>25 %) | décision | raison principale |\n"
          "|---|---|---|---|---|---|---|---|---|---|\n")
        for c in surv:
            d = c.details
            w(f"| {c.market} | [{c.hypothesis.name}](candidates/{c.market}__{c.hypothesis.name}.md) | {c.candidate_cfg} | "
              f"{f(c.wf.get('sharpe'))} | {pct(d.get('robustness', {}).get('score'))} | "
              f"{f(d.get('dsr', {}).get('deflated_sharpe'), '{:.2f}')} | {f(d.get('pbo', {}).get('pbo'), '{:.2f}')} | "
              f"{pct(d.get('prob_dd25'))} | {DECISION_FR[c.decision]} | {c.reasons[0] if c.reasons else ''} |\n")
    else:
        w("Aucune.\n")
    inval = [c for c in lab.candidates if "decision_before_invalidation" in c.details]
    if inval:
        w("\n## Invalidations (vérification indépendante des données)\n\n")
        w("| classe | stratégie | décision du protocole | décision finale | raison |\n|---|---|---|---|---|\n")
        for c in inval:
            w(f"| {c.market} | {c.hypothesis.name} | {DECISION_FR[c.details['decision_before_invalidation']]} | REJECTED | "
              f"{c.reasons[0]} |\n")
        w("\nCes stratégies ont passé (ou auraient pu passer) les portes statistiques sur des données fausses. "
          "C'est la démonstration que les tests statistiques ne protègent pas d'un problème de données : seule une "
          "vérification sur une source indépendante l'a révélé.\n")
    for key, title in (("ensemble", "Ensemble"), ("sizing", "Dimensionnement"), ("meta", "Machine learning / méta-labeling")):
        if key in extras:
            w(f"\n## {title}\n\n{extras[key]}\n")
    w("\n## Données\n\n| classe | instrument | début | années | note | problèmes |\n|---|---|---|---|---|---|\n")
    for m, audits in lab.audits.items():
        for s, a in audits.items():
            w(f"| {m} | {s} | {a['first']} | {a['years']} | {a['grade']} | {'; '.join(a['issues'][:2]) or '—'} |\n")
    w("\n## Hypothèses différées\n\n")
    for h in HYPOTHESES:
        if h.kind == "deferred":
            w(f"- **{h.name}** — {h.deferred_reason}\n")
    return "".join(L)
