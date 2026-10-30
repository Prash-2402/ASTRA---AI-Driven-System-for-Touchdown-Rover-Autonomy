# PPO Training Guide — hand-off for the ASTRA TOUCHDOWN policy

**Audience:** an engineer or coding agent picking up reinforcement-learning work on ASTRA.
**Status at hand-off:** the PPO *infrastructure* is complete and tested; **no converged policy exists**.
Do not claim a trained model until a run reaches `status: "completed"` **and** its evaluation meets the
acceptance criteria in §7.

---

## 1. What already exists (do not rebuild)

| Piece | File | State |
|---|---|---|
| Gymnasium environment (full 6-DOF physics + sensors + EKF inside) | `machine_learning/environments/touchdown_env.py` | Working, passes SB3 `check_env` |
| Observation builder (EKF estimate only, 14 dims, normalised) | `build_observation()` in the same file | Working |
| Action mapping (desired thrust acceleration → allocation inner loop) | `action_to_accel()` | Working |
| Training loop, analytics, periodic eval, checkpoints | `machine_learning/training/train_touchdown_ppo.py` | Working |
| Checkpoint manager / model versioning | `machine_learning/training/checkpoints.py` | Working |
| Inference controller used by missions | `autonomy/control/lander_ppo.py` | Working (tested with a 1k-step model) |
| API: start training, list runs, stream metrics | `POST/GET /api/touchdown/training[/{run_id}]` | Working |
| UI: RL Lab (reward, success, losses, entropy, KL, eval table) | `frontend/src/application/pages/RLLab.tsx` | Working |
| Tests | `tests/unit/test_statistics_and_rl.py` (`test_ppo_environment_contract`, `test_ppo_trains_and_infers`) | Passing |

The mission runner only offers PPO in Mission Control when `CheckpointManager.latest_model_path("touchdown_ppo")`
finds a run whose `metadata.json` has `status == "completed"` and a `model.zip`.

## 2. History — what was tried and why it failed

| Run | Steps | Outcome | Diagnosis |
|---|---|---|---|
| `touchdown_ppo_v1` | 227 k (stopped) | 0 % success, landing error ≈ 8 km, all 450 kg fuel burnt | **Reward exploitation:** per-step tracking penalty over a 140 s episode outweighed the crash penalty; nothing terminated a fly-away, so the policy learned to thrust away from the ground. |
| `touchdown_ppo_v2` | ~100 k (stopped by owner) | 0 % success, reward plateau ≈ −176, episodes ≈ 720 steps | Env v2 added fly-away termination (−150), potential-based shaping, 400–1500 m starts, `log_std_init=-1`. Behaviour no longer exploitative but **not landing**: episodes end mostly in slow crashes or timeouts. Training throughput was ~60–110 steps/s on 2 CPU envs, so 100 k steps ≈ 15–30 min of experience is far too little. |

Both runs are kept in `machine_learning/checkpoints/` with honest metadata (`failed` / `stopped`). Do not delete them.

## 3. Problem definition (current, v2)

- **Policy rate:** 10 Hz (`POLICY_DT = 0.1`), 10 physics steps (100 Hz RK4) per action.
- **Observation (14):** target-relative x, y / 500 m; estimated AGL / 1500 m; velocity / (40, 40, 60);
  velocity error vs the shared descent profile / 10; roll, pitch / 0.5; fuel fraction; log(1+AGL)/8;
  horizontal position σ / 20. All from the EKF and fuel gauge — **never ground truth**.
- **Action (3, [-1, 1]):** `a_cmd = [3·a0, 3·a1, g + 4·a2]` m/s². The classical attitude/thrust-allocation
  loop (`autonomy/control/lander_allocation.py`) converts this into throttle, RCS torque and lateral thrust.
  This is the same interface PID and MPC use, so comparisons isolate the guidance law.
- **Episode:** starts in powered descent at 400–1500 m with randomised position (±300 m) and velocity;
  diversion disabled; ends on touchdown, crash, fly-away (climb > 300 m or > 2 km off target) or 140 s.
- **Reward (v2):** potential-based shaping `γΦ' − Φ` with `Φ = −0.1‖v_des − v‖ − 0.01·dist_h`;
  −0.01·fuel/step; −0.2·tilt²; −0.002·min(track,30); −1 per step above 35° tilt;
  terminal: landed `+100 − 2·min(err,30) − 10·|v_z|`; crash `−60 − 5·min(|v_z|,15) − min(err,30)`; timeout −60; fly-away −150.

