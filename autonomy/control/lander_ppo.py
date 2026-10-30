"""PPO guidance controller: loads a trained Stable-Baselines3 policy checkpoint."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from autonomy.control.lander_allocation import AllocationConfig, allocate
from machine_learning.environments.touchdown_env import POLICY_DT, action_to_accel, build_observation
from machine_learning.training.checkpoints import CheckpointManager


class NoTrainedPolicyError(RuntimeError):
    pass


class LanderPPOController:
    name = "ppo"

    def __init__(self, checkpoint: str | None = None):
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

    def compute(self, est: dict, target: np.ndarray, dt: float, params):
        self.hold -= dt
        if self.a_cmd is None or self.hold <= 1e-9:
            obs = build_observation(est, target, params.fuel_mass)
            action, _ = self.model.predict(obs, deterministic=True)
            self.last_action = np.asarray(action).tolist()
            self.a_cmd = action_to_accel(action, est["g"])
            self.hold = POLICY_DT
        cmd, info = allocate(self.a_cmd, est["euler"], est["omega"], est["mass"], params, self.alloc)
        info["ppo"] = {"action": self.last_action, "checkpoint": Path(self.path).parent.name}
        return cmd, info
