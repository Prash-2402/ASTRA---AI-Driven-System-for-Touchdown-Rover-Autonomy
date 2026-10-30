"""Thrust allocation + attitude control inner loop for the lander.

Input: desired non-gravitational acceleration a_cmd (world) from a guidance
law (PID cascade, MPC or PPO). Output: ActuatorCommand (throttle, lateral, torque).

1. Desired thrust vector T = m a_cmd; its direction defines the desired body z axis,
   limited to tilt_max from vertical.
2. Throttle = projection of T onto the *current* body z axis / T_max.
3. Lateral thrusters supply the residual component perpendicular to body z.
4. Attitude PD (quaternion-free small-angle error  e = R^T (z_b × z_des), yaw hold)
   with closed-loop natural frequency wn and damping zeta, scaled by inertia.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.common.math3d import euler_to_rotmat, wrap_angle
from simulation.touchdown.lander import ActuatorCommand, LanderParams


@dataclass
class AllocationConfig:
    tilt_max_deg: float = 30.0
    att_wn: float = 2.2
    att_zeta: float = 0.9
    yaw_target: float = 0.0


def allocate(a_cmd: np.ndarray, euler: np.ndarray, omega: np.ndarray, mass: float,
             p: LanderParams, cfg: AllocationConfig) -> tuple[ActuatorCommand, dict]:
    T = mass * np.asarray(a_cmd, dtype=float)
    if T[2] < 0.05 * mass:            # never command downward thrust
        T[2] = 0.05 * mass
    tn = float(np.linalg.norm(T))
    d = T / tn
    tilt_max = np.radians(cfg.tilt_max_deg)
    tilt = float(np.arccos(np.clip(d[2], -1, 1)))
    if tilt > tilt_max:
        h = np.hypot(d[0], d[1])
        d = np.array([d[0] / h * np.sin(tilt_max), d[1] / h * np.sin(tilt_max), np.cos(tilt_max)])
    R = euler_to_rotmat(euler)
    zb = R[:, 2]
    along = float(T @ zb)
    throttle = float(np.clip(along / p.max_thrust, 0.0, 1.0))
    resid = T - throttle * p.max_thrust * zb
    rb = R.T @ resid
    lateral = np.clip(rb[:2] / p.max_lateral_thrust, -1, 1)
    e_body = R.T @ np.cross(zb, d)
    e_body[2] = -float(wrap_angle(euler[2] - cfg.yaw_target))
    I = np.asarray(p.inertia_full) * mass / p.wet_mass
    wn, z = cfg.att_wn, cfg.att_zeta
    tau = I * (wn ** 2 * e_body - 2 * z * wn * np.asarray(omega))
    torque = np.clip(tau / np.asarray(p.max_torque), -1, 1)
    info = {"a_cmd": np.asarray(a_cmd).tolist(), "thrust_dir": d.tolist(),
            "att_error_deg": np.degrees(e_body).tolist(), "tilt_cmd_deg": float(np.degrees(min(tilt, tilt_max)))}
    return ActuatorCommand(throttle, lateral, torque), info
