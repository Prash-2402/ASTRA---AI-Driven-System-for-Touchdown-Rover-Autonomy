"""Telemetry storage strategy.

Full-rate frames (10 Hz) are written once per run to a gzip-compressed JSON
Lines archive under ``data/telemetry/<run_uid>.jsonl.gz``. The database keeps
a pointer (telemetry_archives) plus 1 Hz decimated rows for fast querying.
Archives stream back for CSV/JSON export without loading the DB.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path

from backend.core.config import settings


def write_archive(run_uid: str, frames: list[dict]) -> tuple[Path, int]:
    path = settings.telemetry_dir / f"{run_uid}.jsonl.gz"
    with gzip.open(path, "wt") as f:
        for fr in frames:
            f.write(json.dumps(fr, separators=(",", ":")) + "\n")
    return path, path.stat().st_size


def read_archive(run_uid: str, every: int = 1, path: str | Path | None = None) -> list[dict]:
    """`path`: the location recorded in the database when the run was stored (archives written by another
    checkout/data dir stay readable); falls back to this installation's telemetry directory."""
    path = Path(path) if path and Path(path).exists() else settings.telemetry_dir / f"{run_uid}.jsonl.gz"
    if not path.exists():
        return []
    out = []
    with gzip.open(path, "rt") as f:
        for i, line in enumerate(f):
            if i % every == 0:
                out.append(json.loads(line))
    return out


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        elif isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v) and len(v) <= 16:
            for i, x in enumerate(v):
                out[f"{key}[{i}]"] = x
        elif isinstance(v, (int, float, str, bool)) or v is None:
            out[key] = v
    return out


def frames_to_csv(frames: list[dict]) -> str:
    rows = [_flatten(f) for f in frames]
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
