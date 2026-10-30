"""Evaluate every checkpoint of one or more PPO runs on identical seeds and pick the best.

Ranking: success rate, then mean landing error, then mean touchdown speed. The winner is copied to
<run>/best_model.zip (and recorded in <run>/selection.json); the app loads best_model.zip when present.

Usage: python -m machine_learning.evaluation.select_checkpoint --runs touchdown_ppo_local [touchdown_ppo_main] --episodes 12
"""
from __future__ import annotations

import argparse
import json
import shutil
from multiprocessing import Pool
from pathlib import Path

from machine_learning.training.checkpoints import CheckpointManager


def _eval(path: str) -> dict:
    from stable_baselines3 import PPO

    from machine_learning.training.train_touchdown_ppo import evaluate
    return {"path": path, **evaluate(PPO.load(path, device="cpu"), episodes=EPISODES)}


EPISODES = 12


def main(runs: list[str], episodes: int, workers: int, include_bc: bool = False) -> dict:
    """ckpt_bc (the pure demonstration clone, before any RL) is excluded by default: the selected model
    must be PPO-trained."""
    global EPISODES
    EPISODES = episodes
    root = CheckpointManager().root
    cands = []
    for r in runs:
        d = root / r
        cands += sorted(str(p) for p in d.glob("ckpt_*.zip") if include_bc or p.name != "ckpt_bc.zip")
        cands += [str(d / "model.zip")] if (d / "model.zip").exists() else []
    with Pool(min(workers, len(cands))) as p:
        res = p.map(_eval, cands)
    res.sort(key=lambda e: (-e["success_rate"], e["mean_landing_error_m"], e["mean_touchdown_speed"]))
    best = res[0]
    for r in runs:
        d = root / r
        if Path(best["path"]).parent == d:
            shutil.copy(best["path"], d / "best_model.zip")
            (d / "selection.json").write_text(json.dumps({"best": best, "all": res}, indent=2))
    return {"best": best, "all": res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--episodes", type=int, default=12)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--include-bc", action="store_true", help="also consider the pre-RL demonstration clone")
    a = ap.parse_args()
    out = main(a.runs, a.episodes, a.workers, a.include_bc)
    for e in out["all"]:
        print(f"{'BEST ' if e is out['best'] else '     '}{Path(e['path']).parent.name}/{Path(e['path']).name:16s} success {e['success_rate']:.0%}  "
              f"error {e['mean_landing_error_m']:.1f} m  touchdown {e['mean_touchdown_speed']:.2f} m/s  fuel {e['mean_fuel_kg']:.0f} kg")
