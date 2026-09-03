"""Les vraies stratégies de scalping : le retour à la moyenne, pas la prédiction.

Un trou dans le travail précédent, et il est important.

`research_prediction.py` demandait « un modèle peut-il prédire la direction de la
prochaine heure ? ». Réponse : non, 49,96 % hors échantillon. Mais **aucun scalpeur ne
fait ça**. Le scalping classique ne prédit pas la direction : il parie que ce qui vient
de bouger trop va revenir. C'est une hypothèse structurellement différente, et elle n'a
jamais été testée ici.

Les cinq stratégies testées, toutes causales, toutes sur barres de 5 minutes :

* **Retour au VWAP** — le prix s'écarte du prix moyen pondéré par les volumes de la
  séance, on parie sur le retour. C'est le scalp le plus pratiqué au monde.
* **Fade d'extrême (z-score)** — le prix s'écarte de N écarts-types de sa moyenne
  courte, on prend le contre.
* **Fade du gap d'ouverture** — le marché ouvre loin de la clôture de la veille, on
  parie que l'écart se comble.
* **Cassure de la fourchette d'ouverture** — le contraire : on suit la cassure des
  trente premières minutes. Inclus parce que c'est la stratégie que tout le monde
  oppose au fade, et qu'il serait malhonnête de ne tester que les hypothèses de retour.
* **Retournement après série** — N barres consécutives dans le même sens, on parie sur
  le retournement.

Trois exigences, sans quoi le résultat ne veut rien dire
-------------------------------------------------------
1. **Le coût est payé sur chaque aller-retour.** Un scalp gagne quelques points de base ;
   la fourchette en coûte autant. Une stratégie de scalping testée sans coût est un
   générateur de nombres.
2. **Aucune position ne traverse la clôture.** Sinon ce n'est plus du scalping, et le
   rendement mesuré est celui du risque overnight.
3. **Quinze actifs, un seul jeu de paramètres.** Un seuil optimisé par actif sur soixante
   séances trouve un signal à tous les coups. Les paramètres sont fixés une fois, les
   quinze actifs sont quinze tests du même pari, et c'est la cohérence entre eux qui
   décide — pas le meilleur d'entre eux.

Lancer :  .venv/bin/python -u scripts/research_meanrev.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES

pd.set_option("display.width", 240)

# Un aller-retour sur ETF liquide chez un courtier sans commission : la moitié de la
# fourchette à l'entrée, la moitié à la sortie. 1,5 bp par jambe est le mélange mesuré
# sur ce livre (SPY à 0,25 bp, DBC à plusieurs).
COST_BPS_PER_SIDE = 1.5
HOLD_BARS = 6                # 30 minutes sur des barres de 5 minutes
BARS_PER_YEAR = 78 * 252     # 78 barres de 5 min par séance


def load(cat: Catalog, symbol: str) -> pd.DataFrame:
    bars = cat.read_indexed("eod_5m", "yahoo", symbol)
    if bars.empty:
        return bars
    bars = bars.copy()
    bars["session"] = bars["session_id"] if "session_id" in bars.columns \
        else bars.index.normalize().astype("int64")
    return bars


def forward_return(close: pd.Series, session: pd.Series, hold: int) -> pd.Series:
    """Rendement des `hold` prochaines barres, NaN si ça traverse la clôture.

    Le masque de séance n'est pas un détail : sans lui, une position ouverte à 15h55
    encaisse le mouvement de nuit, et la stratégie mesurée n'est plus du scalping mais
    du portage overnight déguisé.
    """
    fwd = close.shift(-hold) / close - 1.0
    same_session = session.shift(-hold) == session
    return fwd.where(same_session)


def evaluate(signal: pd.Series, fwd: pd.Series, *, hold: int) -> dict:
    """Ce que rapporte un signal, coûts payés, une fois entré avec un retard d'une barre.

    Le retard n'est pas une prudence excessive : le signal se lit sur la clôture de la
    barre t, un ordre passé après cette clôture s'exécute sur la barre suivante.
    Compter le rendement depuis la clôture de t est un look-ahead d'une barre, et sur
    des barres de 5 minutes il représente la totalité de l'avantage recherché.
    """
    entered = signal.shift(1)
    live = entered.notna() & (entered != 0) & fwd.notna()
    n = int(live.sum())
    if n < 100:
        return {"trades": n}

    gross = (entered[live] * fwd[live]).astype("float64")
    cost = 2 * COST_BPS_PER_SIDE / 1e4          # aller-retour
    net = gross - cost

    sd = float(net.std(ddof=1))
    # Les trades se chevauchent (`hold` barres), donc les rendements sont corrélés en
    # série. Le t de Student naïf surestime alors la significativité d'un facteur
    # racine(hold). La correction de Newey-West serait plus fine ; diviser le t par
    # racine(hold) est la version conservatrice, et pour trancher « signal ou pas » elle
    # suffit.
    t_naive = float(net.mean() / sd * np.sqrt(n)) if sd > 0 else np.nan
    t_adj = t_naive / np.sqrt(hold) if np.isfinite(t_naive) else np.nan

    return {
        "trades": n,
        "gain_brut_bp": float(gross.mean() * 1e4),
        "coût_bp": cost * 1e4,
        "gain_net_bp": float(net.mean() * 1e4),
        "% gagnants": float((net > 0).mean()),
        "t_ajusté": t_adj,
        "p": float(2 * (1 - stats.norm.cdf(abs(t_adj)))) if np.isfinite(t_adj) else np.nan,
        "sharpe_annualisé": (float(net.mean() / sd * np.sqrt(BARS_PER_YEAR / hold))
                             if sd > 0 else np.nan),
    }


# ------------------------------------------------------------------ stratégies
def vwap_reversion(bars: pd.DataFrame, threshold: float = 1.5) -> pd.Series:
    """Écart au VWAP de la séance, en écarts-types. On prend le contre au-delà du seuil."""
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    volume = bars["volume"].astype("float64").replace(0.0, np.nan)
    group = bars.groupby("session")
    vwap = ((typical * volume).groupby(bars["session"]).cumsum()
            / volume.groupby(bars["session"]).cumsum())
    gap = (bars["close"] - vwap) / bars["close"]
    sd = gap.groupby(bars["session"]).transform(
        lambda s: s.expanding(min_periods=12).std(ddof=0))
    z = gap / sd.replace(0.0, np.nan)
    return pd.Series(np.where(z > threshold, -1.0, np.where(z < -threshold, 1.0, 0.0)),
                     index=bars.index).replace(0.0, np.nan)


def zscore_fade(bars: pd.DataFrame, window: int = 24, threshold: float = 2.0) -> pd.Series:
    close = bars["close"].astype("float64")
    mean = close.rolling(window, min_periods=window // 2).mean()
    sd = close.rolling(window, min_periods=window // 2).std(ddof=0)
    z = (close - mean) / sd.replace(0.0, np.nan)
    return pd.Series(np.where(z > threshold, -1.0, np.where(z < -threshold, 1.0, 0.0)),
                     index=bars.index).replace(0.0, np.nan)


def gap_fade(bars: pd.DataFrame, threshold: float = 0.002, bars_in: int = 6) -> pd.Series:
    """Fade du gap d'ouverture, sur les premières barres de la séance uniquement."""
    session_open = bars.groupby("session")["open"].transform("first")
    prior_close = bars.groupby("session")["close"].transform("last").shift(1)
    prior_close = prior_close.groupby(bars["session"]).transform("first")
    gap = (session_open - prior_close) / prior_close
    position_in_session = bars.groupby("session").cumcount()

    direction = np.where(gap > threshold, -1.0, np.where(gap < -threshold, 1.0, 0.0))
    return pd.Series(np.where(position_in_session < bars_in, direction, 0.0),
                     index=bars.index).replace(0.0, np.nan)


