"""PPO training loop for ASTRA TOUCHDOWN (Stable-Baselines3).

Writes, per run directory:
  metadata.json  - status (running/completed/failed), config, versions, final evaluation
  metrics.jsonl  - streaming training analytics (rollout + optimisation stats, evaluation)
  model.zip      - final policy (only once training completes)
  ckpt_*.zip     - periodic checkpoints
Usage:  python -m machine_learning.training.train_touchdown_ppo --timesteps 200000 --envs 4
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone

import numpy as np

from machine_learning.training.checkpoints import CheckpointManager


def _now():
    return datetime.now(timezone.utc).isoformat()


def evaluate(model, episodes: int = 10, seed0: int = 9_000_000) -> dict:
    from machine_learning.environments.touchdown_env import TouchdownEnv
    env = TouchdownEnv(seed=0)
    rets, succ, errs, spd, fuel, lens = [], [], [], [], [], []
    for k in range(episodes):
        obs, _ = env.reset(seed=seed0 + k)
        done, R, n, info = False, 0.0, 0, {}
        while not done:
            a, _ = model.predict(obs, deterministic=True)
            obs, r, term, trunc, info = env.step(a)
            R += r; n += 1
            done = term or trunc
        rets.append(R); lens.append(n)
        succ.append(bool(info.get("is_success", False)))
        errs.append(info.get("landing_error", np.nan)); spd.append(info.get("touchdown_speed", np.nan))
        fuel.append(info.get("fuel_used", np.nan))
    return {"episodes": episodes, "mean_return": float(np.mean(rets)), "success_rate": float(np.mean(succ)),
            "mean_landing_error_m": float(np.nanmean(errs)), "mean_touchdown_speed": float(np.nanmean(spd)),
            "mean_fuel_kg": float(np.nanmean(fuel)), "mean_length": float(np.mean(lens))}


def train(timesteps: int, n_envs: int, run_id: str | None = None, seed: int = 0, eval_every: int = 50_000) -> dict:
    import stable_baselines3
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import SubprocVecEnv

    from machine_learning.environments.touchdown_env import TouchdownEnv

    mgr = CheckpointManager()
    run_id = run_id or f"touchdown_ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    d = mgr.run_dir(run_id)
    hp = dict(learning_rate=3e-4, n_steps=1024, batch_size=256, n_epochs=10, gamma=0.995, gae_lambda=0.95,
              clip_range=0.2, ent_coef=0.0, policy_kwargs={"net_arch": [128, 128], "log_std_init": -1.0})
    meta = {"status": "running", "started_at": _now(), "timesteps_target": timesteps, "n_envs": n_envs, "seed": seed,
            "hyperparameters": hp, "environment_version": "v2 (fly-away termination, potential shaping, 400-1500 m starts)", "versions": {"python": platform.python_version(), "torch": torch.__version__,
                                                "stable_baselines3": stable_baselines3.__version__,
                                                "numpy": np.__version__}}
    mgr.write_meta(run_id, meta)
    metrics_f = open(d / "metrics.jsonl", "a")

    class Analytics(BaseCallback):
        def __init__(self):
            super().__init__()
            self.ep_rew, self.ep_len, self.ep_succ = [], [], []
            self.next_eval = eval_every
            self.t0 = time.time()

        def _on_step(self) -> bool:
            for info in self.locals.get("infos", []):
                ep = info.get("episode")
                if ep:
                    self.ep_rew.append(ep["r"]); self.ep_len.append(ep["l"])
                    self.ep_succ.append(float(info.get("is_success", False)))
            return True

        def _on_rollout_end(self) -> None:
            vals = {k: float(v) for k, v in self.model.logger.name_to_value.items()}
            rec = {"t": time.time() - self.t0, "timesteps": int(self.num_timesteps),
                   "episode_reward": float(np.mean(self.ep_rew[-20:])) if self.ep_rew else None,
                   "episode_length": float(np.mean(self.ep_len[-20:])) if self.ep_len else None,
                   "success_rate": float(np.mean(self.ep_succ[-20:])) if self.ep_succ else None,
                   "episodes": len(self.ep_rew),
                   "policy_loss": vals.get("train/policy_gradient_loss"), "value_loss": vals.get("train/value_loss"),
                   "entropy": -vals["train/entropy_loss"] if "train/entropy_loss" in vals else None,
                   "approx_kl": vals.get("train/approx_kl"), "clip_fraction": vals.get("train/clip_fraction")}
            metrics_f.write(json.dumps({"type": "train", **rec}) + "\n"); metrics_f.flush()
            if self.num_timesteps >= self.next_eval:
                self.next_eval += eval_every
                self.model.save(d / f"ckpt_{self.num_timesteps}.zip")
                ev = evaluate(self.model, episodes=5)
                metrics_f.write(json.dumps({"type": "eval", "timesteps": int(self.num_timesteps), **ev}) + "\n")
                metrics_f.flush()

    try:
        vec = make_vec_env(TouchdownEnv, n_envs=n_envs, seed=seed, vec_env_cls=SubprocVecEnv if n_envs > 1 else None,
                           env_kwargs={"seed": seed})
        model = PPO("MlpPolicy", vec, seed=seed, verbose=0, device="cpu", **hp)
        model.learn(total_timesteps=timesteps, callback=Analytics())
        model.save(d / "model.zip")
        vec.close()
        final = evaluate(model, episodes=10)
        metrics_f.write(json.dumps({"type": "eval", "timesteps": int(model.num_timesteps), "final": True, **final}) + "\n")
        meta.update(status="completed", finished_at=_now(), timesteps_done=int(model.num_timesteps), final_evaluation=final)
    except Exception as e:  # noqa: BLE001 - record failure honestly
        meta.update(status="failed", finished_at=_now(), error=repr(e))
        raise
    finally:
        metrics_f.close()
        mgr.write_meta(run_id, meta)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=200_000)
    ap.add_argument("--envs", type=int, default=4)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-every", type=int, default=50_000)
    a = ap.parse_args()
    print(json.dumps(train(a.timesteps, a.envs, a.run_id, a.seed, a.eval_every), indent=2))
