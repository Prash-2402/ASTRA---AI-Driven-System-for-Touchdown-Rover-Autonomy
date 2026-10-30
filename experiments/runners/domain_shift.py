"""Learned vs classical controllers in worlds the learned one never saw (hurdle "The Sensor That Lies", hint 2).

Matched seeds: every controller flies the identical initial conditions, wind sequence and sensor noise in
each world. The PPO policy was trained in the "home" envelope (powered descent from <=1500 m, wind <=6 m/s,
nominal engine, Mars). Worlds:
  home        training-like conditions
  noisy_nav   navigation sensors 4x noisier than the EKF assumes (mismatched noise model)
  weak_engine engine delivers 82 % of commanded thrust         (unmodelled by every controller)
  moon        lunar gravity, no atmosphere                     (different planet)
  high_start  2900 m entry at 62 m/s descent (the app default) (outside the training start range)
Controllers: pid | mpc | ppo (guard: monitor only) | ppo_guarded (guard: fallback to PID).

Usage:  python -m experiments.runners.domain_shift --seeds 6 --workers 8 [--model path/to/model.zip]
Output: data/domain_shift/summary.json (+ fig_domain_shift.png)
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool

import numpy as np

from backend.core.config import settings

BASE = {"initial_position": [-200.0, 150.0, 1200.0], "initial_velocity": [12.0, -8.0, -32.0], "initial_euler_deg": [2.0, -3.0, 0.0],
        "planet": {"wind": [3.0, -1.5, 0.0]}, "terrain": {"rock_density_per_km2": 0.0}, "enable_diversion": False,
        "supervisor": {"ignition_agl": 1e9}, "sensor_health": False}
WORLDS = {
    "home": {},
    "noisy_nav": {"sensors": {"overrides": {"altimeter": {"noise_std": 2.4}, "position": {"noise_std": [16.0, 16.0, 24.0]}, "velocimeter": {"noise_std": 0.5}}}},
    "weak_engine": {"lander": {"thrust_efficiency": 0.82}},
    "moon": {"environment": "moon"},
    "high_start": {"initial_position": [-650.0, 320.0, 2900.0], "initial_velocity": [32.0, -14.0, -62.0]},
}
WORLD_LABEL = {"home": "Home (training world)", "noisy_nav": "Sensors 4x noisier than modelled", "weak_engine": "Engine at 82 % thrust",
               "moon": "Moon gravity", "high_start": "High start (2900 m)"}
CONTROLLERS = {"pid": ("pid", "off"), "mpc": ("mpc", "off"), "ppo": ("ppo", "monitor"), "ppo_guarded": ("ppo", "fallback")}


def _merge(a: dict, b: dict) -> dict:
    out = json.loads(json.dumps(a))
    for k, v in b.items():
        out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _run(job) -> dict:
    from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
    world, ctrl, seed, model = job
    kind, guard = CONTROLLERS[ctrl]
    d = _merge(_merge(BASE, WORLDS[world]), {"seed": seed, "controller": kind, "ppo_guard": guard, "ppo_checkpoint": model})
    m = TouchdownMission(TouchdownConfig.from_dict(d))
    r = m.run()
    td = r.get("touchdown") or {}
    g = r.get("ppo_guard")
    return {"world": world, "controller": ctrl, "seed": seed, "outcome": r.get("outcome"), "success": bool(r.get("success")),
            "landing_error_m": r.get("landing_error_m"), "touchdown_vz": td.get("vertical_speed"),
            "touchdown_vh": td.get("horizontal_speed"), "tilt_deg": td.get("tilt_deg"), "fuel_used_kg": r.get("fuel_used_kg"),
            "failed_checks": [k for k, v in (td.get("checks") or {}).items() if not v],
            "guard_t": g["t"] if g else None, "guard_reasons": g["reasons"] if g else None}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main(seeds: int, workers: int, model: str | None) -> dict:
    from machine_learning.training.checkpoints import CheckpointManager
    model = model or str(CheckpointManager().latest_model_path("touchdown_ppo"))
    jobs = [(w, c, 7000 + s, model) for w in WORLDS for c in CONTROLLERS for s in range(seeds)]
    with Pool(workers) as p:
        runs = p.map(_run, jobs, chunksize=1)
    table = []
    for w in WORLDS:
        for c in CONTROLLERS:
            rr = [r for r in runs if r["world"] == w and r["controller"] == c]
            k = sum(r["success"] for r in rr); lo, hi = wilson(k, len(rr))
            vz = [abs(r["touchdown_vz"]) for r in rr if r["touchdown_vz"] is not None]
            table.append({"world": w, "world_label": WORLD_LABEL[w], "controller": c, "n": len(rr), "successes": k,
                          "success_rate": k / len(rr), "ci_low": lo, "ci_high": hi,
                          "landing_error_m": float(np.nanmean([r["landing_error_m"] for r in rr])),
                          "touchdown_speed": float(np.mean(vz)) if vz else None,
                          "fuel_kg": float(np.nanmean([r["fuel_used_kg"] for r in rr])),
                          "guard_flag_rate": (float(np.mean([r["guard_t"] is not None for r in rr])) if c.startswith("ppo") else None),
                          "guard_t_mean": (float(np.mean([r["guard_t"] for r in rr if r["guard_t"] is not None]))
                                           if c.startswith("ppo") and any(r["guard_t"] is not None for r in rr) else None),
                          "failures": sorted({f for r in rr for f in r["failed_checks"]} | {r["outcome"] for r in rr if r["outcome"] not in ("landed", "crash")})})
    out = settings.data_dir / "domain_shift"; out.mkdir(parents=True, exist_ok=True)
    summary = {"model": model, "seeds": seeds, "worlds": WORLD_LABEL, "controllers": list(CONTROLLERS), "table": table, "runs": runs}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 3.8), dpi=130)
        cols = {"pid": "#2563eb", "mpc": "#16a34a", "ppo": "#ef4444", "ppo_guarded": "#f59e0b"}
        for j, c in enumerate(CONTROLLERS):
            vals = [next(t for t in table if t["world"] == w and t["controller"] == c)["success_rate"] * 100 for w in WORLDS]
            ax.bar(np.arange(len(WORLDS)) + (j - 1.5) * 0.2, vals, 0.2, color=cols[c], label={"ppo": "PPO (unguarded)", "ppo_guarded": "PPO + guard → PID"}.get(c, c.upper()))
        ax.set_xticks(range(len(WORLDS))); ax.set_xticklabels([WORLD_LABEL[w] for w in WORLDS], fontsize=8)
        ax.set_ylabel("safe landings [%]"); ax.set_ylim(0, 105); ax.legend(fontsize=8, ncol=4, loc="lower left")
        ax.set_title("Learned vs classical controllers in worlds the learned one never saw (matched seeds)")
        fig.tight_layout(); fig.savefig(out / "fig_domain_shift.png"); plt.close(fig)
    except Exception as e:  # noqa: BLE001
        print("plot skipped:", e)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    s = main(a.seeds, a.workers, a.model)
    print("model:", s["model"])
    for t in s["table"]:
        print(f"{t['world_label']:24s} {t['controller']:12s} {t['successes']}/{t['n']}  err {t['landing_error_m']:.1f} m  "
              f"vz {t['touchdown_speed'] if t['touchdown_speed'] is None else round(t['touchdown_speed'], 2)}  guard {t['guard_flag_rate']}  fails {t['failures']}")