def opening_range_breakout(bars: pd.DataFrame, range_bars: int = 6) -> pd.Series:
    """Le contraire du fade : on suit la cassure de la fourchette d'ouverture."""
    position = bars.groupby("session").cumcount()
    opening = bars.where(position < range_bars)
    hi = opening.groupby(bars["session"])["high"].transform("max")
    lo = opening.groupby(bars["session"])["low"].transform("min")
    close = bars["close"]
    direction = np.where(close > hi, 1.0, np.where(close < lo, -1.0, 0.0))
    return pd.Series(np.where(position >= range_bars, direction, 0.0),
                     index=bars.index).replace(0.0, np.nan)


def streak_reversal(bars: pd.DataFrame, length: int = 4) -> pd.Series:
    """N barres consécutives dans le même sens : on parie sur le retournement."""
    sign = np.sign(bars["close"].diff())
    up = sign.rolling(length).sum() == length
    down = sign.rolling(length).sum() == -length
    return pd.Series(np.where(up, -1.0, np.where(down, 1.0, 0.0)),
                     index=bars.index).replace(0.0, np.nan)


STRATEGIES = {
    "retour au VWAP": vwap_reversion,
    "fade d'extrême (z)": zscore_fade,
    "fade du gap": gap_fade,
    "cassure d'ouverture": opening_range_breakout,
    "retournement de série": streak_reversal,
}


