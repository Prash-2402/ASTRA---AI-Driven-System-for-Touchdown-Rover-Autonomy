"""Extended Kalman Filter for the lander.

State x (12): p[3] world | v[3] world | theta[3] (roll, pitch, yaw) | b_a[3] accelerometer bias (body)
Inputs u: accelerometer specific force f_b (body), gyro rate w_b (body).

Process model (discrete, dt):
  p_k+1 = p + v dt
  v_k+1 = v + (R(theta) (f_b - b_a) + g) dt
  theta_k+1 = theta + E(theta) w_b dt          (ZYX Euler kinematics)
  b_a,k+1 = b_a                                 (random walk via Q)

Measurements: position (TRN), velocity (Doppler), attitude (star tracker),
altimeter h(x) = p_z - DEM(p_x, p_y)  (nonlinear through the onboard DEM).

Numerical safeguards: Joseph-form covariance update, symmetrisation,
eigenvalue floor, chi-square innovation gating, angle wrapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from simulation.common.math3d import euler_to_rotmat, wrap_angle

LABELS = ["px", "py", "pz", "vx", "vy", "vz", "roll", "pitch", "yaw", "bax", "bay", "baz"]
CHI2_GATE = {1: 10.83, 3: 16.27}   # 99.9 % gates


def euler_rate_matrix(th: np.ndarray) -> np.ndarray:
    r, p, _ = th
    cr, sr, cp = np.cos(r), np.sin(r), np.cos(p)
    cp = np.sign(cp) * max(abs(cp), 1e-3)
    tp = np.sin(p) / cp
    return np.array([[1, sr * tp, cr * tp], [0, cr, -sr], [0, sr / cp, cr / cp]])


@dataclass
class EKFConfig:
    accel_noise: float = 0.05        # m/s^2 / sqrt(Hz)-ish, drives velocity process noise
    gyro_noise: float = 0.002
    bias_walk: float = 0.001
    init_pos_std: float = 30.0
    init_vel_std: float = 2.0
    init_att_std: float = 0.02
    init_bias_std: float = 0.05
    meas_std: dict = field(default_factory=lambda: {"position": [4.0, 4.0, 6.0], "velocimeter": 0.12,
                                                     "attitude": 0.002, "altimeter": 1.0})


class LanderEKF:
    def __init__(self, cfg: EKFConfig, x0: np.ndarray, gravity: float, dem=None):
        self.cfg = cfg
        self.g = np.array([0.0, 0.0, -gravity])
        self.x = np.asarray(x0, dtype=float).copy()
        self.P = np.diag([cfg.init_pos_std] * 3 + [cfg.init_vel_std] * 3 + [cfg.init_att_std] * 3
                         + [cfg.init_bias_std] * 3) ** 2
        self.dem = dem          # callable (x, y) -> height, with .gradient(x, y)
        self.last_innovation: dict[str, dict] = {}
        self.rejected = 0
        self.t = 0.0

    # -- prediction -------------------------------------------------------
    def _rv(self, th, a):
        return euler_to_rotmat(th) @ a

    def predict(self, f_b: np.ndarray, w_b: np.ndarray, dt: float) -> None:
        x = self.x
        p, v, th, b = x[0:3], x[3:6], x[6:9], x[9:12]
        R = euler_to_rotmat(th)
        a_b = f_b - b
        E = euler_rate_matrix(th)
        xn = x.copy()
        xn[0:3] = p + v * dt
        xn[3:6] = v + (R @ a_b + self.g) * dt
        xn[6:9] = wrap_angle(th + E @ w_b * dt)

        F = np.eye(12)
        F[0:3, 3:6] = np.eye(3) * dt
        # d(R(th) a)/d th via central differences on the 3 Euler angles (analytic form is long; documented)
        eps = 1e-6
        dRa = np.zeros((3, 3))
        dEw = np.zeros((3, 3))
        for i in range(3):
            d = np.zeros(3); d[i] = eps
            dRa[:, i] = (self._rv(th + d, a_b) - self._rv(th - d, a_b)) / (2 * eps)
            dEw[:, i] = (euler_rate_matrix(th + d) @ w_b - euler_rate_matrix(th - d) @ w_b) / (2 * eps)
        F[3:6, 6:9] = dRa * dt
        F[3:6, 9:12] = -R * dt
        F[6:9, 6:9] += dEw * dt

        c = self.cfg
        Q = np.zeros((12, 12))
        Q[0:3, 0:3] = np.eye(3) * (0.5 * c.accel_noise * dt ** 2) ** 2
        Q[3:6, 3:6] = np.eye(3) * (c.accel_noise ** 2) * dt
        Q[6:9, 6:9] = np.eye(3) * (c.gyro_noise ** 2) * dt
        Q[9:12, 9:12] = np.eye(3) * (c.bias_walk ** 2) * dt
        self.x = xn
        self.P = F @ self.P @ F.T + Q
        self._condition()
        self.t += dt

    # -- updates ----------------------------------------------------------
    def _update(self, name: str, z: np.ndarray, hx: np.ndarray, H: np.ndarray, Rm: np.ndarray, angle: bool = False,
                dry: bool = False) -> bool:
        """dry=True computes and records the innovation without correcting the state (isolated sensors
        stay under observation but no longer influence the estimate)."""
        y = z - hx
        if angle:
            y = wrap_angle(y)
        S = H @ self.P @ H.T + Rm
        S = 0.5 * (S + S.T)
        try:
            Sinv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            return False
        nis = float(y @ Sinv @ y)
        gate = CHI2_GATE.get(len(y), 16.27)
        accepted = nis <= gate
        self.last_innovation[name] = {"t": self.t, "innovation": y.tolist(), "nis": nis,
                                      "S_diag": np.diag(S).tolist(), "accepted": accepted and not dry}
        if dry:
            return False
        if not accepted:
            self.rejected += 1
            return False
        K = self.P @ H.T @ Sinv
        self.x = self.x + K @ y
        self.x[6:9] = wrap_angle(self.x[6:9])
        I_KH = np.eye(12) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ Rm @ K.T      # Joseph form
        self._condition()
        return True

    def update_position(self, z, dry=False, delay: float = 0.0):
        """TRN fix with known latency: it describes where the vehicle was `delay` s ago, h(x) = p - v*delay."""
        H = np.zeros((3, 12)); H[:, 0:3] = np.eye(3); H[:, 3:6] = -np.eye(3) * delay
        return self._update("position", z, self.x[0:3] - self.x[3:6] * delay, H,
                            np.diag(np.square(self.cfg.meas_std["position"])), dry=dry)

    def update_velocity(self, z, dry=False):
        H = np.zeros((3, 12)); H[:, 3:6] = np.eye(3)
        return self._update("velocimeter", z, self.x[3:6], H, np.eye(3) * self.cfg.meas_std["velocimeter"] ** 2, dry=dry)

    def update_attitude(self, z):
        H = np.zeros((3, 12)); H[:, 6:9] = np.eye(3)
        return self._update("attitude", z, self.x[6:9], H, np.eye(3) * self.cfg.meas_std["attitude"] ** 2, angle=True)

    def update_altimeter(self, z, dry=False):
        if self.dem is None:
            return False
        px, py, pz = self.x[0:3]
        hx = np.array([pz - self.dem.height(px, py)])
        gx, gy = self.dem.gradient(px, py)
        H = np.zeros((1, 12)); H[0, 0] = -gx; H[0, 1] = -gy; H[0, 2] = 1.0
        sigma = self.cfg.meas_std["altimeter"] + 0.002 * abs(float(z[0]))
        return self._update("altimeter", np.asarray(z, float), hx, H, np.array([[sigma ** 2]]), dry=dry)

    def _condition(self) -> None:
        P = 0.5 * (self.P + self.P.T)
        w, V = np.linalg.eigh(P)
        if w.min() < 1e-10:
            w = np.maximum(w, 1e-10)
            P = (V * w) @ V.T
        self.P = P

    def sigma(self) -> np.ndarray:
        return np.sqrt(np.diag(self.P))

    def position_sigma_h(self) -> float:
        return float(np.sqrt(self.P[0, 0] + self.P[1, 1]))
