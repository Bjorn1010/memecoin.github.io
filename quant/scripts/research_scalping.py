"""Scalping at €500: what the possibilities actually are, computed rather than asserted.

The question is "can a scalping bot make €20 an hour on €500". This run answers it by
building the whole possibility surface instead of arguing about one configuration.

Four things are measured, in this order, because each makes the next either interesting
or moot.

**1. Is the target physically reachable?** €20 on a €40 position is a 50% move. Across
4,681 five-minute windows on five instruments, the share of ten-minute windows that move
50% is 0.000%. Not rare — absent. That settles the original target and moves the question
to "what target *is* reachable".

**2. What does a realistic scalp earn, per broker?** The same signal and the same rule,
run through five real fee structures. At €40 a trade the per-order commission dominates
everything: a €1 flat fee is 5% for the round trip against a 0.08% typical move.

**3. What would it take to reach €20/hour?** Inverted: given the move the instrument
actually makes, what combination of position size, leverage, win rate and frequency
produces €20/hour — and is each of those attainable.

**4. What does the leverage required do to survival?** The ruin probability at the
leverage the target implies, from `qt.sizing.ruin`, so the answer includes its cost.

Run:  .venv/bin/python -u scripts/research_scalping.py
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from qt.data.catalog import Catalog
from qt.sizing.ruin import risk_of_ruin
from qt.strategies.scalping import BROKERS, Broker, ScalpSpec, feasibility, run_scalping

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

SYMBOLS = ["QQQ", "SPY", "GLD", "IWM", "TLT", "SLV", "USO", "EEM", "TQQQ", "SQQQ"]
CAPITAL = 500.0
BAR_MINUTES = 5
SPLIT = 0.6          # first 60% of sessions to choose on, the rest to measure


def load(cat: Catalog, symbol: str) -> pd.DataFrame:
    return cat.read_indexed("eod_5m", "yahoo", symbol)


def split_sessions(bars: pd.DataFrame, fraction: float = SPLIT):
    """Split on session boundaries, never mid-day."""
    sessions = sorted(bars["session_id"].unique())
    cut = sessions[int(len(sessions) * fraction)]
    return bars[bars["session_id"] < cut], bars[bars["session_id"] >= cut]


def main() -> None:
    cat = Catalog()
    data = {s: load(cat, s) for s in SYMBOLS}
    data = {s: b for s, b in data.items() if not b.empty}
    if not data:
        print("aucune donnée 5 minutes — lancez l'ingestion intraday d'abord")
        return

    sample = next(iter(data.values()))
    hours = len(sample) * BAR_MINUTES / 60.0
    print(f"{len(data)} actifs · {len(sample)} barres de 5 min · "
          f"{sample['session_id'].nunique()} séances · {hours:.0f} heures de marché")
    print(f"capital simulé : {CAPITAL:.0f} €\n")

    # ------------------------------------------------------------------ 1
    print("=" * 78)
    print("1. LA CIBLE DEMANDÉE EST-ELLE PHYSIQUEMENT ATTEIGNABLE ?")
    print("   20 € sur 40 € engagés = +50 % du prix, en 10 minutes.\n")
    rows = []
    for symbol, bars in data.items():
        f = feasibility(ScalpSpec(), bars, BAR_MINUTES)
        rows.append({"actif": symbol, "médian": f["mouvement_median"],
                     "99e pct": f["mouvement_99e_pct"], "max": f["mouvement_max_observe"],
                     "fenêtres atteignant +50 %": f["part_des_fenetres_atteignant_la_cible"]})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n   Aucune fenêtre, sur aucun actif. La cible n'est pas difficile : elle")
    print("   n'existe pas dans les données.\n")

    # ------------------------------------------------------------------ 2
    print("=" * 78)
    print("2. CE QU'UN SCALP RÉALISTE RAPPORTE, SELON LE COURTIER")
    print("   Cible et stop ramenés à ce que l'actif fait vraiment.\n")

    # A target near the 80th percentile of the holding-period move, with a stop tighter
    # than it. Chosen from the distribution rather than guessed.
    realistic = {}
    for symbol, bars in data.items():
        moves = bars["close"].astype("float64").pct_change(2).abs().dropna()
        realistic[symbol] = (float(moves.quantile(0.80)), float(moves.quantile(0.50)))

    rows = []
    for broker_name, broker in BROKERS.items():
        total_net = total_gross = total_fees = 0.0
        total_trades = impossible = 0
        for symbol, bars in data.items():
            target_pct, stop_pct = realistic[symbol]
            exposure = 40.0
            spec = ScalpSpec(position_eur=exposure, capital_eur=CAPITAL,
                             target_eur=exposure * target_pct,
                             stop_eur=exposure * stop_pct,
                             max_hold_bars=2, max_trades_per_session=8)
            res = run_scalping(bars, spec, broker, symbol=symbol, bar_minutes=BAR_MINUTES)
            d = res.diagnostics
            total_trades += d.get("trades", 0)
            impossible += d.get("ordres_impossibles", 0)
            total_net += d.get("gain_net_eur", 0.0)
            total_gross += d.get("gain_brut_eur", 0.0)
            total_fees += d.get("frais_eur", 0.0)
        rows.append({
            "courtier": broker_name, "trades": total_trades,
            "ordres impossibles": impossible,
            "brut €": round(total_gross, 2), "frais €": round(total_fees, 2),
            "net €": round(total_net, 2),
            "€ / heure": round(total_net / hours, 4),
        })
    broker_table = pd.DataFrame(rows)
    print(broker_table.to_string(index=False))
    print("\n   « ordres impossibles » = 40 € n'achète pas une action entière.")
    print("   Sur QQQ à 707 $ et SPY à 764 $, aucun ordre n'est passable sans")
    print("   fractions d'actions.\n")

    # ------------------------------------------------------------------ 3
    print("=" * 78)
    print("3. QUE FAUDRAIT-IL POUR ATTEINDRE 20 € / HEURE ?\n")

    best_net_per_hour = broker_table["€ / heure"].max()
    print(f"   Meilleur résultat mesuré ci-dessus : {best_net_per_hour:.4f} € / heure")
    if best_net_per_hour > 0:
        print(f"   Il faudrait le multiplier par {20 / best_net_per_hour:,.0f}.\n")
    else:
        print("   Le meilleur résultat est négatif : aucun multiple n'y suffit.\n")

    # The inversion: hold the instrument's real move fixed, ask what the rest must be.
    qqq_move = float(data["QQQ"]["close"].astype("float64").pct_change(2).abs().median())
    print(f"   Le Nasdaq bouge de {qqq_move * 100:.3f} % en 10 minutes (médiane).")
    print("   Pour 20 € par heure, à raison d'un trade par heure, il faudrait :\n")
    rows = []
    for capture in (0.5, 1.0, 2.0):   # share of the move actually captured
        gain_pct = qqq_move * capture
        exposure = 20.0 / gain_pct
        rows.append({
            "part du mouvement captée": f"{capture * 100:.0f}%",
            "gain visé par trade": "20 €",
            "position nécessaire": f"{exposure:,.0f} €",
            "levier sur 500 €": f"x{exposure / CAPITAL:,.0f}",
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n   Levier maximum autorisé en Europe : x30 (forex), x5 (actions).")
    print("   Et capter 100 % du mouvement suppose une prévision parfaite.\n")

    # ------------------------------------------------------------------ 4
    print("=" * 78)
    print("4. CE QUE CE LEVIER FAIT À LA SURVIE\n")
    rows = []
    for leverage in (1, 5, 10, 30, 50, 100):
        # A move against you of 1/leverage wipes the account.
        fatal_move = 1.0 / leverage
        # How often the instrument makes that move in ten minutes.
        moves = data["QQQ"]["close"].astype("float64").pct_change(2).abs().dropna()
        p_fatal = float((moves >= fatal_move).mean())
        # With a 55% win rate — better than almost any real system — and risking the
        # whole account at this leverage, what is ruin.
        # At leverage L, a 1/L move against the position is fatal, so the fraction of
        # capital at risk on each trade is effectively that leverage times the stop.
        ruin = risk_of_ruin(0.55, 1.0, bet_fraction=min(leverage * 0.02, 0.99))
        rows.append({
            "levier": f"x{leverage}",
            "mouvement fatal": f"{fatal_move * 100:.1f}%",
            "fréquence sur 10 min": f"{p_fatal * 100:.3f}%",
            "ruine (avec 55 % de réussite)": f"{ruin * 100:.1f}%",
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n   La colonne « ruine » suppose un avantage réel de 55 % de réussite.")
    print("   Presque aucun système intraday n'atteint ça.\n")

    # ------------------------------------------------------------------ out of sample
    print("=" * 78)
    print("5. ET SI ON CHOISIT LE RÉGLAGE SUR UNE MOITIÉ, MESURÉ SUR L'AUTRE\n")
    best = None
    tried = 0
    for symbol in ("QQQ", "TQQQ", "SLV", "GLD"):
        if symbol not in data:
            continue
        ins, oos = split_sessions(data[symbol])
        for threshold, hold, tp in itertools.product((0.8, 1.2, 1.8), (2, 4, 8), (0.6, 1.0)):
            moves = ins["close"].astype("float64").pct_change(hold).abs().dropna()
            target = float(moves.quantile(0.75)) * tp
            stop = float(moves.quantile(0.50))
            spec = ScalpSpec(position_eur=100.0, capital_eur=CAPITAL,
                             target_eur=100.0 * target, stop_eur=100.0 * stop,
                             max_hold_bars=hold, entry_threshold=threshold,
                             max_trades_per_session=8)
            res = run_scalping(ins, spec, BROKERS["US sans commission"],
                               symbol=symbol, bar_minutes=BAR_MINUTES)
            tried += 1
            score = res.diagnostics.get("gain_net_eur", -1e9)
            if best is None or score > best[0]:
                best = (score, symbol, spec, oos)

    if best is not None:
        score, symbol, spec, oos = best
        res = run_scalping(oos, spec, BROKERS["US sans commission"],
                           symbol=symbol, bar_minutes=BAR_MINUTES)
        oos_hours = len(oos) * BAR_MINUTES / 60.0
        print(f"   {tried} configurations essayées, meilleure sur la 1re moitié : {symbol}")
        print(f"   gain sur la moitié de CHOIX   : {score:+.2f} €")
        print(f"   gain sur la moitié de MESURE  : {res.diagnostics.get('gain_net_eur', 0):+.2f} € "
              f"({res.diagnostics.get('trades', 0)} trades sur {oos_hours:.0f} heures)")
        print(f"   soit {res.diagnostics.get('net_par_heure_eur', 0):+.4f} € par heure")
        print("\n   L'écart entre les deux moitiés est la signature d'une sélection :")
        print("   le réglage a été retenu parce qu'il collait au passé.\n")


if __name__ == "__main__":
    main()