def main() -> None:
    cat = Catalog()
    symbols = [s for s in UNIVERSES["multi_asset"]]

    print("=" * 92)
    print("LE SCALPING QUI NE PRÉDIT PAS : LE RETOUR À LA MOYENNE\n")
    print("  Les stratégies testées ici ne devinent pas la direction. Elles parient que")
    print("  ce qui vient de trop bouger revient. C'est ce que font les vrais scalpeurs,")
    print("  et ça n'avait jamais été testé dans ce dépôt.\n")
    print(f"  barres de 5 minutes · détention {HOLD_BARS} barres (30 min) · "
          f"aller-retour {2 * COST_BPS_PER_SIDE:.1f} bp")
    print("  aucune position ne traverse la clôture · entrée retardée d'une barre\n")

    all_rows = []
    for name, fn in STRATEGIES.items():
        for symbol in symbols:
            bars = load(cat, symbol)
            if bars.empty or len(bars) < 500:
                continue
            fwd = forward_return(bars["close"].astype("float64"), bars["session"], HOLD_BARS)
            stats_row = evaluate(fn(bars), fwd, hold=HOLD_BARS)
            if stats_row.get("trades", 0) < 100:
                continue
            all_rows.append({"stratégie": name, "actif": symbol, **stats_row})

    if not all_rows:
        print("aucune donnée intraday — lancez l'ingestion 5 minutes d'abord")
        return

    table = pd.DataFrame(all_rows)

    print("=" * 92)
    print("RÉSUMÉ PAR STRATÉGIE — sur 15 actifs, un seul jeu de paramètres\n")
    summary = table.groupby("stratégie").agg(
        actifs=("actif", "count"),
        trades=("trades", "sum"),
        gain_brut_bp=("gain_brut_bp", "mean"),
        gain_net_bp=("gain_net_bp", "mean"),
        actifs_positifs=("gain_net_bp", lambda s: int((s > 0).sum())),
        sharpe_moyen=("sharpe_annualisé", "mean"),
        significatifs=("p", lambda s: int((s < 0.05).sum())),
    ).sort_values("gain_net_bp", ascending=False)
    print(summary.to_string(float_format=lambda v: f"{v:.3f}"))

    print("\n  « gain_brut_bp »   = avant coûts. C'est le chiffre que montrent les vendeurs.")
    print(f"  « gain_net_bp »    = après {2 * COST_BPS_PER_SIDE:.1f} bp d'aller-retour. "
          "C'est le seul qui compte.")
    print("  « actifs_positifs » = sur 15. Une pièce de monnaie en donne 7 ou 8.")
    print("  « significatifs »   = p < 5 %, t corrigé du chevauchement des trades.")
    print(f"  attendu par hasard  : {0.05 * len(table):.1f} sur {len(table)}")

    print("\n" + "=" * 92)
    print("CE QUE LE COÛT MANGE\n")
    for name, group in table.groupby("stratégie"):
        brut, net = group["gain_brut_bp"].mean(), group["gain_net_bp"].mean()
        share = (brut - net) / abs(brut) * 100 if brut else np.nan
        verdict = "survit" if net > 0 else "détruite par les coûts" if brut > 0 else "négative avant même les coûts"
        print(f"  {name:24s} brut {brut:+6.3f} bp -> net {net:+6.3f} bp   {verdict}")

    print("\n" + "=" * 92)
    print("LE DÉTAIL, STRATÉGIE PAR STRATÉGIE\n")
    for name, group in table.groupby("stratégie"):
        best = group.loc[group["gain_net_bp"].idxmax()]
        print(f"--- {name}")
        print(group[["actif", "trades", "gain_brut_bp", "gain_net_bp",
                     "% gagnants", "t_ajusté", "p", "sharpe_annualisé"]]
              .sort_values("gain_net_bp", ascending=False)
              .to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        print(f"    meilleur : {best['actif']} à {best['gain_net_bp']:+.3f} bp "
              f"(p={best['p']:.3f})\n")

    # -------------------------------------------------------------- le verdict
    print("=" * 92)
    print("LE VERDICT\n")
    winners = summary[summary["gain_net_bp"] > 0]
    n_sig_total = int((table["p"] < 0.05).sum())
    expected = 0.05 * len(table)

    if winners.empty:
        print("  Aucune des cinq stratégies n'est positive après coûts, en moyenne sur")
        print("  quinze actifs. Le scalping par retour à la moyenne ne marche pas sur ces")
        print("  ETF à cette fréquence — ce n'est pas une question de réglage, c'est que")
        print("  l'écart exploitable est plus petit que la fourchette qu'il faut payer.")
    else:
        print("  Stratégies positives après coûts, en moyenne :")
        for name, row in winners.iterrows():
            print(f"    {name:24s} {row['gain_net_bp']:+.3f} bp/trade · "
                  f"{int(row['actifs_positifs'])}/15 actifs positifs · "
                  f"Sharpe {row['sharpe_moyen']:.2f}")
        print("\n  Avant d'y croire : combien de ces résultats sont significatifs, et")
        print("  combien le seraient par pur hasard ?")
    print(f"\n  résultats significatifs à 5 % : {n_sig_total} / {len(table)}")
    print(f"  attendus par pur hasard       : {expected:.1f}")
    if n_sig_total <= expected + np.sqrt(expected):
        print("\n  -> indistinguable du hasard. Ce qui dépasse est le bruit qu'on attend")
        print("     en faisant soixante-quinze tests.")


if __name__ == "__main__":
    main()
