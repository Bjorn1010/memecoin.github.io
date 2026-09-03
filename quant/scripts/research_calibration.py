"""Quand le bot annonce 70 %, est-ce que ça arrive 70 % du temps ?

C'est la seule question de ce script, et elle se mesure comme une promesse se vérifie :
on note ce qui a été annoncé, on note ce qui est arrivé, on compare.

Le défaut corrigé ici
---------------------
La régression isotonique a le droit de sortir 0.0 et 1.0, et elle le fait à partir
d'une poignée d'observations. Sur le Nasdaq, les compartiments qui produisaient les
probabilités extrêmes contenaient 4, 10 et 16 observations : le modèle annonçait 99,8 %
et le marché montait 25 % du temps. Ce n'est pas une propriété des marchés, c'est un
calibrateur qui prend le bruit au premier degré.

`shrink_to_evidence` ramène chaque probabilité vers le taux de base à hauteur de ce que
les données autorisent (moyenne a posteriori Beta-Binomiale). Ce script mesure l'avant
et l'après sur les mêmes données, avec les mêmes plis, pour que le gain soit un chiffre
et pas une affirmation.

Deux chiffres décident :

  * **écart maximum** — le pire mensonge. Le compartiment où l'annonce s'éloigne le plus
    du réalisé. C'est ce que l'utilisateur subit quand il fait confiance au bot.
  * **erreur de calibration** — l'écart moyen, pondéré par le nombre d'observations dans
    chaque compartiment. C'est le terme « reliability » de la décomposition de Murphy.

Et un troisième qui empêche de tricher :

  * **amplitude** — de combien la probabilité bouge. Un modèle qui annonce toujours le
    taux de base est parfaitement calibré et parfaitement inutile : il ne peut produire
    aucune position. Rétrécir les probabilités améliore mécaniquement la calibration ;
    l'amplitude dit ce que ça a coûté.

Lancer :  .venv/bin/python -u scripts/research_calibration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qt.data.catalog import Catalog  # noqa: E402
from qt.models.probability import (  # noqa: E402
    brier_decomposition,
    reliability_curve,
    shrink_to_evidence,
)
from research_prediction import features_for, triple_barrier  # noqa: E402

pd.set_option("display.width", 240)

SYMBOLS = ["QQQ", "GLD", "SPY"]
NOMS = {"QQQ": "Nasdaq 100", "GLD": "or", "SPY": "S&P 500"}
HORIZON = 6
EMBARGO = 24
N_SPLITS = 4
PRIOR_STRENGTHS = (0.0, 10.0, 25.0, 50.0, 100.0, 200.0)


def walk(X: pd.DataFrame, y: pd.Series, prior_strength: float):
    """Same walk-forward as `fit_calibrated`, but returning the pieces to compare.

    Deliberately duplicated rather than imported: the point is to run the identical
    folds at several prior strengths, and a function that only returns the final
    probabilities cannot show what the shrinkage changed.
    """
    from lightgbm import LGBMClassifier
    from sklearn.isotonic import IsotonicRegression

    n = len(X)
    fold = n // (N_SPLITS + 1)
    out = pd.Series(np.nan, index=X.index, dtype="float64")

    for k in range(1, N_SPLITS + 1):
        train_end = k * fold
        calib_start = max(train_end - fold // 3, 0)
        fit_idx = np.arange(0, max(calib_start - HORIZON - EMBARGO, 0))
        cal_idx = np.arange(calib_start, train_end)
        test_idx = np.arange(train_end + HORIZON + EMBARGO, min(train_end + fold, n))
        if len(fit_idx) < 300 or len(cal_idx) < 100 or len(test_idx) < 50:
            continue

        model = LGBMClassifier(n_estimators=200, num_leaves=15, learning_rate=0.05,
                               min_child_samples=40, subsample=0.8,
                               colsample_bytree=0.8, verbose=-1, random_state=0)
        model.fit(X.iloc[fit_idx], y.iloc[fit_idx])

        cal_scores = model.predict_proba(X.iloc[cal_idx])[:, 1]
        cal_truth = y.iloc[cal_idx].to_numpy()
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(cal_scores, cal_truth)

        test_scores = model.predict_proba(X.iloc[test_idx])[:, 1]
        out.iloc[test_idx] = shrink_to_evidence(
            iso.predict(test_scores), test_scores, cal_scores, cal_truth,
            prior_strength=prior_strength,
        )
    return out


def score(probabilities: pd.Series, outcomes: pd.Series) -> dict:
    ok = probabilities.notna()
    p, o = probabilities[ok].to_numpy(), outcomes[ok].to_numpy()
    if len(p) < 50:
        return {}
    curve = reliability_curve(p, o, n_bins=10)
    decomposition = brier_decomposition(p, o, n_bins=10)
    gap = curve["écart"].abs()
    return {
        "observations": len(p),
        "écart max": float(gap.max()) if len(gap) else np.nan,
        "erreur de calibration": decomposition["reliability"],
        "resolution": decomposition["resolution"],
        "amplitude": float(np.percentile(p, 95) - np.percentile(p, 5)),
        "min": float(p.min()),
        "max": float(p.max()),
        "curve": curve,
    }


def main() -> None:
    cat = Catalog()
    print("=" * 82)
    print("EST-CE QUE CE QUE LE BOT ANNONCE ARRIVE ?\n")
    print("  On lui fait annoncer une probabilité de hausse sur des heures qu'il n'a")
    print("  jamais vues, puis on regarde ce que le marché a fait. Si le bot dit 70 %")
    print("  et que ça monte 70 % du temps, il est honnête. Sinon il ment, et la taille")
    print("  des positions suit ce mensonge.\n")

    summaries: list[dict] = []
    curves: dict[str, pd.DataFrame] = {}

    for symbol in SYMBOLS:
        bars = cat.read_indexed("eod_1h", "yahoo", symbol)
        if bars.empty:
            print(f"  {symbol} : aucune donnée horaire, ignoré")
            continue

        X = features_for(bars)
        labels = triple_barrier(bars, HORIZON)
        usable = X.notna().all(axis=1) & labels.notna() & (labels != 0)
        X, y = X[usable], (labels[usable] > 0).astype(int)
        if len(X) < 800:
            print(f"  {symbol} : {len(X)} observations, il en faut 800 — ignoré")
            continue

        for prior in PRIOR_STRENGTHS:
            stats = score(walk(X, y, prior), y)
            if not stats:
                continue
            curve = stats.pop("curve")
            if prior in (0.0, 50.0):
                curves[f"{symbol}·{prior:.0f}"] = curve
            summaries.append({"actif": symbol, "marché": NOMS.get(symbol, symbol),
                              "prior": prior, **stats})

    if not summaries:
        print("\naucun actif exploitable — lancez l'ingestion horaire d'abord")
        return

    table = pd.DataFrame(summaries)

    print("=" * 82)
    print("AVANT / APRÈS, PAR MARCHÉ\n")
    print("  prior = 0   : la calibration brute, celle qui annonçait 99,8 %")
    print("  prior = 50  : le réglage retenu\n")
    ba = table[table["prior"].isin([0.0, 50.0])].copy()
    ba["réglage"] = np.where(ba["prior"] == 0, "avant", "après")
    show = ba[["marché", "réglage", "écart max", "erreur de calibration",
               "resolution", "amplitude", "min", "max"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n" + "=" * 82)
    print("LE PRIX DU RÉGLAGE : PLUS HONNÊTE, MAIS PLUS PRUDENT\n")
    print("  Rétrécir les probabilités améliore forcément la calibration — à la limite,")
    print("  annoncer toujours 50 % est parfaitement calibré et totalement inutile.")
    print("  La colonne « amplitude » est ce garde-fou : si elle tombe à zéro, le bot")
    print("  ne peut plus prendre aucune position.\n")
    pivot = table.pivot_table(index="prior", values=["écart max", "erreur de calibration",
                                                     "resolution", "amplitude"],
                              aggfunc="mean")
    print(pivot.to_string(float_format=lambda v: f"{v:.4f}"))

    for name, curve in curves.items():
        symbol, prior = name.split("·")
        label = "avant" if prior == "0" else "après"
        print("\n" + "-" * 82)
        print(f"{NOMS.get(symbol, symbol).upper()} — {label} (annoncé contre réalisé)\n")
        print(curve.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n" + "=" * 82)
    print("CE QUE ÇA VEUT DIRE\n")
    after = table[table["prior"] == 50.0]
    before = table[table["prior"] == 0.0]
    if not after.empty and not before.empty:
        print(f"  pire écart annoncé/réalisé   : {before['écart max'].max():.3f} "
              f"-> {after['écart max'].max():.3f}")
        print(f"  erreur de calibration moyenne: {before['erreur de calibration'].mean():.5f} "
              f"-> {after['erreur de calibration'].mean():.5f}")
        print(f"  amplitude moyenne            : {before['amplitude'].mean():.3f} "
              f"-> {after['amplitude'].mean():.3f}")
        print("\n  Une probabilité honnête n'est pas une probabilité rentable. Ce script")
        print("  mesure l'honnêteté ; c'est `SkillGate` qui décide si ce qu'il reste")
        print("  suffit pour trader, et sur ces données il bloque encore.")


if __name__ == "__main__":
    main()
