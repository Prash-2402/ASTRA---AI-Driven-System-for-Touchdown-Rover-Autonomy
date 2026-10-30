"""PPO guidance controller: loads a trained Stable-Baselines3 policy checkpoint, optionally guarded."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from autonomy.control.lander_allocation import AllocationConfig, allocate
from autonomy.control.lander_pid import LanderPIDController
from autonomy.safety.policy_guard import PolicyGuard, load_envelope
from machine_learning.environments.touchdown_env import POLICY_DT, action_to_accel, build_observation
from machine_learning.training.checkpoints import CheckpointManager
from simulation.common.math3d import euler_to_rotmat


class NoTrainedPolicyError(RuntimeError):
    pass


class LanderPPOController:
    name = "ppo"

    def __init__(self, checkpoint: str | None = None, guard: str = "monitor"):
        from stable_baselines3 import PPO
        mgr = CheckpointManager()
        path = Path(checkpoint) if checkpoint else mgr.latest_model_path("touchdown_ppo")
        if path is None or not Path(path).exists():
            raise NoTrainedPolicyError("No trained PPO checkpoint exists. Train one in the RL Lab first.")
        self.path = str(path)
        self.model = PPO.load(self.path, device="cpu")
        self.alloc = AllocationConfig()
        self.hold = 0.0
        self.a_cmd = None
        self.last_action = None
        self.t = 0.0
        self.shadow = LanderPIDController()                 # physics-based reference, always running
        self.guard = PolicyGuard(load_envelope(self.path), mode=guard) if guard != "off" else None
        self.guard_event: dict | None = None
        self.in_control = "ppo"

    def compute(self, est: dict, target: np.ndarray, dt: float, params):
        self.t += dt
        self.hold -= dt
        if self.a_cmd is None or self.hold <= 1e-9:
            obs = build_observation(est, target, params.fuel_mass)
            action, _ = self.model.predict(obs, deterministic=True)
            self.last_action = np.asarray(action).tolist()
            a_ppo = action_to_accel(action, est["g"])
            a_pid, _ = self.shadow.guidance(est, target, POLICY_DT)
            if self.guard:
                # IMU specific force rotated to the world frame = the non-gravitational acceleration actually achieved
                a_meas = euler_to_rotmat(est["euler"]) @ np.asarray(est["imu_accel"], float)
                ev = self.guard.check(self.t, obs, a_ppo, a_pid, est["agl"], POLICY_DT, a_meas=a_meas)
                if ev:
                    self.guard_event = ev
                    if self.guard.mode == "fallback":
                        self.in_control = "pid"
            self.a_cmd = a_pid if self.in_control == "pid" else a_ppo
            self.hold = POLICY_DT
        cmd, info = allocate(self.a_cmd, est["euler"], est["omega"], est["mass"], params, self.alloc)
        info["ppo"] = {"action": self.last_action, "checkpoint": Path(self.path).parent.name, "in_control": self.in_control,
                       "guard": None if not self.guard else {"mode": self.guard.mode, **self.guard.last, "flag": self.guard.flag}}
        return cmd, info
