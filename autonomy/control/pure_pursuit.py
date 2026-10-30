"""Pure Pursuit waypoint tracking + skid-steer wheel allocation for the six-wheel rover.

curvature k = 2 sin(alpha) / L_d       (alpha: bearing of look-ahead point in the rover frame)
v = v_max * speed_factor * max(0.25, 1 - |alpha|/1.2)       (slow for sharp heading corrections)
w = k v
wheel speeds: left = (v - w B_eff/2) / r,  right = (v + w B_eff/2) / r
Torque allocation: per-wheel torque limits; when a wheel is known to be degraded the
same-side healthy wheels receive the torque headroom (up to motor_peak) to hold the side's tractive force.
Slip handling: if estimated slip > slip_limit, speed is scaled down (traction control).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.common.math3d import wrap_angle


@dataclass
class PurePursuitConfig:
    lookahead: float = 1.8
    v_max: float = 0.4
    wheel_radius: float = 0.16
    b_eff: float = 1.35          # effective skid-steer track (> geometric 0.94 m) - calibrated
    wheel_torque: float = 8.0    # nominal per-wheel max torque [N m]
    motor_peak: float = 10.8
    slip_limit: float = 0.35
    turn_in_place_deg: float = 70.0


class PurePursuit:
    def __init__(self, cfg: PurePursuitConfig):
        self.cfg = cfg
        self.idx = 0
        self.path: list = []

    def set_path(self, path: list) -> None:
        self.path = list(path)
        self.idx = 0

    def lookahead_point(self, x, y, lookahead=None):
        P = self.path
        L = lookahead or self.cfg.lookahead
        while self.idx < len(P) - 1 and np.hypot(P[self.idx][0] - x, P[self.idx][1] - y) < L:
            self.idx += 1
        # closest-progress safeguard
        return P[self.idx] if P else (x, y)

    def compute(self, pose, speed_factor: float, slip: float, wheel_health: np.ndarray,
                gentle: bool = False) -> tuple[np.ndarray, np.ndarray, dict]:
        """gentle=True: 1.6x look-ahead and no pivot turns (lower curvature -> lower skid-steer torque demand)."""
        c = self.cfg
        if gentle:
            from dataclasses import replace
            c = replace(c, lookahead=c.lookahead * 1.6, turn_in_place_deg=179.0)
        x, y, psi = pose
        if not self.path or speed_factor <= 0:
            return np.zeros(6), np.full(6, c.wheel_torque) * wheel_health, {"v": 0.0, "w": 0.0, "alpha": 0.0}
        lx, ly = self.lookahead_point(x, y, c.lookahead)
        alpha = float(wrap_angle(np.arctan2(ly - y, lx - x) - psi))
        Ld = max(np.hypot(lx - x, ly - y), 0.3)
        v = c.v_max * speed_factor * max(0.25, 1 - abs(alpha) / 1.2)
        if slip > c.slip_limit:
            v *= max(0.4, 1 - (slip - c.slip_limit))
        if abs(alpha) > np.radians(c.turn_in_place_deg):
            v = 0.0
            w = np.sign(alpha) * 0.5 * max(speed_factor, 0.4)
        else:
            w = 2 * np.sin(alpha) / Ld * v
        vl = (v - w * c.b_eff / 2) / c.wheel_radius
        vr = (v + w * c.b_eff / 2) / c.wheel_radius
        speeds = np.array([vl, vl, vl, vr, vr, vr])
        torques = np.full(6, c.wheel_torque) * wheel_health
        for side in (slice(0, 3), slice(3, 6)):
            deficit = np.sum(c.wheel_torque - torques[side])
            if deficit > 1e-6:
                healthy = wheel_health[side] > 0.95
                if healthy.any():
                    t = torques[side]
                    t[healthy] = np.minimum(c.motor_peak, t[healthy] + deficit / healthy.sum())
                    torques[side] = t
        return speeds, torques, {"v": float(v), "w": float(w), "alpha": alpha, "lookahead": [float(lx), float(ly)]}
