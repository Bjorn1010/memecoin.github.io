"""Le chemin vers la rentabilité, calculé — pas raconté.

Ce script ne propose rien qui n'ait été mesuré ailleurs dans ce dépôt. Il prend la seule
stratégie dont le Sharpe survit à une déflation honnête, il la fait tourner, et il en
tire l'arithmétique jusqu'au bout : ce que ça rapporte sur 500 €, ce qu'il faudrait pour
atteindre 20 €/heure, et ce que coûterait de forcer ce chiffre.

Pourquoi ce script existe
-------------------------
Un objectif exprimé en euros par heure n'est pas une affirmation sur une stratégie, c'est
une affirmation sur du **capital**. Une fois le taux de rendement fixé, le capital suit
par division. 20 €/heure sur 500 €, c'est 35 040 % par an. Sur 5 M€, c'est 3,5 %. La
stratégie est la même. Cette division doit être faite avant le travail, pas découverte
après.

Ce qui a déjà été mesuré et écarté
----------------------------------
Le chemin ne repasse pas par là. Chacune de ces impasses est un script de ce dépôt :

* scalping 20 € sur 40 € en 10 minutes  -> 0,000 % des fenêtres sur 10 ETF
* prédiction de direction horaire       -> 49,96 % hors échantillon, il en faut 53,3 %
* day trading crypto                    -> négatif même à coût nul : pas de signal
* quatre primes de style                -> seule la tendance marche ; DSR 0,0004 combinées
* conditionner au régime de marché      -> −0,32 à −0,81 de Sharpe hors échantillon

Lancer :  .venv/bin/python -u scripts/chemin_rentabilite.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qt.backtest import BacktestConfig
from qt.backtest.engine import run_backtest
from qt.backtest.portfolio_backtest import AllocationSpec, build_weights
from qt.config import CostModel
from qt.data.catalog import Catalog
from qt.data.sources.yahoo import UNIVERSES
from qt.live.objective import HOURS_PER_YEAR, Objective, capital_table
from qt.risk import apply_no_trade_band, portfolio_vol_target
from qt.sizing.ruin import drawdown_probability
from qt.strategies.trend import TrendSpec, build_trend, combine_trend_and_allocator

pd.set_option("display.width", 240)

ETF_COSTS = CostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=1.5)
START = "2010-01-01"
CAPITAL = 500.0
TARGET_PER_HOUR = 20.0
BASIS = "us_market_hours"          # 6.5 h x 252 sessions = 1 638 h of open market a year


def fr(value: float, decimals: int = 0) -> str:
    """French number formatting: a narrow space groups thousands, a comma marks decimals.

    Not cosmetic. Python's `{:,}` renders 6552 as "6,552", which a French reader parses
    as six-point-five — off by a factor of a thousand, in the direction that makes an
    impossible target look reachable. This script exists to stop exactly that kind of
    misreading, so it must not produce one in its own output.
    """
    return f"{value:,.{decimals}f}".replace(",", "\u202f").replace(".", ",")


def measured_book(cat: Catalog, target_vol: float = 0.10):
    """The one configuration whose Sharpe survives deflation: rp + 30% trend."""
    out = {}
    for symbol in UNIVERSES["multi_asset"]:
        df = cat.read_indexed("eod", "yahoo", symbol)
        if df.empty:
            continue
        ratio = df["adj_close"].astype("float64") / df["close"].astype("float64")
        df = df.loc[START:].copy()
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype("float64") * ratio.loc[df.index]
        out[symbol] = df

    prices = pd.DataFrame({s: b["close"] for s, b in out.items()}).dropna()
    out = {s: b.loc[prices.index] for s, b in out.items()}
    returns = np.log(prices).diff()

    trend = build_trend(prices, TrendSpec())
    allocation, _ = build_weights(prices, AllocationSpec(
        method="risk_parity", lookback=252, rebalance_every=21,
        covariance="ledoit_wolf", max_weight=0.25, min_history=252))
    combined = combine_trend_and_allocator(trend.signal, allocation, blend=0.3)

    w = portfolio_vol_target(combined, returns, target_annual_vol=target_vol,
                             bars_per_year=252, max_leverage=3.0)
    w = apply_no_trade_band(w)
    aligned = {s: b.loc[b.index.intersection(w.index)] for s, b in out.items()}
    return run_backtest(aligned, w, BacktestConfig(
        bars_per_year=252, costs=ETF_COSTS, allow_short=True,
        signal_is_weight=True, max_weight_per_symbol=0.60))


def stats_of(result) -> dict:
    equity = result.equity
    rets = equity.pct_change().dropna()
    years = len(rets) / 252
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)
    vol = float(rets.std(ddof=1) * np.sqrt(252))
    dd = float((equity / equity.cummax() - 1).min())
    return {"cagr": cagr, "vol": vol, "sharpe": cagr / vol if vol else np.nan,
            "max_dd": dd, "years": years,
            "hit_rate": float((rets > 0).mean())}


def main() -> None:
    cat = Catalog()
    hours = HOURS_PER_YEAR[BASIS]

    print("=" * 82)
    print("ÉTAPE 1 — CE QUI MARCHE VRAIMENT, MESURÉ\n")
    result = measured_book(cat)
    s = stats_of(result)
    print(f"  Livre : risk parity + 30 % de tendance, 15 ETF, {s['years']:.1f} ans")
    print(f"  rendement annuel   : {s['cagr'] * 100:6.2f} %")
    print(f"  volatilité         : {s['vol'] * 100:6.2f} %")
    print(f"  Sharpe             : {s['sharpe']:6.3f}")
    print(f"  pire perte          : {s['max_dd'] * 100:6.1f} %")
    print(f"  jours positifs     : {s['hit_rate'] * 100:6.1f} %")
    print("\n  C'est le seul résultat du dépôt qui survit à une déflation honnête.")
    print("  Tout le reste — scalping, prédiction horaire, régimes — a été mesuré")
    print("  et écarté. Le chemin part d'ici parce qu'il n'y a rien d'autre.")

    # ------------------------------------------------------------------ étape 2
    print("\n" + "=" * 82)
    print(f"ÉTAPE 2 — CE QUE ÇA DONNE SUR {CAPITAL:.0f} €\n")
    per_year = CAPITAL * s["cagr"]
    print(f"  {CAPITAL:.0f} € x {s['cagr'] * 100:.2f} % = {per_year:.2f} € par an")
    print(f"  soit {per_year / 12:.2f} € par mois")
    print(f"  soit {per_year / hours:.4f} € par heure de marché ouvert")
    print(f"\n  objectif demandé   : {TARGET_PER_HOUR:.2f} € / heure")
    print(f"  atteint            : {per_year / hours:.4f} € / heure")
    print(f"  facteur manquant   : x{fr(TARGET_PER_HOUR / (per_year / hours))}")

    # ------------------------------------------------------------------ étape 3
    print("\n" + "=" * 82)
    print("ÉTAPE 3 — LES DEUX SEULES FAÇONS DE COMBLER CET ÉCART\n")
    objective = Objective(TARGET_PER_HOUR, CAPITAL, BASIS)
    print(f"  Sur {CAPITAL:.0f} €, {TARGET_PER_HOUR:.0f} €/heure exige "
          f"{fr(objective.required_return * 100)} % par an.")
    print("  Le meilleur fonds de l'histoire (Medallion) fait 66 % par an brut,")
    print("  fermé aux capitaux extérieurs depuis 1993.\n")

    print("  (a) Augmenter le capital — le seul levier qui n'achète pas du risque :\n")
    print(capital_table(objective).to_string(index=False))
    needed = objective.required_capital(s["cagr"])
    print(f"\n  Au rendement RÉELLEMENT mesuré ci-dessus ({s['cagr'] * 100:.2f} %),")
    print(f"  il faudrait {fr(needed)} € pour sortir {TARGET_PER_HOUR:.0f} €/heure.")

    print("\n  (b) Augmenter le risque — ce que ça coûte, calculé :\n")
    rows = []
    for multiple in (1, 2, 5, 10, 20, 50):
        vol = s["vol"] * multiple
        ret = s["cagr"] * multiple          # Sharpe constant : le rendement suit le risque
        rows.append({
            "levier": f"x{multiple}",
            "volatilité": f"{vol * 100:.0f} %",
            "rendement attendu": f"{ret * 100:.1f} %",
            "€/heure": round(CAPITAL * ret / hours, 3),
            "pire perte attendue": f"{s['max_dd'] * multiple * 100:.0f} %",
        })
    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    print("\n  La colonne « pire perte » est celle qu'on saute. Au levier x10 le livre")
    print("  a déjà perdu tout le capital une fois sur la période mesurée — et il n'y a")
    print("  pas de deuxième chance après −100 %.")

    ruin_multiple = TARGET_PER_HOUR * hours / (CAPITAL * s["cagr"])
    print(f"\n  Pour {TARGET_PER_HOUR:.0f} €/heure sur {CAPITAL:.0f} € il faudrait un")
    print(f"  levier de x{fr(ruin_multiple)}, soit une volatilité de "
          f"{fr(s['vol'] * ruin_multiple * 100)} %.")
    print("  Ce n'est pas un réglage agressif, c'est une garantie de ruine au premier jour.")

    # ------------------------------------------------------------------ étape 4
    print("\n" + "=" * 82)
    print("ÉTAPE 4 — LA PROBABILITÉ DE RUINE, SIMULÉE\n")
    print("  Même avec un avantage réel, une mise trop grosse ruine. Voici la")
    print(f"  probabilité de perdre la moitié du capital, au taux de réussite mesuré")
    print(f"  du livre ({s['hit_rate'] * 100:.1f} % de jours positifs) :\n")
    rows = []
    for fraction in (0.01, 0.02, 0.05, 0.10, 0.25, 0.50):
        d = drawdown_probability(s["hit_rate"], payoff=1.0, bet_fraction=fraction,
                                 drawdown=0.50, n_bets=252, n_paths=3000)
        rows.append({
            "part du capital risquée par jour": f"{fraction * 100:.0f} %",
            "P(perdre 50 % en 1 an)": f"{d['probability_of_breach'] * 100:.1f} %",
            "pire perte médiane": f"{d['median_worst_drawdown'] * 100:.1f} %",
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # ------------------------------------------------------------------ étape 5
    print("\n" + "=" * 82)
    print("ÉTAPE 5 — LE CHEMIN RÉALISTE, PAR ÉTAPES VÉRIFIABLES\n")
    milestones = pd.DataFrame([
        {"étape": "1. Papier, 3 mois",
         "critère de réussite": "l'écart entre le live et le backtest reste sous 0,5 pt de CAGR",
         "outil": "scripts/replay_live.py",
         "état": "outil prêt, à laisser tourner"},
        {"étape": "2. Battre le Livret A",
         "critère de réussite": f"> 3 % net par an, soit {CAPITAL * 0.03:.0f} €/an sur {CAPITAL:.0f} €",
         "outil": "qt.live.objective",
         "état": f"backtest à {s['cagr'] * 100:.1f} %, non prouvé en live"},
        {"étape": "3. Tenir une perte réelle",
         "critère de réussite": f"survivre à −{abs(s['max_dd']) * 100:.0f} % sans couper",
         "outil": "qt.risk breaker",
         "état": "jamais testé sur de l'argent"},
        {"étape": "4. Capitaliser",
         "critère de réussite": f"le seul levier honnête vers {TARGET_PER_HOUR:.0f} €/h",
         "outil": "arithmétique",
         "état": f"{fr(needed)} € requis au rendement mesuré"},
    ])
    print(milestones.to_string(index=False))

    print("\n" + "=" * 82)
    print("LA CONCLUSION, SANS ENROBAGE\n")
    print(f"  Le bot a une stratégie qui marche : {s['cagr'] * 100:.1f} % par an, Sharpe")
    print(f"  {s['sharpe']:.2f}, mesurée sur {s['years']:.0f} ans avec les coûts. C'est un")
    print("  vrai résultat — la plupart des bots amateurs n'en ont aucun.")
    print(f"\n  Sur {CAPITAL:.0f} €, ça fait {per_year / 12:.2f} € par mois.")
    print(f"  L'objectif de {TARGET_PER_HOUR:.0f} €/heure sur {CAPITAL:.0f} € demande "
          f"{fr(objective.required_return * 100)} % par an.")
    print("  Aucune stratégie au monde ne fait ça, et aucun réglage de ce bot ne le fera.")
    print("\n  Le chemin rentable existe, mais c'est celui-ci : une stratégie modeste et")
    print("  vérifiée, appliquée à du capital qui grandit. Pas un multiplicateur caché")
    print("  dans un calcul de quant. J'ai cherché ce multiplicateur dans cinq directions")
    print("  différentes ; les cinq sont mesurées négatives et listées en tête de ce fichier.")


if __name__ == "__main__":
    main()
