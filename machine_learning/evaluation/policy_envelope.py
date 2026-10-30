"""Measure a trained policy's training envelope: the distribution of observations it experiences in the
training environment (what "its world" looks like from the inside). Saved next to the model as
envelope.json and used by autonomy/safety/policy_guard.py.

Usage: python -m machine_learning.evaluation.policy_envelope --model machine_learning/checkpoints/<run>/model.zip
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

NAMES = ["dx_target", "dy_target", "agl", "vx", "vy", "vz", "dvx_ref", "dvy_ref", "dvz_ref", "roll", "pitch", "fuel_frac", "log_agl", "pos_sigma"]


def _episode(args):
    model_path, seed = args
    from stable_baselines3 import PPO

    from machine_learning.environments.touchdown_env import TouchdownEnv
    model = PPO.load(model_path, device="cpu")
    env = TouchdownEnv(seed=seed)
    obs, _ = env.reset(seed=seed)
    out, done = [obs], False
    while not done:
        a, _ = model.predict(obs, deterministic=True)
        obs, _, term, trunc, _ = env.step(a)
        out.append(obs); done = term or trunc
    return np.array(out)


def build(model_path: str, episodes: int = 24, workers: int = 6) -> dict:
    with Pool(workers) as p:
        data = np.concatenate(p.map(_episode, [(model_path, 500_000 + k) for k in range(episodes)]))
    env = {"names": NAMES, "mean": data.mean(0).tolist(), "std": data.std(0).tolist(),
           "p01": np.percentile(data, 1, axis=0).tolist(), "p99": np.percentile(data, 99, axis=0).tolist(),
           "samples": int(len(data)), "episodes": episodes}
    (Path(model_path).parent / "envelope.json").write_text(json.dumps(env, indent=2))
    return env


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--episodes", type=int, default=24)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    e = build(a.model, a.episodes, a.workers)
    print(f"envelope from {e['samples']} observations over {e['episodes']} episodes -> {Path(a.model).parent / 'envelope.json'}")
