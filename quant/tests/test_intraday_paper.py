"""Le moteur de day trading en papier : ce qu'il doit garantir pour que son relevé compte.

Un relevé de trading est une preuve ou il n'est rien. Trois propriétés le décident, et
chacune se casse en silence :

* **le déterminisme** — mêmes barres, mêmes trades. Sans ça, relancer le script trois
  fois donne trois relevés et aucun n'est vérifiable ;
* **l'absence de look-ahead** — l'entrée se fait à l'ouverture de la barre *suivant* le
  signal. Entrer à la clôture de la barre du signal vaut, sur des barres de 5 minutes,
  plus que tout l'avantage recherché ;
* **la fourchette payée** — un aller-retour coûte deux demi-fourchettes, toujours.

Et une quatrième, qui n'est pas une garantie mais un diagnostic : la moyenne doit être
publiée à côté de la médiane et de l'ablation des meilleurs trades, parce qu'une moyenne
portée par cinq coups sur six cents n'est pas un avantage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qt.data import schemas
from qt.live.intraday_paper import (
    HALF_SPREAD_BPS,
    IntradaySpec,
    simulate,
    summarise,
    zscore,
)


BARS_PER_SESSION = 78          # 6h30 de marché en barres de 5 minutes


def session_index(n: int) -> pd.DatetimeIndex:
    """Un index de vraies séances : 78 barres à partir de 13h30 UTC, puis le lendemain.

    Un simple `date_range` continu traverse minuit, si bien que la date calendaire et
    l'identifiant de séance cessent de coïncider — et un test écrit sur les dates
    accuserait alors le moteur d'une faute qui est dans son jeu de données.
    """
    stamps = []
    day = pd.Timestamp("2026-06-01 13:30", tz="UTC")
    while len(stamps) < n:
        stamps.extend(pd.date_range(day, periods=BARS_PER_SESSION, freq="5min", tz="UTC"))
        day += pd.Timedelta(days=1)
    return pd.DatetimeIndex(stamps[:n])


def make_bars(closes, *, sessions=None) -> pd.DataFrame:
    n = len(closes)
    index = session_index(n)
    close = np.asarray(closes, dtype="float64")
    if sessions is None:
        sessions = np.asarray(index.normalize().astype("int64"))
    frame = pd.DataFrame({
        "ts": schemas.epoch_ms(index),
        "open": close, "high": close * 1.0005, "low": close * 0.9995,
        "close": close, "volume": 1e6,
        "session_id": np.asarray(sessions, dtype="int64"),
    })
    return schemas.to_datetime_index(
        schemas.normalise(frame, schemas.EOD, extra_columns=("session_id",)))


def wandering(n: int = 900, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 400 * np.exp(np.cumsum(rng.standard_normal(n) * 0.0008))
    return make_bars(close)


SPEC = IntradaySpec(symbols=("SPY",))


# ------------------------------------------------------------- déterminisme
def test_the_same_bars_always_give_the_same_trades():
    """La propriété qui rend le relevé vérifiable, et l'exécution idempotente.

    Le conteneur est éphémère et le script tourne à des heures irrégulières : si le
    résultat dépendait du moment de l'exécution, le journal cumulerait des trades
    contradictoires sans que rien ne le signale.
    """
    bars = wandering()
    first = simulate(bars, "SPY", SPEC)
    second = simulate(bars, "SPY", SPEC)
    assert len(first) == len(second)
    assert [t.net_bp for t in first] == [t.net_bp for t in second]
    assert [t.entry_ts for t in first] == [t.entry_ts for t in second]


def test_replaying_a_prefix_gives_a_prefix_of_the_trades():
    """Rejouer un historique plus court ne doit pas réécrire le passé."""
    bars = wandering()
    full = simulate(bars, "SPY", SPEC)
    partial = simulate(bars.iloc[:500], "SPY", SPEC)
    assert len(partial) <= len(full)
    for a, b in zip(partial, full):
        assert a.entry_ts == b.entry_ts
        assert a.net_bp == pytest.approx(b.net_bp)


# --------------------------------------------------------------- look-ahead
def test_entry_happens_on_the_bar_after_the_signal():
    """Le signal se lit sur la clôture de t ; un ordre ne peut pas s'exécuter à ce prix."""
    bars = wandering()
    trades = simulate(bars, "SPY", SPEC)
    assert trades, "le jeu de test doit produire des trades"

    z = zscore(bars["close"].astype("float64"), SPEC.window)
    for trade in trades[:20]:
        position = bars.index.get_loc(trade.entry_ts)
        # La barre PRÉCÉDENTE portait le signal, et l'entrée s'est faite à l'ouverture
        # de celle-ci — jamais à la clôture de celle qui a déclenché.
        assert abs(float(z.iloc[position - 1])) >= SPEC.threshold
        assert trade.entry_price == pytest.approx(float(bars["open"].iloc[position]))


