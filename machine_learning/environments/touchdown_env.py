import gymnasium as gym
from gymnasium import spaces
import numpy as np
from shared.schemas.touchdown import TouchdownConfig
from simulation.touchdown.environment import MarsEnvironment
from simulation.touchdown.physics import Lander6DoFPhysics, quaternion_to_euler

class LanderEDLEnv(gym.Env):
    """
    Gymnasium-compatible Reinforcement Learning Environment for Planetary Touchdown:
    - Actions (Continuous, 4-dim): [throttle (0..1), torque_x (-1..1), torque_y (-1..1), torque_z (-1..1)]
    - Observations (Continuous, 12-dim):
      [norm_x, norm_y, norm_z, norm_vx, norm_vy, norm_vz, roll, pitch, yaw, wx, wy, wz, fuel_fraction]
    - Realistic Mars dynamics with RK4 numerical integration
    - Physics-grounded reward penalizing kinetic energy at impact, tilt, fuel expenditure, and rewarding soft touchdown at target.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, config: TouchdownConfig = None):
        super().__init__()
        self.config = config or TouchdownConfig()
        self.env_model = MarsEnvironment(self.config.env)

        # Action Space: [throttle, tau_x_norm, tau_y_norm, tau_z_norm]
        self.action_space = spaces.Box(
            low=np.array([0.0, -1.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32
        )

        # Observation Space: 13 normalized physical features
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(13,),
            dtype=np.float32
        )

        self.physics = None
        self.dt = self.config.dt
        self.max_steps = 2500
        self.current_step = 0
        self.target = np.array(self.config.initial.target_site, dtype=np.float64)

    def _get_obs(self) -> np.ndarray:
        p = self.physics.pos - self.target
        v = self.physics.vel
        euler = quaternion_to_euler(self.physics.quat)
        omega = self.physics.omega
        fuel_frac = self.physics.fuel_mass / max(1.0, self.config.lander.fuel_mass)

        # Normalization scale factors
        obs = np.array([
            p[0] / 500.0,
            p[1] / 500.0,
            p[2] / 2000.0,
            v[0] / 50.0,
            v[1] / 50.0,
            v[2] / 50.0,
            euler[0],
            euler[1],
            euler[2],
            omega[0] / 2.0,
            omega[1] / 2.0,
            omega[2] / 2.0,
            fuel_frac
        ], dtype=np.float32)
        return np.clip(obs, -10.0, 10.0)

    def reset(self, seed: int = None, options: dict = None):
        super().reset(seed=seed)
        if seed is not None:
            self.env_model = MarsEnvironment(self.config.env)

        self.physics = Lander6DoFPhysics(
            self.config.lander,
            self.env_model,
            self.config.initial
        )
        self.current_step = 0
        obs = self._get_obs()
        return obs, {"fuel_kg": self.physics.fuel_mass}

    def step(self, action: np.ndarray):
        self.current_step += 1
        throttle_cmd = float(np.clip(action[0], 0.0, 1.0))
        rcs_torques = action[1:4].astype(np.float64) * (self.config.lander.rcs_thrust * 0.8)

        _, info = self.physics.step(throttle_cmd, rcs_torques, self.dt)

        obs = self._get_obs()
        pos = self.physics.pos
        vel = self.physics.vel
        euler = quaternion_to_euler(self.physics.quat)
        tilt = np.linalg.norm(euler[0:2])
        dist_target = np.linalg.norm(pos[0:2] - self.target[0:2])
        v_speed = np.linalg.norm(vel)

        # Reward shaping
        # 1. Negative reward proportional to distance and tilt
        reward = -0.002 * dist_target - 0.01 * (v_speed**2) - 0.05 * tilt - 0.005 * throttle_cmd

        terminated = False
        truncated = False

        if self.physics.is_touchdown:
            terminated = True
            touchdown_v = self.physics.touchdown_velocity
            touchdown_tilt = self.physics.touchdown_attitude_deg

            # Success criterion: touchdown velocity <= 2.5 m/s, tilt <= 12 deg, dist <= 15m
            if touchdown_v <= 2.5 and touchdown_tilt <= 12.0 and dist_target <= 15.0:
                reward += 200.0 - 5.0 * dist_target - 10.0 * touchdown_v
                info["success"] = True
            else:
                reward -= 100.0 + 10.0 * touchdown_v + 5.0 * touchdown_tilt
                info["success"] = False
        elif self.current_step >= self.max_steps:
            truncated = True
            info["success"] = False
        elif self.physics.pos[2] > 3500.0 or dist_target > 2500.0:
            terminated = True
            reward -= 150.0
            info["success"] = False

        return obs, float(reward), terminated, truncated, info
