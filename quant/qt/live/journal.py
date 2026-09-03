"""The paper-trading record, kept somewhere it survives.

The daily orchestrator already records everything it does — into a SQLite file under
the data lake, which is `.gitignore`d and lives on whatever machine ran the cycle. That
is the right place for a run on one machine. It is the wrong place for a three-month
paper trial, because the moment the container is recycled the record is gone and the
trial silently restarts from its seed value with a flat curve and a zero drawdown.

So this module keeps a second copy: one CSV row per cycle, committed to the repository.
Plain text, one line a day, diffable — a record whose history is as auditable as the
code that produced it, and which cannot be quietly rewritten.

## Why a mirror and not a move

`mark_to_market` needs the previous cycle's weights and the equity curve, and it reads
them from the `Store`. Rather than reimplement that logic against a CSV — two
implementations of the same arithmetic is how they drift apart — `restore` replays the
journal into a fresh `Store` at the start of a run. The orchestrator is untouched and
does not know the journal exists.

The direction matters: the Store is rebuilt from the journal, never the reverse. The
journal is the record; the database is a working copy.

## What a row has to contain

Enough to rebuild the state and to audit the decision afterwards:

* the equity and drawdown, which is the result;
* the weights actually held, which is what produced it — without them `mark_to_market`
  cannot revalue anything and the curve goes flat again, which is the exact failure this
  file exists to prevent;
* the status and reason, so a halted or stale day is distinguishable from a quiet one.
  A day the feed was dead and a day nothing moved look identical in an equity column.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from qt.data import schemas

# Committed, deliberately outside the gitignored data lake.
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "journal" / "paper_trading.csv"

COLUMNS = [
    "date", "ts_ms", "status", "reason", "equity", "drawdown", "risk_scale",
    "gross", "data_age_days", "weights",
]


@dataclass
class Journal:
    """A committed, append-only record of a paper run."""

    path: Path = DEFAULT_PATH
    run_id: str = "daily"

    # ------------------------------------------------------------------ read
    def frame(self) -> pd.DataFrame:
        """The record, oldest first. An absent or empty file is an empty frame, not an error."""
        if not self.path.exists():
            return pd.DataFrame(columns=COLUMNS)
        try:
            df = pd.read_csv(self.path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=COLUMNS)
        if df.empty:
            return pd.DataFrame(columns=COLUMNS)
        return df.sort_values("ts_ms").reset_index(drop=True)

    def last(self) -> dict | None:
        df = self.frame()
        return None if df.empty else df.iloc[-1].to_dict()

    # ----------------------------------------------------------------- write
    def append(self, result, *, weights: dict[str, float] | None = None) -> None:
        """Add one cycle. Re-running the same day replaces that day rather than duplicating it.

        A cycle is re-run often — a failed refresh, a manual check, a retry after a
        network error. Appending blindly would put several rows on one date, and every
        return computed from the file afterwards would count that day more than once.
        """
        ts_ms = int(schemas.epoch_ms(pd.DatetimeIndex([result.ts])).iloc[0])
        held = weights if weights is not None else result.weights
        row = {
            "date": pd.Timestamp(result.ts).strftime("%Y-%m-%d"),
            "ts_ms": ts_ms,
            "status": result.status,
            "reason": (result.reason or "").replace("\n", " ")[:300],
            "equity": round(float(result.equity), 4),
            "drawdown": round(float(result.drawdown), 6),
            "risk_scale": round(float(result.risk_scale), 4),
            "gross": round(float(result.gross), 5),
            "data_age_days": (round(float(result.data_age_days), 3)
                              if np.isfinite(result.data_age_days) else ""),
            "weights": json.dumps({k: round(float(v), 6) for k, v in held.items()
                                   if abs(float(v)) > 1e-6}, sort_keys=True),
        }

        df = self.frame()
        if not df.empty:
            df = df[df["date"] != row["date"]]
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.sort_values("ts_ms")[COLUMNS].to_csv(self.path, index=False)

    # --------------------------------------------------------------- restore
    def restore(self, store) -> int:
        """Replay the journal into a Store so the orchestrator sees its own history.

        Called before a cycle on a machine that has never run one. Returns the number of
        rows replayed, so a caller can tell "a fresh start" from "restored a trial in
        progress" — a distinction worth surfacing, because the first is expected on day
        one and alarming on day forty.
        """
        df = self.frame()
        if df.empty:
            return 0

        for _, row in df.iterrows():
            ts = int(row["ts_ms"])
            try:
                weights = json.loads(row["weights"]) if isinstance(row["weights"], str) else {}
            except json.JSONDecodeError:
                weights = {}

            for symbol, weight in weights.items():
                store.record_decision(
                    self.run_id, ts, symbol,
                    signal=float(weight), target_weight=float(weight),
                    allowed_weight=float(weight),
                    risk_scale=float(row["risk_scale"]),
                    risk_reason=str(row["reason"])[:300],
                    equity=float(row["equity"]),
                )
            store.record_equity(
                self.run_id, ts, float(row["equity"]), float(row["equity"]),
                float(row["gross"]), float(row["drawdown"]),
                str(row["status"]) in ("halted", "stale", "error"),
            )
        return len(df)


# ------------------------------------------------------------------ analysis
def performance(journal: Journal | None = None, *, periods_per_year: float = 252) -> dict:
    """What the paper trial has actually done so far.

    Returns NaNs rather than guesses while the record is too short to say anything. Two
    weeks of paper trading has no measurable Sharpe, and reporting one is how a trial
    gets abandoned or trusted for the wrong reason.
    """
    df = (journal or Journal()).frame()
    if len(df) < 2:
        return {"jours": len(df), "note": "trop court pour mesurer quoi que ce soit"}

    equity = pd.Series(df["equity"].astype("float64").to_numpy(),
                       index=pd.to_datetime(df["date"]))
    rets = equity.pct_change().dropna()
    days = len(rets)
    total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    sd = float(rets.std(ddof=1)) if days > 1 else np.nan

    out = {
        "jours": int(len(df)),
        "du": str(df["date"].iloc[0]),
        "au": str(df["date"].iloc[-1]),
        "équité": float(equity.iloc[-1]),
        "rendement_total": total,
        "pire_perte": float((equity / equity.cummax() - 1.0).min()),
        "jours_halted": int((df["status"] != "ok").sum()),
    }
    # Annualising two weeks of returns produces a number with no information in it, and
    # it is always the number people quote. Withheld until the sample can carry it.
    if days >= 60 and np.isfinite(sd) and sd > 0:
        out["rendement_annualisé"] = float((1 + total) ** (periods_per_year / days) - 1)
        out["volatilité_annualisée"] = float(sd * np.sqrt(periods_per_year))
        out["sharpe"] = out["rendement_annualisé"] / out["volatilité_annualisée"]
    else:
        out["note"] = (f"{days} jours de rendement — il en faut 60 avant qu'un Sharpe "
                       "ou un rendement annualisé veuille dire quelque chose")
    return out
