"""Conditionner au régime de marché : est-ce que ça ajoute quelque chose, ou est-ce
que c'est de la décoration ?

Le module de régimes markoviens existe depuis longtemps dans ce dépôt et n'a jamais
nourri une seule décision. C'est exactement la situation où l'on suppose qu'un composant
aide parce qu'il est sophistiqué. Ce script le met à l'épreuve sur les deux questions qui
comptent, et il est écrit pour pouvoir répondre non.

**Question 1 — le livre qui marche.** Le livre trend + risk parity fait un Sharpe mesuré
de ~0,97. Est-ce que ce Sharpe est concentré dans un régime ? Si oui, couper le livre
dans le mauvais régime vaut plus que n'importe quelle recherche de signal
supplémentaire. Si le Sharpe est le même partout, le modèle de régime ne sert à rien.

**Question 2 — la prédiction horaire qui ne marche pas.** La resolution mesurée est de
0,0002 pour un seuil de 0,005. Peut-être que la direction est prévisible *dans un
régime donné* et que mélanger les régimes noie le signal. C'est la dernière hypothèse
non testée avant de conclure que la prédiction horaire n'existe pas.

Trois pièges évités
-------------------
1. **Probabilités filtrées, jamais lissées.** Les probabilités lissées de statsmodels
   utilisent tout l'échantillon à chaque point. Un backtest piloté par elles est
   magnifique et sans valeur.
2. **Réestimation glissante.** Un modèle estimé sur tout l'historique connaît 2021 quand
   il étiquette 2021.
3. **Le régime est connu avec un jour de retard.** Le régime d'aujourd'hui se lit sur le
   rendement d'aujourd'hui, qui n'est connu qu'à la clôture. Trader dessus le même jour,
   c'est lire le journal de demain. Tout est décalé d'une barre, et le script mesure ce
   que ce décalage coûte, parce que c'est là que les backtests de régime mentent.

Lancer :  .venv/bin/python -u scripts/research_regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qt.backtest import BacktestConfig, compare  # noqa: E402
from qt.backtest.engine import run_backtest  # noqa: E402
from qt.backtest.portfolio_backtest import AllocationSpec, build_weights  # noqa: E402
from qt.config import CostModel  # noqa: E402
from qt.data.catalog import Catalog  # noqa: E402
from qt.data.sources.yahoo import UNIVERSES  # noqa: E402
from qt.econometrics.regime_switching import regime_probabilities  # noqa: E402
from qt.risk import apply_no_trade_band, portfolio_vol_target  # noqa: E402
from qt.strategies.trend import TrendSpec, build_trend, combine_trend_and_allocator  # noqa: E402
from qt.validation import deflated_sharpe_ratio  # noqa: E402

pd.set_option("display.width", 240)

ETF_COSTS = CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=1.5)
START = "2010-01-01"
TARGET_VOL = 0.10
BLEND = 0.3          # the configuration measured best in research_trend.py
# Configurations evaluated here, counted honestly for the deflation below: two state
# counts, gating on each of two vol ranks, plus the ungated baseline.
TRIALS = 5


def load_total_return(catalog: Catalog, symbols) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        df = catalog.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
        df = df.loc[START:].copy()
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype("float64") * ratio.loc[df.index]
        out[symbol] = df
    return out


def annualised(returns: pd.Series, periods: float = 252) -> tuple[float, float]:
    sd = float(returns.std(ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return np.nan, np.nan
    return float(returns.mean() / sd * np.sqrt(periods)), sd * np.sqrt(periods)


# ------------------------------------------------------------------ question 1
def book_by_regime(cat: Catalog) -> None:
    bars = load_total_return(cat, UNIVERSES["multi_asset"])
    prices = pd.DataFrame({s: b["close"] for s, b in bars.items()}).dropna()
    bars = {s: b.loc[prices.index] for s, b in bars.items()}
    returns = np.log(prices).diff()

    cfg = BacktestConfig(bars_per_year=252, costs=ETF_COSTS, allow_short=True,
                         signal_is_weight=True, max_weight_per_symbol=0.60)

    trend = build_trend(prices, TrendSpec())
    allocation, _ = build_weights(prices, AllocationSpec(
        method="risk_parity", lookback=252, rebalance_every=21,
        covariance="ledoit_wolf", max_weight=0.25, min_history=252))
    combined = combine_trend_and_allocator(trend.signal, allocation, blend=BLEND)

    def run(weights: pd.DataFrame):
        w = portfolio_vol_target(weights, returns, target_annual_vol=TARGET_VOL,
                                 bars_per_year=252, max_leverage=3.0)
        w = apply_no_trade_band(w)
        aligned = {s: b.loc[b.index.intersection(w.index)] for s, b in bars.items()}
        return run_backtest(aligned, w, cfg)

    baseline = run(combined)
    book_returns = baseline.equity.pct_change().dropna()

    print("=" * 82)
    print("QUESTION 1 — LE LIVRE QUI MARCHE EST-IL PORTÉ PAR UN SEUL RÉGIME ?\n")
    print("  Le livre trend + risk parity fait un Sharpe de ~0,97 sur 2010-2026.")
    print("  Si tout ce Sharpe vient d'un seul régime, couper le livre dans l'autre")
    print("  vaut plus que n'importe quelle recherche de signal supplémentaire.\n")

    # The regime is estimated on the market's own returns, not the book's: conditioning a
    # book on its own realised performance is circular.
    market = np.log(prices["SPY"]).diff().dropna()

    results: dict[str, object] = {"sans filtre": baseline}
    summary_rows = []

    for n_states in (2, 3):
        regimes = regime_probabilities(market, n_states=n_states, lookback=1000,
                                       refit_every=250, min_train=500)
        # A regime read from today's return is only actionable tomorrow.
        rank = regimes["vol_rank"].shift(1).reindex(book_returns.index)

        table = pd.concat([book_returns.rename("ret"), rank.rename("rank")],
                          axis=1).dropna()
        if table.empty:
            print(f"  {n_states} régimes : aucune estimation exploitable")
            continue

        print(f"--- {n_states} régimes (classés par volatilité, 0 = le plus calme)\n")
        rows = []
        for r, group in table.groupby("rank"):
            sharpe, vol = annualised(group["ret"])
            rows.append({
                "régime": int(r),
                "jours": len(group),
                "part du temps": len(group) / len(table),
                "rendement moyen/j": float(group["ret"].mean()),
                "vol annualisée": vol,
                "Sharpe": sharpe,
                "% jours positifs": float((group["ret"] > 0).mean()),
            })
        by_regime = pd.DataFrame(rows)
        print(by_regime.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        print()

        # Gating: hold the book only outside the worst regime.
        worst = int(by_regime.loc[by_regime["Sharpe"].idxmin(), "régime"])
        mask = (rank != worst).astype("float64").reindex(combined.index).fillna(1.0)
        gated = run(combined.mul(mask, axis=0))
        results[f"hors régime {worst} ({n_states} états)"] = gated

        summary_rows.append({
            "modèle": f"{n_states} régimes",
            "régime coupé": worst,
            "part du temps coupée": float((rank == worst).mean()),
            "écart de Sharpe entre régimes": float(by_regime["Sharpe"].max()
                                                   - by_regime["Sharpe"].min()),
        })

    table = compare(results, 252)
    keep = [c for c in ("cagr", "annual_vol", "sharpe", "max_drawdown", "calmar",
                        "turnover_annual", "cost_share_of_gross") if c in table.columns]
    print("=" * 82)
    print("CE QUE LE FILTRE CHANGE, TOUT COMPRIS (COÛTS INCLUS)\n")
    print(table[keep].sort_values("sharpe", ascending=False).to_string())

    if summary_rows:
        print("\n" + pd.DataFrame(summary_rows).to_string(index=False,
                                                          float_format=lambda v: f"{v:.4f}"))

    base_sharpe = float(table.loc["sans filtre", "sharpe"])
    best_name = table["sharpe"].astype("float64").idxmax()
    best_sharpe = float(table.loc[best_name, "sharpe"])
    print(f"\n  sans filtre        : Sharpe {base_sharpe:.3f}")
    print(f"  meilleur avec filtre: {best_name} — Sharpe {best_sharpe:.3f}")
    gain = best_sharpe - base_sharpe
    print(f"  gain               : {gain:+.3f}")

    if best_name != "sans filtre":
        curve = results[best_name].equity.pct_change().dropna()
        sharpes = table["sharpe"].astype("float64").dropna().to_numpy()
        dsr = deflated_sharpe_ratio(curve, n_trials=TRIALS,
                                    sr_variance=float(np.var(sharpes, ddof=1))
                                    if len(sharpes) > 1 else None,
                                    periods_per_year=252)
        print(f"  DSR du meilleur    : {dsr}")
    if gain < 0.05:
        print("\n  -> le filtre de régime ne paie pas sur ce livre. Le Sharpe est réparti")
        print("     entre les régimes, donc il n'y a pas de mauvais régime à couper.")

    # ------------------------------------------------------------------ honesty
    # Everything above picked the regime to cut by looking at the Sharpe of every
    # regime over the whole sample — which is choosing the configuration on the data it
    # is then scored on. On three states that is three tries, and the best of three
    # tries on a noisy statistic beats the baseline about as often as not. The only
    # version of this test that means anything picks the regime on the first half and
    # is scored on the second.
    print("\n" + "=" * 82)
    print("LE MÊME TEST, SANS REGARDER LA RÉPONSE D'ABORD\n")
    print("  Ci-dessus, le régime à couper a été choisi en regardant tout l'historique,")
    print("  puis mesuré sur ce même historique. C'est la façon la plus courante de")
    print("  produire un résultat flatteur sans écrire une seule affirmation fausse.")
    print("  Ici le régime est choisi sur 2010-2018 et le filtre est mesuré sur")
    print("  2018-2026, que le choix soit bon ou mauvais.\n")

    for n_states in (2, 3):
        regimes = regime_probabilities(market, n_states=n_states, lookback=1000,
                                       refit_every=250, min_train=500)
        rank = regimes["vol_rank"].shift(1).reindex(book_returns.index)
        joint = pd.concat([book_returns.rename("ret"), rank.rename("rank")],
                          axis=1).dropna()
        if len(joint) < 500:
            continue

        cut = len(joint) // 2
        first, second = joint.iloc[:cut], joint.iloc[cut:]
        sharpes = {int(r): annualised(g["ret"])[0] for r, g in first.groupby("rank")
                   if len(g) > 50}
        if len(sharpes) < 2:
            continue
        chosen = min(sharpes, key=lambda k: sharpes[k])

        split_date = second.index[0]
        mask = (rank != chosen).astype("float64").reindex(combined.index).fillna(1.0)
        oos_gated = run(combined.mul(mask, axis=0))

        base_oos = baseline.equity.loc[split_date:].pct_change().dropna()
        gated_oos = oos_gated.equity.loc[split_date:].pct_change().dropna()
        s_base, _ = annualised(base_oos)
        s_gate, _ = annualised(gated_oos)

        print(f"  {n_states} régimes — choisi sur 2010-{first.index[-1].year} : "
              f"couper le régime {chosen} (Sharpe {sharpes[chosen]:.2f} sur cette moitié)")
        print(f"    hors échantillon ({split_date.date()} → {second.index[-1].date()}) : "
              f"sans filtre {s_base:.3f}  ·  avec filtre {s_gate:.3f}  ·  "
              f"écart {s_gate - s_base:+.3f}")

    print("\n  C'est cet écart-là qui compte, pas celui du tableau précédent.")
    return None


# ------------------------------------------------------------------ question 2
def prediction_by_regime(cat: Catalog) -> None:
    """La direction horaire est-elle prévisible *à l'intérieur* d'un régime ?"""
    from research_prediction import features_for, triple_barrier

    print("\n" + "=" * 82)
    print("QUESTION 2 — LA DIRECTION HORAIRE EST-ELLE PRÉVISIBLE DANS UN RÉGIME DONNÉ ?\n")
    print("  Mélanger un marché calme et un marché violent peut noyer un signal qui")
    print("  n'existe que dans l'un des deux. C'est la dernière hypothèse avant de")
    print("  conclure que la prédiction horaire n'existe pas.\n")

    from lightgbm import LGBMClassifier

    rows = []
    for symbol in ("QQQ", "GLD", "SPY"):
        bars = cat.read_indexed("eod_1h", "yahoo", symbol)
        if bars.empty:
            continue
        X = features_for(bars)
        labels = triple_barrier(bars, 6)
        usable = X.notna().all(axis=1) & labels.notna() & (labels != 0)
        X, y = X[usable], (labels[usable] > 0).astype(int)
        if len(X) < 800:
            continue

        hourly = np.log(bars["close"].astype("float64")).diff().dropna()
        regimes = regime_probabilities(hourly, n_states=2, lookback=1500,
                                       refit_every=400, min_train=600)
        rank = regimes["vol_rank"].shift(1).reindex(X.index)

        # One walk-forward split, applied identically inside each regime, so the
        # comparison is against the same model rather than against a differently sized
        # training set.
        split = int(len(X) * 0.6)
        model = LGBMClassifier(n_estimators=200, num_leaves=15, learning_rate=0.05,
                               min_child_samples=40, subsample=0.8, colsample_bytree=0.8,
                               verbose=-1, random_state=0)
        model.fit(X.iloc[:split], y.iloc[:split])
        test = np.arange(split + 30, len(X))
        pred = model.predict(X.iloc[test])
        truth = y.iloc[test].to_numpy()
        rank_test = rank.iloc[test].to_numpy()

        overall = float((pred == truth).mean())
        for r in (0.0, 1.0):
            sel = rank_test == r
            if sel.sum() < 100:
                continue
            accuracy = float((pred[sel] == truth[sel]).mean())
            base = float(max(truth[sel].mean(), 1 - truth[sel].mean()))
            # Is the excess over the base rate distinguishable from zero?
            k = int((pred[sel] == truth[sel]).sum())
            n = int(sel.sum())
            p_value = float(stats.binomtest(k, n, base, alternative="greater").pvalue)
            rows.append({
                "actif": symbol,
                "régime": "calme" if r == 0.0 else "agité",
                "heures": n,
                "précision": accuracy,
                "taux de base": base,
                "excès": accuracy - base,
                "p-value": p_value,
            })
        rows.append({"actif": symbol, "régime": "TOUS", "heures": len(test),
                     "précision": overall, "taux de base": np.nan,
                     "excès": np.nan, "p-value": np.nan})

    if not rows:
        print("  aucune donnée horaire exploitable")
        return

    table = pd.DataFrame(rows)
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    conditional = table[table["régime"] != "TOUS"]
    if not conditional.empty:
        best = conditional.loc[conditional["excès"].idxmax()]
        n_significant = int((conditional["p-value"] < 0.05).sum())
        print(f"\n  meilleur excès conditionnel : {best['excès']:+.4f} "
              f"({best['actif']}, régime {best['régime']}, p={best['p-value']:.3f})")
        print(f"  résultats significatifs à 5 % : {n_significant} / {len(conditional)}")
        print(f"  attendu par pur hasard        : {0.05 * len(conditional):.1f}")
        if n_significant <= 0.05 * len(conditional) + 1:
            print("\n  -> conditionner au régime ne fait pas apparaître de prédiction.")
            print("     Le signal n'était pas noyé : il n'y en a pas.")


def main() -> None:
    cat = Catalog()
    book_by_regime(cat)
    prediction_by_regime(cat)

    print("\n" + "=" * 82)
    print("CE QU'IL FAUT EN RETENIR\n")
    print("  Un modèle de régime ne crée pas de signal. Il ne peut que redistribuer")
    print("  celui qui existe déjà — et si le rendement est réparti uniformément entre")
    print("  les régimes, il n'y a rien à redistribuer. Les deux tableaux ci-dessus")
    print("  disent lequel des deux cas s'applique ici.")


if __name__ == "__main__":
    main()
