"""Generic PID with anti-windup (conditional integration + integrator clamp) and output saturation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PIDGains:
    kp: float
    ki: float = 0.0
    kd: float = 0.0
    out_min: float = -np.inf
    out_max: float = np.inf
    i_limit: float = np.inf


class PID:
    def __init__(self, gains: PIDGains, dim: int = 1):
        self.g = gains
        self.i = np.zeros(dim)
        self.prev_e = None
        self.last = {}

    def reset(self):
        self.i[:] = 0
        self.prev_e = None

    def __call__(self, error, dt: float, derivative=None):
        e = np.atleast_1d(np.asarray(error, dtype=float))
        if derivative is None:
            d = np.zeros_like(e) if self.prev_e is None else (e - self.prev_e) / max(dt, 1e-6)
        else:
            d = np.atleast_1d(np.asarray(derivative, dtype=float))
        self.prev_e = e
        u_unsat = self.g.kp * e + self.g.ki * self.i + self.g.kd * d
        u = np.clip(u_unsat, self.g.out_min, self.g.out_max)
        # anti-windup: only integrate when not saturated, or when integration drives out of saturation
        saturated = u != u_unsat
        drives_out = np.sign(e) != np.sign(u_unsat)
        integrate = ~saturated | drives_out
        self.i = np.where(integrate, self.i + e * dt, self.i)
        self.i = np.clip(self.i, -self.g.i_limit, self.g.i_limit)
        self.last = {"p": (self.g.kp * e).tolist(), "i": (self.g.ki * self.i).tolist(), "d": (self.g.kd * d).tolist(),
                     "u": u.tolist(), "saturated": bool(saturated.any())}
        return u
