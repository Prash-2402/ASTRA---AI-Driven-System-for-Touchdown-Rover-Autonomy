# Reinforcement Learning (PPO)

**Status: infrastructure complete; no converged policy.** PPO work is paused and handed off —
see [PPO_TRAINING_GUIDE.md](PPO_TRAINING_GUIDE.md) for the full brief, history and acceptance criteria.

- Algorithm: Proximal Policy Optimization, Stable-Baselines3 2.x, PyTorch (CPU).
- Environment: `machine_learning/environments/touchdown_env.py` — full 6-DOF physics, sensors and EKF inside;
  observations from estimates only (14 dims); continuous 3-D action = desired thrust acceleration over the
  shared allocation loop; policy period 0.1 s.
- Reward: potential-based shaping on velocity-profile tracking and horizontal distance, fuel and tilt
  penalties, terminal landing/crash terms, fly-away termination (anti-exploitation).
- Training loop, analytics (episode reward/length, success, policy & value loss, entropy, approx-KL,
  clip fraction), periodic deterministic evaluation, checkpoints and versioned metadata:
  `machine_learning/training/train_touchdown_ppo.py`.
- Inference: `autonomy/control/lander_ppo.py`; the API refuses PPO (HTTP 409) until a run is `completed`.

| Run | Result |
|---|---|
| v1 (227 k steps) | failed — reward exploitation (fly-away) |
| v2 (~100 k steps) | stopped by owner — 0 % success, not converged |
