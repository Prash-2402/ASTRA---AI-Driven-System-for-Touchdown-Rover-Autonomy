"""PPO training for ASTRA TOUCHDOWN (Stable-Baselines3), warm-started from demonstrations.

Why: a randomly initialised policy essentially never lands, so plain PPO never observes the landing
reward (previous run: 0 % success after 100 k steps). Training therefore has two stages:
  1. Demonstration warm start (behaviour cloning): the cascade-PID guidance flies episodes through the
     SAME observation/action interface as the policy; half of them with injected action noise (labels stay
     the clean PID action) so the policy also learns to recover from off-nominal states. The actor is
     regressed onto the demonstrated actions and the critic onto the demonstrated discounted returns.
  2. PPO fine-tuning on the environment reward with conservative updates (small clip range, target KL)
     so the warm start is improved, not destroyed.

Writes, per run directory:
  metadata.json  - status (running/completed/failed), config, versions, BC + final evaluation
  metrics.jsonl  - streaming analytics (bc stage, rollout + optimisation stats, evaluations)
  model.zip      - final policy (only once training completes)
  ckpt_*.zip     - periodic checkpoints
Usage:  python -m machine_learning.training.train_touchdown_ppo --timesteps 2000000 --envs 6
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from multiprocessing import get_context

import numpy as np

from machine_learning.training.checkpoints import CheckpointManager

GAMMA = 0.995


def _now():
    return datetime.now(timezone.utc).isoformat()


def evaluate(model, episodes: int = 10, seed0: int = 9_000_000) -> dict:
    from machine_learning.environments.touchdown_env import TouchdownEnv
    env = TouchdownEnv(seed=0)
    rets, succ, errs, spd, fuel, lens, reasons = [], [], [], [], [], [], {}
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
        reasons[str(info.get("terminal_reason"))] = reasons.get(str(info.get("terminal_reason")), 0) + 1
    return {"episodes": episodes, "mean_return": float(np.mean(rets)), "success_rate": float(np.mean(succ)),
            "mean_landing_error_m": float(np.nanmean(errs)), "mean_touchdown_speed": float(np.nanmean(spd)),
            "mean_fuel_kg": float(np.nanmean(fuel)), "mean_length": float(np.mean(lens)), "outcomes": reasons}


def _demo_episode(args) -> dict:
    """One PID-flown episode through the policy interface. Returns observations, clean PID actions, returns."""
    seed, noise = args
    from autonomy.control.lander_pid import LanderPIDController
    from machine_learning.environments.touchdown_env import POLICY_DT, TouchdownEnv, accel_to_action
    env = TouchdownEnv(seed=seed)
    pid = LanderPIDController()
    rng = np.random.default_rng(seed + 17)
    obs, _ = env.reset(seed=seed)
    O, A, R = [], [], []
    done, info = False, {}
    while not done:
        est = env.mission.estimate()
        a_cmd, _ = pid.guidance(est, env.mission.target, POLICY_DT)
        a = accel_to_action(a_cmd, est["g"])
        O.append(obs); A.append(a)
        act = np.clip(a + rng.normal(0, noise, 3), -1, 1) if noise > 0 else a
        obs, r, term, trunc, info = env.step(act)
        R.append(r)
        done = term or trunc
    G, g = np.zeros(len(R), np.float32), 0.0
    for i in range(len(R) - 1, -1, -1):
        g = R[i] + GAMMA * g
        G[i] = g
    return {"obs": np.array(O, np.float32), "act": np.array(A, np.float32), "ret": G,
            "success": bool(info.get("is_success", False))}


def collect_demonstrations(n_episodes: int, workers: int, seed: int) -> dict:
    jobs = [(seed * 1_000_003 + 7919 * k, 0.0 if k % 2 == 0 else 0.25) for k in range(n_episodes)]
    if workers > 1:
        with get_context("spawn").Pool(workers) as pool:
            eps = pool.map(_demo_episode, jobs)
    else:
        eps = [_demo_episode(j) for j in jobs]
    return {"obs": np.concatenate([e["obs"] for e in eps]), "act": np.concatenate([e["act"] for e in eps]),
            "ret": np.concatenate([e["ret"] for e in eps]), "episodes": n_episodes,
            "demo_success_rate": float(np.mean([e["success"] for e in eps]))}


def behaviour_clone(model, demos: dict, epochs: int = 40, batch: int = 1024, lr: float = 1e-3) -> dict:
    import torch
    pol = model.policy
    obs = torch.as_tensor(demos["obs"]); act = torch.as_tensor(demos["act"]); ret = torch.as_tensor(demos["ret"])
    opt = torch.optim.Adam(pol.parameters(), lr=lr)
    n = len(obs)
    for ep in range(epochs):
        perm = torch.randperm(n)
        lp = lv = 0.0
        for i in range(0, n, batch):
            idx = perm[i:i + batch]
            dist = pol.get_distribution(obs[idx])
            loss_pi = ((dist.distribution.mean - act[idx]) ** 2).mean()
            loss_v = ((pol.predict_values(obs[idx]).squeeze(-1) - ret[idx]) ** 2).mean()
            loss = loss_pi + 1e-3 * loss_v
            opt.zero_grad(); loss.backward(); opt.step()
            lp += loss_pi.item() * len(idx); lv += loss_v.item() * len(idx)
    with torch.no_grad():
        pol.log_std.fill_(-1.6)                      # explore ~0.2 around the cloned behaviour
    return {"bc_epochs": epochs, "bc_samples": n, "bc_action_mse": lp / n, "bc_value_mse": lv / n}


def train(timesteps: int, n_envs: int, run_id: str | None = None, seed: int = 0, eval_every: int = 50_000,
          bc_episodes: int | None = None) -> dict:
    import stable_baselines3
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import SubprocVecEnv

    from machine_learning.environments.touchdown_env import TouchdownEnv

    torch.set_num_threads(max(1, min(4, n_envs)))
    mgr = CheckpointManager()
    run_id = run_id or f"touchdown_ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    d = mgr.run_dir(run_id)
    bc_episodes = bc_episodes if bc_episodes is not None else int(np.clip(timesteps // 4000, 4, 150))
    hp = dict(learning_rate=1e-4, n_steps=1024, batch_size=512, n_epochs=10, gamma=GAMMA, gae_lambda=0.95,
              clip_range=0.1, ent_coef=0.0, target_kl=0.03, policy_kwargs={"net_arch": [128, 128], "log_std_init": -1.6})
    meta = {"status": "running", "started_at": _now(), "timesteps_target": timesteps, "n_envs": n_envs, "seed": seed,
            "method": "PPO warm-started by behaviour cloning of cascade-PID demonstrations, then PPO fine-tuning",
            "bc_episodes": bc_episodes, "hyperparameters": hp,
            "environment_version": "v3 (per-worker episode seeds, graded terminal reward, target jumps, wind randomisation, fast mode)",
            "versions": {"python": platform.python_version(), "torch": torch.__version__,
                         "stable_baselines3": stable_baselines3.__version__, "numpy": np.__version__}}
    mgr.write_meta(run_id, meta)
    metrics_f = open(d / "metrics.jsonl", "a")

    def log(rec):
        metrics_f.write(json.dumps(rec) + "\n"); metrics_f.flush()

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
            el = time.time() - self.t0
            log({"type": "train", "t": el, "timesteps": int(self.num_timesteps),
                 "steps_per_s": round(self.num_timesteps / max(el, 1e-6), 1),
                 "episode_reward": float(np.mean(self.ep_rew[-30:])) if self.ep_rew else None,
                 "episode_length": float(np.mean(self.ep_len[-30:])) if self.ep_len else None,
                 "success_rate": float(np.mean(self.ep_succ[-30:])) if self.ep_succ else None,
                 "episodes": len(self.ep_rew),
                 "policy_loss": vals.get("train/policy_gradient_loss"), "value_loss": vals.get("train/value_loss"),
                 "entropy": -vals["train/entropy_loss"] if "train/entropy_loss" in vals else None,
                 "approx_kl": vals.get("train/approx_kl"), "clip_fraction": vals.get("train/clip_fraction")})
            if self.num_timesteps >= self.next_eval:
                self.next_eval += eval_every
                self.model.save(d / f"ckpt_{self.num_timesteps}.zip")
                log({"type": "eval", "timesteps": int(self.num_timesteps), **evaluate(self.model, episodes=6)})

    try:
        vec = make_vec_env(TouchdownEnv, n_envs=n_envs, seed=seed, vec_env_cls=SubprocVecEnv if n_envs > 1 else None)
        model = PPO("MlpPolicy", vec, seed=seed, verbose=0, device="cpu", **hp)
        # ---- stage 1: demonstration warm start ----
        t0 = time.time()
        demos = collect_demonstrations(bc_episodes, n_envs, seed)
        bc = behaviour_clone(model, demos)
        bc_eval = evaluate(model, episodes=6)
        model.save(d / "ckpt_bc.zip")
        bc_rec = {"type": "bc", "seconds": round(time.time() - t0, 1), "demo_success_rate": demos["demo_success_rate"], **bc, **bc_eval}
        log(bc_rec)
        meta["bc"] = bc_rec; mgr.write_meta(run_id, meta)
        print(f"[bc] demos {bc_episodes} eps ({demos['demo_success_rate']:.0%} landed), cloned policy success "
              f"{bc_eval['success_rate']:.0%}, {bc_rec['seconds']:.0f} s", flush=True)
        # ---- stage 2: PPO fine-tuning ----
        model.learn(total_timesteps=timesteps, callback=Analytics())
        model.save(d / "model.zip")
        vec.close()
        final = evaluate(model, episodes=12)
        log({"type": "eval", "timesteps": int(model.num_timesteps), "final": True, **final})
        meta.update(status="completed", finished_at=_now(), timesteps_done=int(model.num_timesteps), final_evaluation=final)
        print(f"[done] success {final['success_rate']:.0%}, landing error {final['mean_landing_error_m']:.1f} m", flush=True)
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
    ap.add_argument("--envs", type=int, default=6)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-every", type=int, default=250_000)
    ap.add_argument("--bc-episodes", type=int, default=None)
    a = ap.parse_args()
    print(json.dumps(train(a.timesteps, a.envs, a.run_id, a.seed, a.eval_every, a.bc_episodes), indent=2, default=str))