## 4. Recommended plan (in order — stop as soon as §7 is met)

1. **Throughput first.** Profile `TouchdownEnv.step`. The EKF predict (numerical Jacobian at 100 Hz) and
   per-step allocation dominate. Options, in order of preference:
   - run the EKF predict at 50 Hz inside the env (document it), and cache `euler_to_rotmat`;
   - use `SubprocVecEnv` with `n_envs = (CPU cores − 1)`; on 8+ cores expect 400–800 steps/s;
   - budget **≥ 2–5 M environment steps**. Anything under 1 M is not a fair test of PPO here.
2. **Curriculum on start altitude.** Begin with 100–400 m starts, small lateral offsets (±50 m) and low
   horizontal velocity; widen to 400–1500 m, then 1500–2900 m (the full mission envelope) once success > 70 %.
   Implement as an env kwarg (`difficulty` 0–1) and a callback that raises it on eval success.
3. **Observation/return normalisation.** Wrap with `VecNormalize(norm_obs=True, norm_reward=True, clip_obs=10)`
   and **save the normaliser** next to `model.zip` (`vecnormalize.pkl`); load it in `LanderPPOController`.
4. **Hyper-parameters to start from:** `n_steps=2048` per env, `batch_size=512`, `n_epochs=10`, `gamma=0.995`,
   `gae_lambda=0.95`, `lr=3e-4 → linear decay`, `clip_range=0.2`, `ent_coef=0.0`, `net_arch=[256,256]`,
   `log_std_init=-1.0`. Try 3 seeds; report all of them.
5. **If still no landings after ~1 M steps:** add a dense terminal-approach term (e.g. reward −|v_z − v_des,z|
   only below 50 m AGL) *as potential shaping*, or reduce the action range of `a2` to `g ± 3`. Change one thing
   at a time and record each change in `metadata.json` (`environment_version`).
6. **Optional, clearly labelled alternative:** a *residual* policy (PPO output added to the PID guidance) usually
   learns much faster. If you build it, name it `ppo_residual`, keep plain `ppo` separate, and never present
   residual results as plain-PPO results.

## 5. Commands

```bash
source .venv/bin/activate
python -m machine_learning.training.train_touchdown_ppo --timesteps 2000000 --envs 7 --run-id touchdown_ppo_v3 --eval-every 200000
```

Or from the UI: **Reinforcement Learning Lab → Train a touchdown policy**, or `POST /api/touchdown/training`
with `{"timesteps": 2000000, "envs": 7, "seed": 0}`. Metrics stream to
`machine_learning/checkpoints/<run_id>/metrics.jsonl` and appear live in the RL Lab.

## 6. Rules (non-negotiable, from the ASTRA brief)

- Observations come from the EKF/sensors only. Ground truth may be used **only inside the reward**
  (currently: true tilt for the attitude-stability term) — document any such use.
- Never mark a run `completed` unless `model.learn` finished; failed/aborted runs keep their metadata.
- Do not tune on, or report, experiment results that the policy has not actually produced.
- Keep the env change log in `metadata.json["environment_version"]`.
- Held-out evaluation for PPO = seeds `9_000_000+` (already used by `evaluate()`), never used for training.

## 7. Acceptance criteria (definition of done for PPO)

1. A run with `status: completed` and `model.zip` (+ `vecnormalize.pkl` if used).
2. Final deterministic evaluation over **≥ 50 episodes** on held-out seeds: success rate reported with a
   95 % Wilson interval; mean landing error, |v_z| at contact, fuel used.
3. Full-mission check: run a Touchdown experiment (Experiment Lab, module *touchdown*, controllers
   `pid, mpc, ppo`, conditions `nominal, hazard, disturbance`, N ≥ 20) and report PPO next to PID/MPC —
   whatever the numbers are.
4. `pytest -m slow tests/unit/test_statistics_and_rl.py` still passes.
5. Update `docs/REINFORCEMENT_LEARNING.md` and `docs/KNOWN_LIMITATIONS.md` with the outcome.

## 8. Files your agent will touch

`machine_learning/environments/touchdown_env.py` (curriculum, normalisation hooks) ·
`machine_learning/training/train_touchdown_ppo.py` (VecNormalize, LR schedule, curriculum callback) ·
`autonomy/control/lander_ppo.py` (load the normaliser) · `docs/REINFORCEMENT_LEARNING.md`.
