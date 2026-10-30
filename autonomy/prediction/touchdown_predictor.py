"""Touchdown prediction engine.

Rolls a translational point-mass model forward from the *estimated* state
under the descent-profile guidance law with the vehicle's actuator limits
(max acceleration T_max/m, tilt limit) and rocket-equation fuel use. Used for
(a) the predicted trajectory / touchdown point shown to the operator and
(b) diversion-feasibility checks.
"""
from __future__ import annotations

import numpy as np

from autonomy.control.descent_profile import desired_velocity
from autonomy.framework import PredictionEngine
from simulation.touchdown.environment import G0


class TouchdownPredictor(PredictionEngine):
    def __init__(self, dem, max_thrust: float, isp: float, dry_mass: float, tilt_max_deg: float = 30.0,
                 k_v: float = 0.9, dt: float = 0.25):
        self.dem = dem
        self.max_thrust = max_thrust
        self.isp = isp
        self.dry = dry_mass
        self.tan_t = np.tan(np.radians(tilt_max_deg))
        self.k_v = k_v
        self.dt = dt

    def predict(self, state: np.ndarray, horizon_s: float = 200.0, *, target=None, fuel: float = 0.0,
                gravity: float = 3.72, profile_accel: float = 1.0) -> dict:
        p = np.asarray(state[0:3], float).copy()
        v = np.asarray(state[3:6], float).copy()
        fuel_left = float(fuel)
        traj = [p.tolist()]
        t = 0.0
        fuel_used = 0.0
        while t < horizon_s:
            ground = self.dem.height(p[0], p[1])
            agl = p[2] - ground
            if agl <= 0.0:
                break
            m = self.dry + max(fuel_left, 0.0)
            if target is not None and fuel_left > 0:
                v_des = desired_velocity(p, target, agl, a_prof=profile_accel)
                a = self.k_v * (v_des - v) + np.array([0, 0, gravity])
                a[2] = max(a[2], 0.0)
                h = np.hypot(a[0], a[1])
                if h > self.tan_t * a[2]:
                    a[:2] *= self.tan_t * a[2] / max(h, 1e-9)
                amax = self.max_thrust / m
                n = np.linalg.norm(a)
                if n > amax:
                    a *= amax / n
                dm = m * np.linalg.norm(a) / (self.isp * G0) * self.dt
                fuel_left -= dm
                fuel_used += dm
            else:
                a = np.zeros(3)
            acc = a + np.array([0, 0, -gravity])
            p = p + v * self.dt + 0.5 * acc * self.dt ** 2
            v = v + acc * self.dt
            t += self.dt
            if len(traj) < 400 and int(t / self.dt) % 2 == 0:
                traj.append(p.tolist())
        traj.append(p.tolist())
        ground = self.dem.height(p[0], p[1])
        return {"trajectory": traj, "touchdown_point": [float(p[0]), float(p[1]), float(ground)],
                "touchdown_velocity": v.tolist(), "time_to_go": t, "fuel_used": fuel_used,
                "fuel_remaining": fuel_left, "fuel_exhausted": fuel_left <= 0}
