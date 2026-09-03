"""Le fade d'extrême, seul survivant : est-ce un vrai avantage ou soixante séances de chance ?

`research_meanrev.py` a testé cinq stratégies de scalping. Une seule a un avantage brut
réel : le fade d'extrême (z-score), +1,93 bp en moyenne sur quinze actifs, et jusqu'à
+8,6 bp sur EEM. C'est plus que le coût. Mais sur soixante séances les t valent 1,28,
0,96, 0,66 — rien de significatif, et « le meilleur de cinq stratégies sur le meilleur
de quinze actifs » est exactement la forme que prend le bruit quand on le cherche.

Ce script décide, et il est construit pour pouvoir dire non.

Trois durcissements par rapport au premier passage
--------------------------------------------------
**1. Des coûts par actif, pas une moyenne.** Appliquer 3 bp d'aller-retour à SPY comme à
DBC est faux dans les deux sens : ça condamne SPY à tort et ça absout DBC à tort. La
fourchette réelle va de 0,5 bp d'aller-retour sur SPY à 8 bp sur DBC. C'est le paramètre
qui décide si un avantage de 2 bp existe ou non, donc il ne peut pas être une constante.

**2. Trois ans de données horaires, pas soixante séances.** Yahoo donne 730 jours en
horaire contre 60 en 5 minutes. Un avantage de retour à la moyenne qui existe doit se
voir aux deux fréquences ; s'il ne vit qu'à une seule, c'est un artefact.

**3. Hors échantillon.** Les paramètres — fenêtre, seuil, durée de détention — sont
choisis sur la première moitié de l'historique horaire et mesurés sur la seconde. Sans
ça, ce script mesurerait sa propre capacité à ajuster trois paramètres.

Lancer :  .venv/bin/python -u scripts/research_zfade.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES

pd.set_option("display.width", 240)

# Demi-fourchette par actif, en points de base, pour un ordre au marché de détail.
#
# Ce sont des ESTIMATIONS, pas des mesures : les barres Yahoo ne portent pas de
# cotations bid/ask, donc rien ici ne peut vérifier ces chiffres. Ils viennent des
# fourchettes typiques publiées pour ces ETF et ils sont volontairement pessimistes sur
# les lignes peu liquides. Comme c'est le paramètre qui décide du verdict, la sensibilité
# du résultat à ces valeurs est mesurée explicitement en fin de script.
HALF_SPREAD_BPS = {
    "SPY": 0.25, "QQQ": 0.35, "IWM": 0.80, "EFA": 1.00, "EEM": 1.50,
    "TLT": 0.80, "IEF": 0.80, "LQD": 1.00, "HYG": 1.00, "GLD": 0.60,
    "SLV": 1.50, "USO": 2.50, "DBC": 4.00, "UUP": 3.00, "VNQ": 1.50,
}

GRID_WINDOWS = (12, 24, 48)
GRID_THRESHOLDS = (1.5, 2.0, 2.5, 3.0)
GRID_HOLDS = (3, 6, 12)


def load(cat: Catalog, symbol: str, dataset: str) -> pd.DataFrame:
    bars = cat.read_indexed(dataset, "yahoo", symbol)
    if bars.empty:
        return bars
    bars = bars.copy()
    bars["session"] = (bars["session_id"] if "session_id" in bars.columns
                       else bars.index.normalize().astype("int64"))
    return bars


def zfade_signal(bars: pd.DataFrame, window: int, threshold: float) -> pd.Series:
    close = bars["close"].astype("float64")
    mean = close.rolling(window, min_periods=window // 2).mean()
    sd = close.rolling(window, min_periods=window // 2).std(ddof=0)
    z = (close - mean) / sd.replace(0.0, np.nan)
    return pd.Series(np.where(z > threshold, -1.0, np.where(z < -threshold, 1.0, 0.0)),
                     index=bars.index).replace(0.0, np.nan)


def forward_return(close: pd.Series, session: pd.Series, hold: int) -> pd.Series:
    fwd = close.shift(-hold) / close - 1.0
    return fwd.where(session.shift(-hold) == session)


def evaluate(signal: pd.Series, fwd: pd.Series, *, hold: int, cost_bps: float,
             bars_per_year: float) -> dict:
    """Rendement net d'un signal, entrée retardée d'une barre, coûts payés."""
    entered = signal.shift(1)
    live = entered.notna() & (entered != 0) & fwd.notna()
    n = int(live.sum())
    if n < 60:
        return {"trades": n, "gain_net_bp": np.nan, "t": np.nan, "p": np.nan,
                "sharpe": np.nan, "gain_brut_bp": np.nan}

    gross = (entered[live] * fwd[live]).astype("float64")
    net = gross - cost_bps / 1e4
    sd = float(net.std(ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return {"trades": n, "gain_net_bp": np.nan, "t": np.nan, "p": np.nan,
                "sharpe": np.nan, "gain_brut_bp": float(gross.mean() * 1e4)}

    # Les trades se chevauchent sur `hold` barres : le t naïf est gonflé d'un facteur
    # racine(hold). La division est la correction conservatrice.
    t = float(net.mean() / sd * np.sqrt(n)) / np.sqrt(hold)
    return {
        "trades": n,
        "gain_brut_bp": float(gross.mean() * 1e4),
        "gain_net_bp": float(net.mean() * 1e4),
        "% gagnants": float((net > 0).mean()),
        "t": t,
        "p": float(2 * (1 - stats.norm.cdf(abs(t)))),
        "sharpe": float(net.mean() / sd * np.sqrt(bars_per_year / hold)),
    }


def round_trip(symbol: str, multiplier: float = 1.0) -> float:
    return 2 * HALF_SPREAD_BPS.get(symbol, 2.0) * multiplier


def sweep(cat: Catalog, symbols, dataset: str, bars_per_year: float,
          *, index=None, cost_multiplier: float = 1.0) -> pd.DataFrame:
    """Toute la grille de paramètres sur tous les actifs, sur une tranche de temps."""
    rows = []
    for symbol in symbols:
        bars = load(cat, symbol, dataset)
        if bars.empty or len(bars) < 400:
            continue
        if index is not None:
            bars = bars.loc[bars.index.isin(index)]
            if len(bars) < 200:
                continue
        close = bars["close"].astype("float64")
        cost = round_trip(symbol, cost_multiplier)

        for window in GRID_WINDOWS:
            for threshold in GRID_THRESHOLDS:
                signal = zfade_signal(bars, window, threshold)
                for hold in GRID_HOLDS:
                    fwd = forward_return(close, bars["session"], hold)
                    stats_row = evaluate(signal, fwd, hold=hold, cost_bps=cost,
                                         bars_per_year=bars_per_year)
                    if stats_row["trades"] < 60:
                        continue
                    rows.append({"actif": symbol, "fenêtre": window, "seuil": threshold,
                                 "détention": hold, "coût_bp": cost, **stats_row})
    return pd.DataFrame(rows)


def main() -> None:
    cat = Catalog()
    symbols = list(UNIVERSES["multi_asset"])
    hourly_year = 6.5 * 252

    print("=" * 96)
    print("LE FADE D'EXTRÊME EST-IL UN VRAI AVANTAGE ?\n")
    print("  C'est la seule des cinq stratégies de scalping à avoir un avantage brut.")
    print("  Reste à savoir si c'est un avantage ou soixante séances de chance.\n")

    # -------------------------------------------------- 1. horaire, in/out sample
    probe = load(cat, "SPY", "eod_1h")
    if probe.empty:
        print("aucune donnée horaire")
        return
    midpoint = probe.index[len(probe) // 2]
    in_index = probe.index[probe.index <= midpoint]
    out_index = probe.index[probe.index > midpoint]

    print("=" * 96)
    print("ÉTAPE 1 — CHOISIR LES PARAMÈTRES SUR LA PREMIÈRE MOITIÉ (horaire)\n")
    print(f"  apprentissage : {in_index[0].date()} -> {in_index[-1].date()}")
    print(f"  vérification  : {out_index[0].date()} -> {out_index[-1].date()}")
    print(f"  grille        : {len(GRID_WINDOWS)}x{len(GRID_THRESHOLDS)}x{len(GRID_HOLDS)} "
          f"= {len(GRID_WINDOWS) * len(GRID_THRESHOLDS) * len(GRID_HOLDS)} configurations\n")

    in_sample = sweep(cat, symbols, "eod_1h", hourly_year, index=in_index)
    if in_sample.empty:
        print("pas assez de données horaires")
        return

    pooled = in_sample.groupby(["fenêtre", "seuil", "détention"]).agg(
        actifs=("actif", "count"),
        trades=("trades", "sum"),
        gain_net_bp=("gain_net_bp", "mean"),
        actifs_positifs=("gain_net_bp", lambda s: int((s > 0).sum())),
        sharpe=("sharpe", "mean"),
    ).sort_values("gain_net_bp", ascending=False)
    print(pooled.head(8).to_string(float_format=lambda v: f"{v:.3f}"))

    best = pooled.index[0]
    window, threshold, hold = int(best[0]), float(best[1]), int(best[2])
    print(f"\n  meilleure configuration en apprentissage : fenêtre {window}, "
          f"seuil {threshold}, détention {hold} barres")
    print(f"  gain moyen : {pooled.iloc[0]['gain_net_bp']:+.3f} bp · "
          f"{int(pooled.iloc[0]['actifs_positifs'])}/15 actifs positifs")

    # -------------------------------------------------------- 2. hors échantillon
    print("\n" + "=" * 96)
    print("ÉTAPE 2 — LA MÊME CONFIGURATION SUR LA SECONDE MOITIÉ, SANS RIEN CHANGER\n")

    out_sample = sweep(cat, symbols, "eod_1h", hourly_year, index=out_index)
    chosen = out_sample[(out_sample["fenêtre"] == window)
                        & (out_sample["seuil"] == threshold)
                        & (out_sample["détention"] == hold)]
    if chosen.empty:
        print("  configuration non évaluable hors échantillon")
        return

    print(chosen[["actif", "trades", "coût_bp", "gain_brut_bp", "gain_net_bp",
                  "% gagnants", "t", "p", "sharpe"]]
          .sort_values("gain_net_bp", ascending=False)
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    mean_net = float(chosen["gain_net_bp"].mean())
    n_positive = int((chosen["gain_net_bp"] > 0).sum())
    n_sig_pos = int(((chosen["p"] < 0.05) & (chosen["gain_net_bp"] > 0)).sum())
    # Le livre entier : chaque actif pèse pareil, ce qui est la seule façon de traiter
    # les quinze sans choisir lesquels après coup.
    pooled_t = (float(chosen["gain_net_bp"].mean())
                / (float(chosen["gain_net_bp"].std(ddof=1)) / np.sqrt(len(chosen)))
                if len(chosen) > 1 and chosen["gain_net_bp"].std(ddof=1) > 0 else np.nan)

    print(f"\n  gain net moyen hors échantillon : {mean_net:+.3f} bp par trade")
    print(f"  actifs positifs                 : {n_positive} / {len(chosen)}")
    print(f"  positifs ET significatifs       : {n_sig_pos} / {len(chosen)}")
    print(f"  t du livre entier (équipondéré) : {pooled_t:.2f}")

    # ------------------------------------------------------- 3. la même en 5 min
    print("\n" + "=" * 96)
    print("ÉTAPE 3 — LA MÊME CHOSE EN 5 MINUTES, SUR 60 SÉANCES INDÉPENDANTES\n")
    print("  Un avantage réel doit se voir aux deux fréquences. S'il ne vit qu'à une")
    print("  seule, c'est un artefact de cette fréquence-là.\n")

    five = sweep(cat, symbols, "eod_5m", 78 * 252)
    if not five.empty:
        f_chosen = five[(five["fenêtre"] == window) & (five["seuil"] == threshold)
                        & (five["détention"] == hold)]
        if not f_chosen.empty:
            print(f"  configuration identique (fenêtre {window}, seuil {threshold}, "
                  f"détention {hold}) :")
            print(f"    gain net moyen  : {f_chosen['gain_net_bp'].mean():+.3f} bp")
            print(f"    actifs positifs : {int((f_chosen['gain_net_bp'] > 0).sum())} "
                  f"/ {len(f_chosen)}")
            print(f"    meilleur        : {f_chosen.loc[f_chosen['gain_net_bp'].idxmax(), 'actif']} "
                  f"à {f_chosen['gain_net_bp'].max():+.3f} bp")

    # ----------------------------------------------- 4. sensibilité aux coûts
    print("\n" + "=" * 96)
    print("ÉTAPE 4 — TOUT DÉPEND DES COÛTS, DONC VOICI LA SENSIBILITÉ\n")
    print("  Les fourchettes utilisées sont des estimations et rien ici ne peut les")
    print("  vérifier. Si le verdict bascule entre 0,5x et 2x, il ne repose pas sur")
    print("  les données mais sur mon estimation de la fourchette.\n")

    print("  multiplicateur | gain net moyen | actifs positifs")
    print("  " + "-" * 52)
    for multiplier in (0.5, 1.0, 1.5, 2.0):
        s = sweep(cat, symbols, "eod_1h", hourly_year, index=out_index,
                  cost_multiplier=multiplier)
        c = s[(s["fenêtre"] == window) & (s["seuil"] == threshold)
              & (s["détention"] == hold)]
        if c.empty:
            continue
        print(f"       x{multiplier:<11.1f}| {c['gain_net_bp'].mean():+13.3f} bp "
              f"| {int((c['gain_net_bp'] > 0).sum())} / {len(c)}")

    # ------------------------------------------------------------- le verdict
    print("\n" + "=" * 96)
    print("LE VERDICT\n")
    if mean_net > 0 and n_positive > len(chosen) * 0.6 and np.isfinite(pooled_t) and pooled_t > 2:
        print(f"  Le fade d'extrême survit hors échantillon : {mean_net:+.3f} bp net par")
        print(f"  trade, {n_positive}/{len(chosen)} actifs positifs, t={pooled_t:.2f}.")
        print("  C'est un avantage exploitable. Reste à le dimensionner et à vérifier")
        print("  qu'il tient en papier sur des données réelles.")
    else:
        print(f"  Le fade d'extrême ne survit pas hors échantillon : {mean_net:+.3f} bp net,")
        print(f"  {n_positive}/{len(chosen)} actifs positifs, t={pooled_t:.2f} — il en")
        print("  faudrait plus de 2 pour distinguer ça de zéro.")
        print("\n  L'avantage brut est réel : le prix revient bien après un écart. Ce qui")
        print("  n'est pas réel, c'est qu'il reste quelque chose une fois la fourchette")
        print("  payée. C'est le sort habituel du scalping de détail — l'avantage existe,")
        print("  il appartient à celui qui tient le carnet d'ordres, pas à celui qui le")
        print("  traverse.")


if __name__ == "__main__":
    main()
