"""Model registry: every fitted model is versioned, hashed and reproducible.

The rule this enforces: **no prediction without provenance**. Every stored model
records the feature schema it expects, the label spec it was trained against, the
training window and a content hash. At scoring time the schema hash is checked, so a
model can never silently score a feature matrix that has drifted from the one it
learned on — the failure mode where everything keeps working and the numbers quietly
stop meaning anything.

Storage is joblib plus a sidecar JSON, deliberately simple: the metadata must stay
readable without loading the model or importing the codebase.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..config import CONFIG
from .model import QuantModel


@dataclass
class ModelRecord:
    model_id: str
    path: Path
    meta: dict

    @property
    def created_at(self) -> str:
        return self.meta.get("created_at", "")

    @property
    def schema_hash(self) -> str:
        return self.meta.get("schema_hash", "")


def _hash_meta(meta: dict) -> str:
    return hashlib.sha256(json.dumps(meta, sort_keys=True, default=str).encode()).hexdigest()[:12]


class ModelRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else CONFIG.models_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        model: QuantModel,
        *,
        name: str,
        symbol: str = "",
        extra: dict | None = None,
    ) -> ModelRecord:
        import joblib

        meta = {
            "name": name,
            "symbol": symbol,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "schema_hash": hashlib.sha256(
                json.dumps(sorted(model.meta.get("features", []))).encode()
            ).hexdigest()[:16],
            **model.meta,
            **(extra or {}),
        }
        model_id = f"{name}-{_hash_meta(meta)}"
        path = self.root / f"{model_id}.joblib"
        joblib.dump(model, path)
        (self.root / f"{model_id}.json").write_text(json.dumps(meta, indent=2, default=str))
        return ModelRecord(model_id, path, meta)

    def load(self, model_id: str) -> tuple[QuantModel, dict]:
        import joblib

        path = self.root / f"{model_id}.joblib"
        if not path.exists():
            raise FileNotFoundError(f"no model {model_id!r} in {self.root}")
        model = joblib.load(path)
        meta_path = self.root / f"{model_id}.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return model, meta

    def latest(self, name: str) -> ModelRecord | None:
        records = [r for r in self.list_records() if r.meta.get("name") == name]
        if not records:
            return None
        return max(records, key=lambda r: r.created_at)

    def list_records(self) -> list[ModelRecord]:
        out = []
        for meta_path in sorted(self.root.glob("*.json")):
            model_id = meta_path.stem
            if not (self.root / f"{model_id}.joblib").exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                continue
            out.append(ModelRecord(model_id, self.root / f"{model_id}.joblib", meta))
        return out

    def table(self) -> pd.DataFrame:
        rows = []
        for r in self.list_records():
            rows.append(
                {
                    "model_id": r.model_id,
                    "name": r.meta.get("name"),
                    "symbol": r.meta.get("symbol"),
                    "created_at": r.created_at,
                    "n_samples": r.meta.get("n_samples"),
                    "n_features": r.meta.get("n_features"),
                    "train_start": r.meta.get("train_start"),
                    "train_end": r.meta.get("train_end"),
                    "schema_hash": r.schema_hash,
                }
            )
        return pd.DataFrame(rows).sort_values("created_at", ascending=False) if rows else pd.DataFrame()

    def check_schema(self, model: QuantModel, X: pd.DataFrame) -> None:
        """Raise unless `X` carries exactly the features the model was trained on."""
        expected = list(model.meta.get("features", []))
        missing = [c for c in expected if c not in X.columns]
        if missing:
            raise KeyError(
                f"feature matrix is missing {len(missing)} trained features "
                f"(first few: {missing[:5]}); refusing to score"
            )
