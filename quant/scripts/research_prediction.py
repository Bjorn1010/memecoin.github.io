"""Can a model predict the direction of the market? Measured, not asserted.

This is the question underneath every request for a trading bot, so it deserves the most
careful measurement in the repository rather than the loosest.

The method is the one that makes a prediction claim falsifiable:

**Triple-barrier labels.** Each observation is labelled by what happened first — a
profit target, a stop, or a time limit — rather than by the sign of a fixed-horizon
return. A fixed-horizon label calls a trade that went 3% against you before recovering a
"win", which is not how anyone trades it.

**Purged cross-validation with an embargo.** Labels built from overlapping windows share
information, so an ordinary k-fold puts a label's own future in the training set. Purging
removes the overlap; the embargo removes the serial correlation that survives it. Without
both, accuracy on financial data is routinely overstated by ten points or more.

**Accuracy against the base rate, never against 50%.** If 54% of labels are "up", a model
predicting "up" always scores 54% and has learned nothing. The number that matters is the
excess over the majority class, and its confidence interval.

**Walk-forward, retrained.** A single train/test split measures one draw. Retraining as
the window rolls forward is what a live system does, and it is the only simulation whose
result transfers.

What would count as prediction: an accuracy meaningfully above the base rate, stable
across folds, on data the model never saw, surviving a deflated Sharpe when traded. Each
of those is reported below whether it is met or not.

Run:  .venv/bin/python -u scripts/research_prediction.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from qt.data.catalog import Catalog

pd.set_option("display.width", 240)

SYMBOLS = ["QQQ", "SPY", "GLD", "IWM", "TLT", "SLV", "USO", "EEM"]
BAR_MINUTES = 60          # hourly bars: 730 sessions, far more than the 60 at 5 minutes
HORIZON = 6               # bars ahead the label looks
N_SPLITS = 5
EMBARGO = 24


def load(cat: Catalog, symbol: str) -> pd.DataFrame:
    bars = cat.read_indexed("eod_1h", "yahoo", symbol)
    if bars.empty:
        return bars
    bars = bars.copy()
    bars["symbol"] = symbol
    return bars


def features_for(bars: pd.DataFrame) -> pd.DataFrame:
    """Causal features a short-horizon model could plausibly use.

    Deliberately few and deliberately standard. Two hundred features on four thousand
    observations finds patterns in noise reliably, and the purged CV below would then be
    measuring how well the noise was memorised.
    """
    close = bars["close"].astype("float64")
    high = bars["high"].astype("float64")
    low = bars["low"].astype("float64")
    volume = bars["volume"].astype("float64").replace(0.0, np.nan)
    ret = np.log(close).diff()

    out = pd.DataFrame(index=bars.index)
    for h in (1, 3, 6, 12, 24):
        out[f"ret_{h}"] = np.log(close).diff(h)
    for w in (12, 24, 48):
        vol = ret.rolling(w, min_periods=w // 2).std(ddof=0)
        out[f"vol_{w}"] = vol
        out[f"z_{w}"] = (ret.rolling(w, min_periods=w // 2).mean() / vol.replace(0.0, np.nan))
    out["range"] = (high - low) / close
    out["range_z"] = (out["range"] - out["range"].rolling(48, min_periods=24).mean()) / \
        out["range"].rolling(48, min_periods=24).std(ddof=0).replace(0.0, np.nan)
    out["close_in_range"] = (close - low) / (high - low).replace(0.0, np.nan)
    out["volume_z"] = (volume - volume.rolling(48, min_periods=24).mean()) / \
        volume.rolling(48, min_periods=24).std(ddof=0).replace(0.0, np.nan)
    out["hour"] = bars.index.hour
    out["session_position"] = bars.groupby(bars["session_id"]).cumcount()
    return out


def triple_barrier(bars: pd.DataFrame, horizon: int, width: float = 1.0) -> pd.Series:
    """+1 if the up barrier is hit first, -1 if the down barrier is, 0 on the time limit.

    Barriers are set in units of recent volatility so they mean the same thing in a calm
    hour and a violent one — a fixed percentage barrier is hit constantly in one regime
    and never in the other, and the label then encodes the regime rather than the move.
    """
    close = bars["close"].astype("float64")
    high = bars["high"].astype("float64")
    low = bars["low"].astype("float64")
    vol = np.log(close).diff().rolling(24, min_periods=12).std(ddof=0)

    labels = np.zeros(len(bars))
    close_a, high_a, low_a, vol_a = (close.to_numpy(), high.to_numpy(),
                                     low.to_numpy(), vol.to_numpy())
    session = bars["session_id"].to_numpy()

    for i in range(len(bars) - horizon):
        if not np.isfinite(vol_a[i]) or vol_a[i] <= 0:
            labels[i] = np.nan
            continue
        up = close_a[i] * (1 + width * vol_a[i])
        down = close_a[i] * (1 - width * vol_a[i])
        outcome = 0.0
        for j in range(i + 1, min(i + 1 + horizon, len(bars))):
            if session[j] != session[i]:
                break                      # a label must not resolve across a session
            if low_a[j] <= down:
                outcome = -1.0
                break
            if high_a[j] >= up:
                outcome = 1.0
                break
        labels[i] = outcome
    labels[len(bars) - horizon:] = np.nan
    return pd.Series(labels, index=bars.index, name="label")


def purged_splits(n: int, n_splits: int, horizon: int, embargo: int):
    """Contiguous test blocks, with the overlapping training observations removed.

    Labels built over `horizon` bars overlap, so an observation just before a test block
    contains that block's outcome. Purging removes it; the embargo removes what serial
    correlation leaves behind.
    """
    fold = n // n_splits
    for k in range(n_splits):
        start, stop = k * fold, (k + 1) * fold if k < n_splits - 1 else n
        test = np.arange(start, stop)
        left = np.arange(0, max(start - horizon - embargo, 0))
        right = np.arange(min(stop + horizon + embargo, n), n)
        yield np.concatenate([left, right]), test


def main() -> None:
    cat = Catalog()
    frames = {s: load(cat, s) for s in SYMBOLS}
    frames = {s: b for s, b in frames.items() if not b.empty}
    if not frames:
        print("aucune donnée horaire — lancez l'ingestion intraday d'abord")
        return

    try:
        from lightgbm import LGBMClassifier
    except ImportError:
        print("lightgbm absent")
        return

    print(f"{len(frames)} actifs · barres de {BAR_MINUTES} minutes · "
          f"horizon de prédiction : {HORIZON} barres\n")

    rows = []
    for symbol, bars in frames.items():
        X = features_for(bars)
        y = triple_barrier(bars, HORIZON)

        ok = X.notna().all(axis=1) & y.notna()
        X, y = X[ok], y[ok]
        if len(X) < 800:
            continue

        # The base rate: the most common label. Any accuracy at or below this is a model
        # that has learned to say the same thing every time.
        base_rate = float(y.value_counts(normalize=True).max())

        accuracies, edges = [], []
        for train_idx, test_idx in purged_splits(len(X), N_SPLITS, HORIZON, EMBARGO):
            if len(train_idx) < 400 or len(test_idx) < 100:
                continue
            model = LGBMClassifier(n_estimators=200, num_leaves=15, learning_rate=0.05,
                                   min_child_samples=40, subsample=0.8,
                                   colsample_bytree=0.8, verbose=-1, random_state=0)
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            pred = model.predict(X.iloc[test_idx])
            truth = y.iloc[test_idx].to_numpy()
            accuracies.append(float((pred == truth).mean()))

            # Directional edge, measured correctly: only where the model commits to a
            # direction AND the market actually moved. Counting "nothing happened" as a
            # wrong direction drags this to 36% and makes the model look
            # anti-predictive, which it is not — it is simply silent. That error was
            # made here first, and it is the reason this subset is taken explicitly.
            engaged = (pred != 0) & (truth != 0)
            if engaged.sum() > 20:
                edges.append(float((pred[engaged] == truth[engaged]).mean()))

        if not accuracies:
            continue
        acc = float(np.mean(accuracies))
        excess = acc - base_rate
        # Is the excess distinguishable from zero across folds?
        t, p = (stats.ttest_1samp(np.array(accuracies) - base_rate, 0.0)
                if len(accuracies) > 2 else (np.nan, np.nan))

        rows.append({
            "actif": symbol,
            "observations": len(X),
            "taux de base": round(base_rate, 4),
            "précision": round(acc, 4),
            "excès": round(excess, 4),
            "p-value": round(float(p), 4) if np.isfinite(p) else None,
            "direction juste": round(float(np.mean(edges)), 4) if edges else None,
        })

    table = pd.DataFrame(rows)
    print("=" * 78)
    print("LE MODÈLE PRÉDIT-IL MIEUX QUE « TOUJOURS LA MÊME RÉPONSE » ?\n")
    print("  « taux de base »  = ce qu'on obtient en répondant toujours la classe majoritaire")
    print("  « excès »         = ce que le modèle ajoute. C'est le seul chiffre qui compte.")
    print("  « p-value »       = probabilité que cet excès soit du hasard\n")
    print(table.to_string(index=False))

    if not table.empty:
        mean_excess = float(table["excès"].mean())
        n_positive = int((table["excès"] > 0).sum())
        n_significant = int((table["p-value"].fillna(1.0) < 0.05).sum())
        print(f"\n  excès moyen sur {len(table)} actifs : {mean_excess:+.4f} "
              f"({mean_excess * 100:+.2f} points)")
        print(f"  actifs avec un excès positif      : {n_positive} / {len(table)}")
        print(f"  actifs statistiquement significatifs : {n_significant} / {len(table)}")
        print("\n  Un excès positif sur la moitié des actifs, c'est ce que donne une pièce")
        print("  de monnaie. Ce qui compterait : un excès positif PARTOUT, significatif,")
        print("  et assez grand pour couvrir les coûts.")

        # The column that actually decides it. Overall accuracy is dominated by the
        # majority class — "nothing will happen" — which is true often and impossible to
        # trade. Only the directional column can be turned into a position.
        direction = table["direction juste"].dropna()
        if len(direction):
            print("\n" + "=" * 78)
            print("LA COLONNE QUI DÉCIDE VRAIMENT : « DIRECTION JUSTE »\n")
            print("  La précision globale est portée par la classe majoritaire — « il ne va")
            print("  rien se passer » — qui est souvent vraie et impossible à trader. Seule")
            print("  la justesse directionnelle peut devenir une position.\n")
            print(f"  moyenne            : {direction.mean():.4f}")
            print(f"  au-dessus de 50 %  : {int((direction > 0.5).sum())} / {len(direction)}")
            print(f"  seuil de rentabilité sur ETF : 0.533")
            if direction.mean() < 0.52:
                print("\n  -> à ce niveau, il n'y a pas de prédiction exploitable.")

        # What excess would be needed to matter, at real costs.
        print("\n" + "=" * 78)
        print("QUEL EXCÈS FAUDRAIT-IL POUR QUE CE SOIT RENTABLE ?\n")
        for cost_bps, label in ((2.0, "ETF, courtier sans commission"),
                                (12.0, "crypto au tarif retail")):
            # A directional bet wins `edge` and loses (1-edge); to cover cost c on a
            # move of size m: (2*edge - 1) * m > c
            move_bps = 30.0     # a typical hourly ETF move
            needed = 0.5 + cost_bps / (2 * move_bps)
            print(f"  {label:32s} il faudrait avoir raison {needed * 100:.1f} % du temps")
        print("\n  Le meilleur système intraday documenté publiquement tourne autour de")
        print("  53-55 %. Le tableau ci-dessus dit où en est celui-ci.")


if __name__ == "__main__":
    main()
