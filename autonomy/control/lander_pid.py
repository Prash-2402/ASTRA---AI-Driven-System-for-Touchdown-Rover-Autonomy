"""Cascade PID guidance for the lander.

  position/altitude  --(profile)-->  desired velocity
  velocity error     --(PID)----->   desired acceleration (+ gravity compensation)
  acceleration       --(allocation: attitude PD + throttle + lateral)--> actuators
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from autonomy.control.descent_profile import desired_velocity
from autonomy.control.lander_allocation import AllocationConfig, allocate
from autonomy.control.pid import PID, PIDGains


@dataclass
class LanderPIDConfig:
    vel_h: dict = field(default_factory=lambda: {"kp": 0.45, "ki": 0.04, "kd": 0.0, "out_min": -3.0, "out_max": 3.0, "i_limit": 20.0})
    vel_v: dict = field(default_factory=lambda: {"kp": 0.9, "ki": 0.08, "kd": 0.0, "out_min": -4.0, "out_max": 6.0, "i_limit": 20.0})
    profile_accel: float = 1.0
    profile_k_low: float = 0.08       # gentle final descent: time to sense and side-step late hazards
    allocation: AllocationConfig = field(default_factory=AllocationConfig)


class LanderPIDController:
    name = "pid"

    def __init__(self, cfg: LanderPIDConfig | None = None):
        self.cfg = cfg or LanderPIDConfig()
        self.pid_h = PID(PIDGains(**self.cfg.vel_h), dim=2)
        self.pid_v = PID(PIDGains(**self.cfg.vel_v), dim=1)

    def reset(self):
        self.pid_h.reset(); self.pid_v.reset()

    def guidance(self, est: dict, target: np.ndarray, dt: float) -> tuple[np.ndarray, dict]:
        v_des = desired_velocity(est["p"], target, est["agl"], a_prof=self.cfg.profile_accel,
                                 k_low=self.cfg.profile_k_low, hold=bool(est.get("hover")))
        ev = v_des - est["v"]
        a_h = self.pid_h(ev[:2], dt)
        a_v = self.pid_v(ev[2:3], dt)
        a_cmd = np.array([a_h[0], a_h[1], a_v[0] + est["g"]])
        return a_cmd, {"v_des": v_des.tolist(), "vel_error": ev.tolist(), "pid_h": self.pid_h.last, "pid_v": self.pid_v.last}

    def compute(self, est: dict, target: np.ndarray, dt: float, params):
        a_cmd, info = self.guidance(est, target, dt)
        cmd, alloc = allocate(a_cmd, est["euler"], est["omega"], est["mass"], params, self.cfg.allocation)
        info.update(alloc)
        return cmd, info
