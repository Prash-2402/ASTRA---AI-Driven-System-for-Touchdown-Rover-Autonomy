"""Gymnasium environment wrapping the ASTRA TOUCHDOWN simulator for PPO.

* The full physics (6-DOF RK4), sensors and EKF run inside the environment.
* Observations are built ONLY from the EKF estimate + mission information
  (target, reference velocity, fuel gauge) - never from ground truth.
* Action (continuous, [-1,1]^3): desired thrust acceleration (world)
      a_cmd = [3 a0, 3 a1, g + 4 a2]   m/s^2
  converted to throttle / attitude torque / lateral thrust by the shared
  allocation inner loop.
* Policy period 0.1 s (10 physics steps at 100 Hz).
* Episodes start in the powered-descent regime with randomised initial conditions and mild wind
  randomisation. Lidar diversion is not part of the policy's job: instead, in a fraction of
  episodes the target JUMPS mid-descent (as the diversion planner does in the real mission), so
  the policy learns to follow a re-planned pad.
* Training runs the mission in ``fast`` mode (no lidar scanning, no telemetry log, no prediction
  roll-outs) - physics, sensors and EKF are unchanged.
"""
from __future__ import annotations

import gymnasium as gym
import numpy as np

from autonomy.control.descent_profile import desired_velocity
from autonomy.control.lander_allocation import AllocationConfig, allocate

OBS_DIM = 14
POLICY_DT = 0.1


def build_observation(est: dict, target: np.ndarray, fuel_capacity: float) -> np.ndarray:
    p, v = est["p"], est["v"]
    rel = np.asarray(target[:2]) - p[:2]
    v_des = desired_velocity(p, target, est["agl"])
    sig = est["sigma"]
    obs = np.array([
        rel[0] / 500.0, rel[1] / 500.0, est["agl"] / 1500.0,
        v[0] / 40.0, v[1] / 40.0, v[2] / 60.0,
        (v_des[0] - v[0]) / 10.0, (v_des[1] - v[1]) / 10.0, (v_des[2] - v[2]) / 10.0,
        est["euler"][0] / 0.5, est["euler"][1] / 0.5,
        est["fuel"] / fuel_capacity,
        np.log1p(max(est["agl"], 0.0)) / 8.0,
        float(np.linalg.norm(sig[0:2])) / 20.0,
    ], dtype=np.float32)
    return np.clip(obs, -10, 10)


def action_to_accel(action: np.ndarray, g: float) -> np.ndarray:
    a = np.clip(np.asarray(action, dtype=float), -1, 1)
    return np.array([3.0 * a[0], 3.0 * a[1], g + 4.0 * a[2]])


def accel_to_action(a_cmd: np.ndarray, g: float) -> np.ndarray:
    """Inverse of action_to_accel (used to turn PID demonstrations into policy actions)."""
    return np.clip(np.array([a_cmd[0] / 3.0, a_cmd[1] / 3.0, (a_cmd[2] - g) / 4.0]), -1, 1).astype(np.float32)


def terminal_reward(outcome: str | None, td: dict, err: float) -> float:
    """Graded so that every failure still points toward a landing: a softer, more upright, closer
    crash scores better than a hard one, and timing out (hovering) is worse than any touchdown."""
    if outcome == "landed":
        return 100.0 - 1.0 * min(err, 30.0) - 5.0 * abs(td.get("vertical_speed", 0.0))
    if outcome == "crash":
        vz, vh, tilt = abs(td.get("vertical_speed", 10.0)), td.get("horizontal_speed", 5.0), td.get("tilt_deg", 30.0)
        return (-20.0 - 4.0 * min(max(vz - 1.5, 0.0), 15.0) - 6.0 * min(max(vh - 1.0, 0.0), 10.0)
                - 1.5 * min(max(tilt - 8.0, 0.0), 30.0) - 0.5 * min(err, 40.0))
    return -90.0                                                 # timeout


class TouchdownEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, seed: int = 0, randomize: bool = True, max_time: float = 140.0,
                 switch_prob: float = 0.3, wind_max: float = 6.0, fast: bool = True):
        super().__init__()
        self.observation_space = gym.spaces.Box(-10, 10, (OBS_DIM,), np.float32)
        self.action_space = gym.spaces.Box(-1, 1, (3,), np.float32)
        self.base_seed = seed
        self.randomize = randomize
        self.max_time = max_time
        self.switch_prob = switch_prob
        self.wind_max = wind_max
        self.fast = fast
        self.episode = 0
        self.mission = None
        self.alloc = AllocationConfig()
        self._switch = None

    def _make_mission(self, seed: int):
        from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
        rng = np.random.default_rng(seed)
        self._switch = None
        cfg = TouchdownConfig(seed=seed, controller="pid", enable_diversion=False)
        if self.randomize:
            alt = rng.uniform(400, 1500)
            cfg.initial_position = [rng.uniform(-300, 300), rng.uniform(-300, 300), alt]
            cfg.initial_velocity = [rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-45, -15)]
            cfg.initial_euler_deg = list(rng.uniform(-5, 5, 3))
            w = rng.uniform(0, self.wind_max); a = rng.uniform(0, 2 * np.pi)
            cfg.planet.wind = [w * np.cos(a), w * np.sin(a), 0.0]
            # target jump (simulated diversion) at a random altitude in the lower half of the descent
            if rng.random() < self.switch_prob:
                r, b = rng.uniform(20, 60), rng.uniform(0, 2 * np.pi)
                self._switch = {"agl": float(rng.uniform(120, max(150, 0.5 * alt))), "dx": r * np.cos(b), "dy": r * np.sin(b), "done": False}
        cfg.terrain.rock_density_per_km2 = 0.0      # rocks are the lidar/diversion planner's job, not the policy's
        cfg.supervisor.ignition_agl = 1e9           # start directly in powered descent
        cfg.supervisor.max_mission_time = self.max_time
        return TouchdownMission(cfg, fast=self.fast)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # every vector-env worker draws its own episode seeds from its own seeded generator
        s = int(self.np_random.integers(0, 2**31 - 1))
        self.episode += 1
        self.mission = self._make_mission(s)
        self.prev_fuel = self.mission.lander.fuel
        self.start_alt = float(self.mission.lander.pos[2])
        self.prev_phi = self._potential(self.mission.estimate())
        return build_observation(self.mission.estimate(), self.mission.target, self.mission.cfg.lander.fuel_mass), {}

    def _potential(self, est) -> float:
        """Potential for shaping (Ng et al. 1999): F = gamma*phi' - phi keeps the optimal policy unchanged."""
        v_des = desired_velocity(est["p"], self.mission.target, est["agl"])
        dist = float(np.hypot(*(est["p"][:2] - self.mission.target[:2])))
        return -0.1 * float(np.linalg.norm(v_des - est["v"])) - 0.01 * dist

    def step(self, action):
        m = self.mission
        a_cmd = action_to_accel(action, m.g)
        steps = int(round(POLICY_DT / 0.01))
        for _ in range(steps):
            est = m.estimate()
            cmd, _ = allocate(a_cmd, est["euler"], est["omega"], est["mass"], m.cfg.lander, self.alloc)
            m.controller = _Fixed(cmd)            # inject policy command into the mission control slot
            m.step()
            if m.supervisor.terminal:
                break
        est = m.estimate()
        sw = self._switch
        if sw and not sw["done"] and est["agl"] < sw["agl"] and not m.supervisor.terminal:
            sw["done"] = True
            x, y = m.target[0] + sw["dx"], m.target[1] + sw["dy"]
            m.target = np.array([x, y, m.dem.height(x, y)])
            self.prev_phi = self._potential(est)  # a re-plan is not the policy's fault: no shaping jump
        obs = build_observation(est, m.target, m.cfg.lander.fuel_mass)
        v_des = desired_velocity(est["p"], m.target, est["agl"])
        track = float(np.linalg.norm(v_des - est["v"]))
        fuel_step = self.prev_fuel - m.lander.fuel
        self.prev_fuel = m.lander.fuel
        tilt = np.radians(m.lander.tilt_deg())          # attitude stability uses true tilt only for the reward
        phi = self._potential(est)
        reward = (0.995 * phi - self.prev_phi) - 0.01 * fuel_step - 0.2 * tilt ** 2 - 0.002 * min(track, 30.0) - 0.01
        self.prev_phi = phi
        if tilt > np.radians(35):
            reward -= 1.0
        terminated, truncated = False, False
        info = {}
        # anti-exploitation: flying away / climbing is terminal with a large penalty
        dist_h = float(np.hypot(*(m.lander.pos[:2] - m.target[:2])))
        if (m.lander.pos[2] > self.start_alt + 300 or dist_h > 2000) and not m.supervisor.terminal:
            return obs, float(reward - 150.0), True, False, {"is_success": False, "landing_error": dist_h,
                                                             "touchdown_speed": np.nan, "fuel_used": m.lander.fuel_used,
                                                             "terminal_reason": "fly-away"}
        if m.supervisor.terminal:
            r = m.result or {}
            terminated = r.get("outcome") in ("landed", "crash")
            truncated = not terminated
            td = r.get("touchdown") or {}
            err = r.get("landing_error_m", 100.0)
            reward += terminal_reward(r.get("outcome"), td, err)
            info = {"is_success": r.get("outcome") == "landed", "landing_error": err,
                    "touchdown_speed": abs(td.get("vertical_speed", np.nan)) if td else np.nan,
                    "fuel_used": r.get("fuel_used_kg", np.nan), "terminal_reason": r.get("outcome")}
        return obs, float(reward), terminated, truncated, info


class _Fixed:
    """Controller stub returning a pre-computed command (used by the RL env only)."""
    name = "ppo-env"

    def __init__(self, cmd):
        self.cmd = cmd

    def compute(self, est, target, dt, params):
        return self.cmd, {}
