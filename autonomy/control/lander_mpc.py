"""Model Predictive Control guidance for the lander.

Prediction model (translational, point mass with gravity), step dt_m:
  p_{k+1} = p_k + v_k dt + 0.5 (u_k + g) dt^2
  v_{k+1} = v_k + (u_k + g) dt
Decision variables: u_0..u_{Nc-1} (thrust acceleration, world); u_k = u_{Nc-1} for k >= Nc (move blocking).

Objective (documented in docs/TOUCHDOWN_CONTROL.md):
  J = sum_k  Qv ||v_k - v_ref_k||^2 + Qp ||p_k - p_ref_k||^2 + R ||u_k - u_hover||^2 + Rd ||u_k - u_{k-1}||^2
      + Wgs * sum_k max(0, tan(gs)·||p_xy - target_xy|| - (p_z - h_target))^2      (soft glide-slope)
Hard constraints per distinct input:
  ||u||^2 <= a_max^2,  u_z >= a_min,  ||u_xy|| <= tan(tilt_max) u_z
Reference: a kinematic roll-out of the shared descent-profile velocity field.

Every update: read estimate -> predict -> optimise (SLSQP, warm start) -> apply first input -> recompute next update.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from autonomy.control.descent_profile import desired_velocity
from autonomy.control.lander_allocation import AllocationConfig, allocate


@dataclass
class LanderMPCConfig:
    horizon: int = 16               # prediction steps N
    control_horizon: int = 5        # distinct inputs Nc
    dt: float = 0.5                 # prediction step [s]
    update_period: float = 0.25     # re-optimisation period [s]
    q_v: float = 1.0
    q_p: float = 0.02
    r_u: float = 0.05
    r_du: float = 0.3
    w_glideslope: float = 2.0
    glideslope_deg: float = 15.0
    tilt_max_deg: float = 30.0
    profile_accel: float = 1.0
    profile_k_low: float = 0.08       # gentle final descent (same reference as the PID)
    allocation: AllocationConfig = field(default_factory=AllocationConfig)


class LanderMPCController:
    name = "mpc"

    def __init__(self, cfg: LanderMPCConfig | None = None):
        self.cfg = cfg or LanderMPCConfig()
        self.u_prev: np.ndarray | None = None
        self.t_since = 1e9
        self.u_apply = None
        self.last_solution: dict = {}

    def reset(self):
        self.u_prev = None; self.t_since = 1e9; self.u_apply = None

    def _expand(self, U: np.ndarray) -> np.ndarray:
        c = self.cfg
        Uf = np.empty((c.horizon, 3))
        Uf[:c.control_horizon] = U
        Uf[c.control_horizon:] = U[-1]
        return Uf

    def rollout(self, p0, v0, Uf, g):
        c = self.cfg
        P = np.empty((c.horizon + 1, 3)); V = np.empty((c.horizon + 1, 3))
        P[0], V[0] = p0, v0
        gv = np.array([0, 0, -g])
        for k in range(c.horizon):
            a = Uf[k] + gv
            P[k + 1] = P[k] + V[k] * c.dt + 0.5 * a * c.dt ** 2
            V[k + 1] = V[k] + a * c.dt
        return P, V

    def reference(self, p0, target, ground_h, hold: bool = False):
        c = self.cfg
        P = np.empty((c.horizon + 1, 3)); V = np.empty((c.horizon + 1, 3))
        p = np.asarray(p0, float).copy()
        for k in range(c.horizon + 1):
            v = desired_velocity(p, target, p[2] - ground_h, a_prof=c.profile_accel, k_low=c.profile_k_low, hold=hold)
            P[k], V[k] = p, v
            p = p + v * c.dt
            if p[2] < ground_h:
                p[2] = ground_h
        return P, V

    def solve(self, est: dict, target: np.ndarray) -> dict:
        c = self.cfg
        g, m = est["g"], est["mass"]
        a_max = est["max_thrust"] / m * 0.98
        a_min = est["min_thrust"] / m
        ground_h = est["p"][2] - est["agl"]
        Pref, Vref = self.reference(est["p"], target, ground_h, hold=bool(est.get("hover")))
        u_hover = np.array([0, 0, g])
        tan_t = np.tan(np.radians(c.tilt_max_deg))
        tan_gs = np.tan(np.radians(c.glideslope_deg))
        h_t = float(target[2]) if len(target) > 2 else ground_h

        def cost(x):
            U = x.reshape(c.control_horizon, 3)
            Uf = self._expand(U)
            P, V = self.rollout(est["p"], est["v"], Uf, g)
            J = c.q_v * np.sum((V[1:] - Vref[1:]) ** 2) + c.q_p * np.sum((P[1:] - Pref[1:]) ** 2)
            J += c.r_u * np.sum((Uf - u_hover) ** 2)
            prev = self.u_prev[0] if self.u_prev is not None else Uf[0]
            dU = np.diff(np.vstack([prev, U]), axis=0)
            J += c.r_du * np.sum(dU ** 2)
            viol = tan_gs * np.linalg.norm(P[1:, :2] - target[:2], axis=1) - (P[1:, 2] - h_t)
            J += c.w_glideslope * np.sum(np.maximum(0.0, viol) ** 2)
            return float(J)

        cons = []
        for k in range(c.control_horizon):
            i = 3 * k
            cons.append({"type": "ineq", "fun": lambda x, i=i: a_max ** 2 - (x[i] ** 2 + x[i + 1] ** 2 + x[i + 2] ** 2)})
            cons.append({"type": "ineq", "fun": lambda x, i=i: x[i + 2] - a_min})
            cons.append({"type": "ineq", "fun": lambda x, i=i: tan_t * x[i + 2] - np.sqrt(x[i] ** 2 + x[i + 1] ** 2 + 1e-9)})
        if self.u_prev is not None:
            x0 = np.vstack([self.u_prev[1:], self.u_prev[-1:]]).ravel()
        else:
            x0 = np.tile(u_hover, c.control_horizon)
        t0 = time.perf_counter()
        res = minimize(cost, x0, method="SLSQP", constraints=cons, options={"maxiter": 60, "ftol": 1e-4})
        U = res.x.reshape(c.control_horizon, 3)
        # project onto constraints in case SLSQP returned a slightly infeasible iterate
        for k in range(c.control_horizon):
            U[k, 2] = max(U[k, 2], a_min)
            h = np.hypot(U[k, 0], U[k, 1])
            if h > tan_t * U[k, 2]:
                U[k, :2] *= tan_t * U[k, 2] / h
            n = np.linalg.norm(U[k])
            if n > a_max:
                U[k] *= a_max / n
        self.u_prev = U
        P, V = self.rollout(est["p"], est["v"], self._expand(U), g)
        self.last_solution = {"success": bool(res.success), "iterations": int(res.nit), "cost": float(res.fun),
                              "solve_ms": 1000 * (time.perf_counter() - t0), "predicted_positions": P.tolist(),
                              "reference_positions": Pref.tolist(), "u0": U[0].tolist(),
                              "horizon": c.horizon, "control_horizon": c.control_horizon, "message": str(res.message)}
        return self.last_solution

    def guidance(self, est: dict, target: np.ndarray, dt: float):
        self.t_since += dt
        hov = bool(est.get("hover"))
        if hov != getattr(self, "_hov", False):          # re-plan at once when a hover starts or ends
            self._hov = hov
            self.t_since = 1e9
        if self.u_apply is None or self.t_since >= self.cfg.update_period - 1e-9:
            self.solve(est, target)
            self.u_apply = self.u_prev[0].copy()
            self.t_since = 0.0
        sol = {k: v for k, v in self.last_solution.items() if k not in ("predicted_positions", "reference_positions")}
        return self.u_apply.copy(), {"mpc": sol}

    def compute(self, est: dict, target: np.ndarray, dt: float, params):
        a_cmd, info = self.guidance(est, target, dt)
        cmd, alloc = allocate(a_cmd, est["euler"], est["omega"], est["mass"], params, self.cfg.allocation)
        info.update(alloc)
        return cmd, info

    def predicted_trajectory(self) -> list:
        return self.last_solution.get("predicted_positions", [])
