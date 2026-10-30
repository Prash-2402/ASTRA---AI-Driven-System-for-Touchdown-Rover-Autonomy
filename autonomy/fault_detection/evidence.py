"""Fault evidence extraction from sensor-derived signals (no ground truth)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Evidence:
    t: float = 0.0
    lidar_stale: float = 0.0
    camera_stale: float = 0.0
    visloc_stale: float = 0.0
    lidar_corruption: float = 0.0          # fraction of ground-ring rays inconsistent with flat-ground geometry
    visloc_nis: float = 0.0
    wheel_residual: np.ndarray = field(default_factory=lambda: np.zeros(6))   # isolated (wheel - median of others)
    wheel_capability: np.ndarray = field(default_factory=lambda: np.ones(6))  # estimated torque capability fraction
    slip: float = 0.0
    battery_ratio: float = 1.0             # measured / predicted electrical power
    p_fixed_est: float = 22.0              # estimated non-traction load [W]
    perception_inconsistency: float = 0.0
    perception_checked: int = 0

    def to_dict(self):
        return {k: (np.round(v, 3).tolist() if isinstance(v, np.ndarray) else round(float(v), 4)) for k, v in self.__dict__.items()}


class EvidenceBuilder:
    def __init__(self, nominal_torque: float, electronics_w: float, eta: float, k_cu: float):
        self.nominal_torque = nominal_torque
        self.electronics_w = electronics_w
        self.eta, self.k_cu = eta, k_cu
        self.wheel_res = np.zeros(6)
        self.capability = np.ones(6)
        self.batt_ratio = 1.0
        self.p_fixed = electronics_w
        self.slip = 0.0
        self.nis_hist: deque = deque(maxlen=8)

    def wheel_update(self, cmd: np.ndarray, meas: np.ndarray, torque: np.ndarray):
        denom = np.maximum(np.abs(cmd), 0.8)
        r = np.abs(cmd - meas) / denom
        iso = np.array([r[k] - np.median(np.delete(r, k)) for k in range(6)])
        self.wheel_res = 0.9 * self.wheel_res + 0.1 * iso
        # capability: when a wheel lags its command, the torque it delivers is (close to) its ceiling
        lagging = r > 0.25
        for k in np.where(lagging)[0]:
            ceiling = abs(torque[k]) / self.nominal_torque
            self.capability[k] = 0.95 * self.capability[k] + 0.05 * min(ceiling, 1.0)
        for k in np.where(~lagging)[0]:
            self.capability[k] = min(1.0, self.capability[k] + 0.002)

    def battery_update(self, power_meas: float, torques: np.ndarray, speeds: np.ndarray):
        mech = np.maximum(torques * speeds, 0).sum() / self.eta + self.k_cu * np.sum(torques ** 2)
        pred = mech + self.electronics_w
        ratio = power_meas / max(pred, 1.0)
        self.batt_ratio = 0.85 * self.batt_ratio + 0.15 * ratio
        self.p_fixed = 0.9 * self.p_fixed + 0.1 * max(power_meas - mech, 0.0)

    def slip_update(self, v_odom: float, v_est: float):
        s = 0.0 if abs(v_odom) < 0.05 else float(np.clip(1 - v_est / v_odom, -1, 1))
        self.slip = 0.8 * self.slip + 0.2 * s

    def nis_update(self, nis: float):
        self.nis_hist.append(nis)

    def lidar_corruption(self, pts_body: np.ndarray, rows: int, sensor_h: float, tilts_deg, roll: float, pitch: float) -> float:
        """Fraction of steep-ring returns inconsistent with locally planar ground, using the estimated attitude.
        Expected range along a ray d (rotated by roll/pitch) to a plane sensor_h below: sensor_h / (-d_z)."""
        cr, sr, cp, sp = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch)
        R = np.array([[cp, sp * sr, sp * cr], [0, cr, -sr], [-sp, cp * sr, cp * cr]])
        n = len(pts_body) // rows
        bad = tot = 0
        for r_i, tilt in enumerate(tilts_deg):
            if tilt > -15:
                continue
            row = pts_body[r_i * n:(r_i + 1) * n]
            fin = np.all(np.isfinite(row), axis=1)
            if not fin.any():
                continue
            d = row[fin] - np.array([0.3, 0, sensor_h - 0.3])
            rng = np.linalg.norm(d, axis=1)
            dz = (d / rng[:, None]) @ R.T
            down = dz[:, 2] < -0.1
            exp = sensor_h / -dz[down, 2]
            tot += down.sum()
            bad += np.sum(np.abs(rng[down] - exp) > 0.6 * exp)
        return bad / tot if tot else 0.0