def test_a_signal_on_the_last_bar_of_a_session_is_not_traded():
    """Entrer là ferait porter la position toute la nuit : ce n'est plus du day trading."""
    n = 160
    close = np.full(n, 100.0)
    close[BARS_PER_SESSION - 1] = 130.0     # dernière barre de la première séance
    trades = simulate(make_bars(close), "SPY",
                      IntradaySpec(symbols=("SPY",), window=12, threshold=1.5))
    for trade in trades:
        entry_session = trade.entry_ts.normalize()
        assert trade.exit_ts.normalize() == entry_session


def test_no_position_survives_the_close():
    bars = wandering()
    for trade in simulate(bars, "SPY", SPEC):
        assert trade.entry_ts.date() == trade.exit_ts.date()


# --------------------------------------------------------------------- coût
def test_every_trade_pays_two_half_spreads():
    bars = wandering()
    for trade in simulate(bars, "SPY", SPEC):
        assert trade.cost_bp == pytest.approx(2 * HALF_SPREAD_BPS["SPY"])
        assert trade.net_bp == pytest.approx(trade.gross_bp - trade.cost_bp)


def test_a_wider_spread_lowers_every_net_result():
    """Le coût est le paramètre qui décide, donc il doit mordre visiblement."""
    bars = wandering()
    tight = simulate(bars, "SPY", SPEC)          # 0,25 bp par jambe
    wide = simulate(bars, "DBC", IntradaySpec(symbols=("DBC",)))   # 4,00 bp
    assert tight and wide
    assert np.mean([t.net_bp for t in wide]) < np.mean([t.net_bp for t in tight])


# ------------------------------------------------------------------- sortie
def test_the_stop_is_checked_on_the_bar_extremes_not_its_close():
    """Une barre qui touche le stop puis revient a bel et bien sorti la position.

    Ne vérifier que la clôture laisse passer des pertes qui ont réellement eu lieu, et
    fait paraître la stratégie plus tolérante qu'elle ne l'est.
    """
    n = 120
    close = np.full(n, 100.0)
    close[30] = 108.0                       # écart : le moteur vend
    frame = make_bars(close)
    frame = frame.copy()
    frame.iloc[33, frame.columns.get_loc("high")] = 200.0   # pic contre la position

    trades = simulate(frame, "SPY", IntradaySpec(symbols=("SPY",), window=12,
                                                 threshold=1.5, stop_sigma=1.0))
    stopped = [t for t in trades if t.exit_reason == "stop"]
    assert stopped, "un pic au-delà du stop doit sortir la position"
    assert all(t.net_bp < 0 for t in stopped)


def test_an_unfinished_position_is_not_recorded():
    """Valoriser une position ouverte au dernier prix connu gonfle le relevé des
    positions qui vont bien et masque celles qui vont mal."""
    bars = wandering(n=200)
    trades = simulate(bars, "SPY", SPEC)
    last_bar = bars.index[-1]
    for trade in trades:
        assert trade.exit_ts <= last_bar


def test_the_daily_trade_cap_is_respected():
    spec = IntradaySpec(symbols=("SPY",), max_trades_per_session=2)
    bars = wandering()
    per_session: dict = {}
    for trade in simulate(bars, "SPY", spec):
        day = trade.entry_ts.date()
        per_session[day] = per_session.get(day, 0) + 1
    assert per_session, "le jeu de test doit produire des trades"
    assert max(per_session.values()) <= 2


def test_trades_never_overlap():
    """Deux positions simultanées sur le même actif fausseraient le t de Student, qui
    suppose des observations indépendantes."""
    trades = simulate(wandering(), "SPY", SPEC)
    for previous, following in zip(trades, trades[1:]):
        assert following.entry_ts > previous.exit_ts


# -------------------------------------------------------------- diagnostics
def test_the_summary_publishes_the_median_beside_the_mean():
    """Le chiffre mesuré : moyenne +2,29 bp, médiane −0,86 bp. Le trade typique perd.

    Publier la moyenne seule décrirait la stratégie comme gagnante alors qu'elle perd
    presque à chaque fois et se rattrape rarement.
    """
    stats = summarise(simulate(wandering(), "SPY", SPEC), SPEC)
    assert "net_médian_bp" in stats
    assert "sans_les_5_meilleurs_bp" in stats
    assert "sans_les_10_meilleurs_bp" in stats


def test_removing_the_best_trades_can_only_lower_the_mean():
    stats = summarise(simulate(wandering(), "SPY", SPEC), SPEC)
    if np.isfinite(stats["sans_les_10_meilleurs_bp"]):
        assert stats["sans_les_10_meilleurs_bp"] <= stats["sans_les_5_meilleurs_bp"]
        assert stats["sans_les_5_meilleurs_bp"] <= stats["net_moyen_bp"]


def test_an_empty_record_says_so_rather_than_inventing_a_number():
    assert summarise([], SPEC)["trades"] == 0


def test_a_flat_market_produces_no_trades():
    """Sans écart il n'y a rien à fader. Un moteur qui trade quand même invente."""
    assert simulate(make_bars(np.full(300, 100.0)), "SPY", SPEC) == []
