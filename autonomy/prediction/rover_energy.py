"""Rover route energy prediction (planner + supervisor use the same model, with online-updated parameters).

Energy per metre at speed v on a segment with slope s and class c:
  e = P_fixed / v  +  m g (C_rr(c) + max(sin s, 0)) / eta + k_slip(c)
P_fixed (electronics + parasitic) is estimated online from battery telemetry, so a
power-drain fault changes the prediction once it is observed.
"""
from __future__ import annotations

import numpy as np

from autonomy.planning.rover_perception import cell_of

CRR_EST = {-1: 0.08, 0: 0.03, 1: 0.06, 2: 0.16, 3: 0.08}


class RouteEnergyModel:
    def __init__(self, mass: float, g: float = 3.72076, eta: float = 0.72, p_fixed: float = 22.0):
        self.mass, self.g, self.eta = mass, g, eta
        self.p_fixed = p_fixed
        self.drive_scale = 1.0       # multiplicative correction on traction energy (estimated online)

    def predict(self, path: list, slope_deg: np.ndarray, cam_class: np.ndarray, v: float) -> dict:
        v = max(v, 0.05)
        e = 0.0
        length = 0.0
        for a, b in zip(path[:-1], path[1:]):
            d = float(np.hypot(b[0] - a[0], b[1] - a[1]))
            i, j = cell_of(*b)
            s = np.radians(slope_deg[i, j])
            crr = CRR_EST.get(int(cam_class[i, j]), 0.08)
            traction = self.mass * self.g * (crr + max(np.sin(s) * 0.5, 0.0)) / self.eta * self.drive_scale
            e += d * (self.p_fixed / v + traction)
            length += d
        return {"energy_wh": e / 3600.0, "length_m": length, "time_s": length / v}

    def best_speed(self, v_max: float) -> float:
        """Energy-per-metre is decreasing in v when fixed loads dominate: drive as fast as allowed."""
        return v_max
