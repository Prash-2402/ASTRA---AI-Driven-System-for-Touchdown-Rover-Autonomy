"""Rover Extended Kalman Filter.

State x (8): [x, y, z, v, psi, omega, roll, pitch]   (world ENU, m, m/s, rad, rad/s)
Process (dt):
  x += v cos(psi) cos(pitch) dt     y += v sin(psi) cos(pitch) dt     z += -v sin(pitch) dt
  psi += omega dt                   v, omega, roll, pitch: random walks (driven by Q)
Measurements:
  wheel odometry  v_odom = r * mean(wheel speeds)          (slip makes this biased -> evidence)
  gyro            omega_z (body ~ world yaw rate)
  IMU tilt        [roll, pitch]
  visual localisation [x, y, z, psi]                        (camera-derived; lost under camera dropout)
Covariance is reported alongside the true error; covariance is NOT a proof of accuracy.
"""
from __future__ import annotations

import numpy as np

from simulation.common.math3d import wrap_angle

LABELS = ["x", "y", "z", "v", "psi", "omega", "roll", "pitch"]


class RoverEKF:
    def __init__(self, x0: np.ndarray, p0_diag=None, q_diag=None):
        self.x = np.asarray(x0, float).copy()
        self.P = np.diag(p0_diag if p0_diag is not None else [0.05, 0.05, 0.05, 0.05, 0.02, 0.02, 0.02, 0.02]) ** 2
        self.q = np.asarray(q_diag if q_diag is not None else [0.01, 0.01, 0.02, 0.4, 0.002, 0.3, 0.05, 0.05])
        self.innovations: list[dict] = []
        self.last_nis: dict[str, float] = {}
        self.consecutive_rejects = 0
        self.relocalizations = 0

    def predict(self, dt: float) -> None:
        x, y, z, v, psi, om, roll, pitch = self.x
        c, s, cp, sp = np.cos(psi), np.sin(psi), np.cos(pitch), np.sin(pitch)
        self.x = np.array([x + v * c * cp * dt, y + v * s * cp * dt, z - v * sp * dt, v, wrap_angle(psi + om * dt),
                           om, roll, pitch])
        F = np.eye(8)
        F[0, 3] = c * cp * dt; F[0, 4] = -v * s * cp * dt; F[0, 7] = -v * c * sp * dt
        F[1, 3] = s * cp * dt; F[1, 4] = v * c * cp * dt; F[1, 7] = -v * s * sp * dt
        F[2, 3] = -sp * dt; F[2, 7] = -v * cp * dt
        F[4, 5] = dt
        Q = np.diag(self.q ** 2) * dt
        self.P = F @ self.P @ F.T + Q
        self.P = 0.5 * (self.P + self.P.T)

    def _update(self, name, z, hx, H, R, angle_idx=(), t=0.0, gate=None) -> bool:
        y = np.atleast_1d(z - hx).astype(float)
        for i in angle_idx:
            y[i] = wrap_angle(y[i])
        S = H @ self.P @ H.T + R
        Si = np.linalg.inv(S)
        nis = float(y @ Si @ y)
        self.last_nis[name] = nis
        self.innovations.append({"t": round(t, 2), "sensor": name, "nis": nis, "dof": len(y)})
        if len(self.innovations) > 2000:
            self.innovations = self.innovations[-1000:]
        if gate is not None and nis > gate:
            return False
        # Kalman gain computation
        K = self.P @ H.T @ Si
        self.x = self.x + K @ y
        self.x[4] = wrap_angle(self.x[4])
        # Joseph-form covariance update: (I - KH) P (I - KH)^T + K R K^T (preserves positive-definiteness)
        IKH = np.eye(8) - K @ H
        self.P = IKH @ self.P @ IKH.T + K @ R @ K.T
        self.P = 0.5 * (self.P + self.P.T)
        return True

    def update_odometry(self, v_odom: float, t: float, sigma: float | None = None) -> bool:
        H = np.zeros((1, 8)); H[0, 3] = 1
        s = sigma if sigma is not None else 0.03 + 0.15 * abs(v_odom)
        return self._update("odometry", np.array([v_odom]), self.x[3:4], H, np.array([[s * s]]), t=t)

    def update_gyro(self, wz: float, t: float) -> bool:
        H = np.zeros((1, 8)); H[0, 5] = 1
        return self._update("gyro", np.array([wz]), self.x[5:6], H, np.array([[0.006 ** 2]]), t=t)

    def update_tilt(self, rp, t: float) -> bool:
        H = np.zeros((2, 8)); H[0, 6] = 1; H[1, 7] = 1
        return self._update("tilt", np.asarray(rp), self.x[6:8], H, np.eye(2) * 0.02 ** 2, t=t)

    def update_visloc(self, xy, z, yaw, t: float) -> bool:
        """Absolute fix with chi-square gating. Three consecutive rejections are treated as evidence
        that the filter itself has diverged (over-confident P): position/heading covariance is
        inflated to cover the innovation and the fix is re-applied (re-localisation)."""
        H = np.zeros((4, 8)); H[0, 0] = H[1, 1] = H[2, 2] = H[3, 4] = 1
        zz = np.array([xy[0], xy[1], z, yaw])
        R = np.diag([0.15, 0.15, 0.08, 0.02]) ** 2
        ok = self._update("visloc", zz, self.x[[0, 1, 2, 4]], H, R, angle_idx=(3,), t=t, gate=30.0)
        if ok:
            self.consecutive_rejects = 0
            return True
        self.consecutive_rejects += 1
        if self.consecutive_rejects >= 3:
            y = zz - self.x[[0, 1, 2, 4]]
            y[3] = wrap_angle(y[3])
            for k, idx in enumerate((0, 1, 2, 4)):
                self.P[idx, idx] += y[k] ** 2
            self.relocalizations += 1
            self.consecutive_rejects = 0
            return self._update("visloc", zz, self.x[[0, 1, 2, 4]], H, R, angle_idx=(3,), t=t, gate=None)
        return False

    def sigma(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.P), 0, None))

    def pos_sigma(self) -> float:
        return float(np.sqrt(self.P[0, 0] + self.P[1, 1]))
