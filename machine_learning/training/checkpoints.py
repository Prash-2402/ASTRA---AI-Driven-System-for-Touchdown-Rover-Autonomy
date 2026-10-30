"""Checkpoint manager with simple model versioning (one directory per training run)."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(os.environ.get("ASTRA_CHECKPOINT_DIR", Path(__file__).resolve().parents[1] / "checkpoints"))


class CheckpointManager:
    def __init__(self, root: Path | str = ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        d = self.root / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_meta(self, run_id: str, meta: dict) -> None:
        (self.run_dir(run_id) / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))

    def read_meta(self, run_id: str) -> dict | None:
        f = self.root / run_id / "metadata.json"
        return json.loads(f.read_text()) if f.exists() else None

    def list_runs(self, prefix: str = "") -> list[dict]:
        out = []
        for d in sorted(self.root.iterdir()) if self.root.exists() else []:
            if d.is_dir() and d.name.startswith(prefix):
                meta = self.read_meta(d.name) or {}
                meta["run_id"] = d.name
                meta["has_model"] = (d / "model.zip").exists()
                out.append(meta)
        return out

    def latest_model_path(self, prefix: str) -> Path | None:
        """Most recent run whose training COMPLETED and produced a model."""
        runs = [r for r in self.list_runs(prefix) if r.get("has_model") and r.get("status") == "completed"]
        if not runs:
            return None
        runs.sort(key=lambda r: r.get("finished_at", ""))
        return self.root / runs[-1]["run_id"] / "model.zip"
