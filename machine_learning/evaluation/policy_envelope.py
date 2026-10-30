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
    from autonomy.control.lander_pid import LanderPIDController
    from autonomy.safety.policy_guard import GuardConfig
    from machine_learning.environments.touchdown_env import POLICY_DT, action_to_accel
    model = PPO.load(model_path, device="cpu")
    jumps = seed % 2 == 0           # inputs: with and without target jumps; disagreement: normal flight only
    env = TouchdownEnv(seed=seed, switch_prob=0.3 if jumps else 0.0)
    pid, gc = LanderPIDController(), GuardConfig()
    obs, _ = env.reset(seed=seed)
    out, done, ewma, peak, t = [obs], False, 0.0, 0.0, 0.0
    while not done:
        a, _ = model.predict(obs, deterministic=True)
        est = env.mission.estimate()
        a_pid, _ = pid.guidance(est, env.mission.target, POLICY_DT)
        ewma = (1 - gc.disagree_alpha) * ewma + gc.disagree_alpha * float(np.linalg.norm(action_to_accel(a, est["g"]) - a_pid))
        t += POLICY_DT
        if t > gc.warmup_s and est["agl"] > gc.min_agl:
            peak = max(peak, ewma)
        obs, _, term, trunc, _ = env.step(a)
        out.append(obs); done = term or trunc
    return np.array(out), (None if jumps else peak)


def build(model_path: str, episodes: int = 24, workers: int = 6) -> dict:
    with Pool(workers) as p:
        res = p.map(_episode, [(model_path, 500_000 + k) for k in range(episodes)])
    data = np.concatenate([r[0] for r in res])
    peaks = [r[1] for r in res if r[1] is not None]
    env = {"names": NAMES, "mean": data.mean(0).tolist(), "std": data.std(0).tolist(),
           # how far this policy normally strays from the PID reference in its own world
           "disagreement_max": float(np.max(peaks)), "disagreement_p90": float(np.percentile(peaks, 90)),
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
