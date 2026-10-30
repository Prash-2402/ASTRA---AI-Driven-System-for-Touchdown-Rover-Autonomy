"""Six-degree-of-freedom lander rigid-body model.

State vector (14):  p[3] (world ENU, m) | v[3] (m/s) | q[4] (body->world) | w[3] (body rad/s) | m_fuel (kg)

Equations of motion (see docs/TOUCHDOWN_PHYSICS.md):
  p' = v
  v' = ( R(q) F_body_thrust + F_aero + F_dist ) / m  +  g
  q' = 0.5 q ⊗ [0, w]
  w' = I^-1 ( tau - w × I w )
  m_fuel' = - (|T_main| + |T_lat|_1) / (Isp g0)  - |tau|_1 / (arm Isp g0)

Actuators follow first-order lags toward commanded values; the *achieved*
actuator outputs (not the commands) enter the dynamics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from simulation.common.math3d import quat_derivative, quat_normalize, quat_to_euler, quat_to_rotmat, rk4_step
from simulation.touchdown.environment import G0, Atmosphere


@dataclass
class LanderParams:
    dry_mass: float = 1100.0            # kg
    fuel_mass: float = 450.0            # kg (initial)
    max_thrust: float = 10_000.0        # N, main engine (body +z)
    min_throttle: float = 0.15          # deep-throttling lower bound when lit
    isp: float = 225.0                  # s
    max_lateral_thrust: float = 500.0   # N per body axis (x, y)
    max_torque: list[float] = field(default_factory=lambda: [700.0, 700.0, 350.0])  # N m
    rcs_arm: float = 1.5                # m, lever arm for RCS fuel accounting
    inertia_full: list[float] = field(default_factory=lambda: [1900.0, 1900.0, 2300.0])  # kg m^2 at full mass
    drag_cd: float = 1.2
    ref_area: float = 7.0               # m^2
    throttle_tau: float = 0.12          # s
    rcs_tau: float = 0.05               # s
    footprint_radius: float = 2.2       # m (pad circle)
    leg_height: float = 1.2             # m, CoM height above pad plane

    @property
    def wet_mass(self) -> float:
        return self.dry_mass + self.fuel_mass


@dataclass
class ActuatorCommand:
    throttle: float = 0.0                                   # [0, 1]; 0 = engine off
    lateral: np.ndarray = field(default_factory=lambda: np.zeros(2))   # [-1, 1] body x, y
    torque: np.ndarray = field(default_factory=lambda: np.zeros(3))    # [-1, 1] body x, y, z

    def clipped(self, p: LanderParams) -> "ActuatorCommand":
        th = float(np.clip(self.throttle, 0.0, 1.0))
        if 0.0 < th < p.min_throttle:
            th = p.min_throttle
        return ActuatorCommand(th, np.clip(self.lateral, -1, 1), np.clip(self.torque, -1, 1))

    def to_dict(self) -> dict:
        return {"throttle": float(self.throttle), "lateral": np.asarray(self.lateral).tolist(),
                "torque": np.asarray(self.torque).tolist()}


class Lander:
    def __init__(self, params: LanderParams, p0, v0, q0, w0=None):
        self.p = params
        self.x = np.zeros(14)
        self.x[0:3] = p0
        self.x[3:6] = v0
        self.x[6:10] = quat_normalize(np.asarray(q0, dtype=float))
        self.x[10:13] = np.zeros(3) if w0 is None else w0
        self.x[13] = params.fuel_mass
        # achieved actuator state
        self.throttle = 0.0
        self.lateral = np.zeros(2)
        self.torque = np.zeros(3)
        self.ext_force = np.zeros(3)      # injected disturbance, world frame [N]
        self.last_accel = np.zeros(3)
        self.last_ang_accel = np.zeros(3)
        self.fuel_used = 0.0
        self._gravity = 0.0

    # -- convenience accessors --------------------------------------------------
    @property
    def pos(self): return self.x[0:3]
    @property
    def vel(self): return self.x[3:6]
    @property
    def quat(self): return self.x[6:10]
    @property
    def omega(self): return self.x[10:13]
    @property
    def fuel(self): return float(self.x[13])
    @property
    def mass(self): return self.p.dry_mass + max(self.fuel, 0.0)

    def inertia(self, mass: float) -> np.ndarray:
        # inertia scaled with total mass (propellant assumed co-located with CoM; documented simplification)
        return np.asarray(self.p.inertia_full) * (mass / self.p.wet_mass)

    # -- dynamics ---------------------------------------------------------------
    def _forces(self, x: np.ndarray, atm: Atmosphere, gravity: float, terrain_h: float):
        p = self.p
        fuel = max(x[13], 0.0)
        mass = p.dry_mass + fuel
        R = quat_to_rotmat(quat_normalize(x[6:10]))
        lit = fuel > 0.0
        thr = self.throttle if lit else 0.0
        lat = self.lateral if lit else np.zeros(2)
        tq = self.torque if lit else np.zeros(3)
        f_body = np.array([lat[0] * p.max_lateral_thrust, lat[1] * p.max_lateral_thrust, thr * p.max_thrust])
        f_thrust_world = R @ f_body
        alt = x[2] - terrain_h
        v_rel = x[3:6] - atm.wind()
        rho = atm.density(x[2])
        f_aero = -0.5 * rho * p.drag_cd * p.ref_area * np.linalg.norm(v_rel) * v_rel
        torque = tq * np.asarray(p.max_torque)
        mdot = 0.0
        if lit:
            mdot = (abs(f_body[2]) + abs(f_body[0]) + abs(f_body[1])) / (p.isp * G0)
            mdot += np.sum(np.abs(torque)) / (p.rcs_arm * p.isp * G0)
        return mass, f_thrust_world, f_aero, torque, mdot, alt

    def derivative(self, x: np.ndarray, atm: Atmosphere, gravity: float, terrain_h: float) -> np.ndarray:
        mass, f_thr, f_aero, torque, mdot, _ = self._forces(x, atm, gravity, terrain_h)
        dx = np.zeros(14)
        dx[0:3] = x[3:6]
        dx[3:6] = (f_thr + f_aero + self.ext_force) / mass + np.array([0.0, 0.0, -gravity])
        dx[6:10] = quat_derivative(x[6:10], x[10:13])
        I = self.inertia(mass)
        w = x[10:13]
        Iw = I * w
        wxIw = np.array([w[1] * Iw[2] - w[2] * Iw[1], w[2] * Iw[0] - w[0] * Iw[2], w[0] * Iw[1] - w[1] * Iw[0]])
        dx[10:13] = (torque - wxIw) / I
        dx[13] = -mdot
        return dx

    def step(self, cmd: ActuatorCommand, dt: float, atm: Atmosphere, gravity: float, terrain_h: float) -> None:
        self._gravity = gravity
        c = cmd.clipped(self.p)
        # first-order actuator lag, exact discretisation over dt
        a_t = 1 - np.exp(-dt / self.p.throttle_tau)
        a_r = 1 - np.exp(-dt / self.p.rcs_tau)
        self.throttle += a_t * (c.throttle - self.throttle)
        if c.throttle == 0.0 and self.throttle < self.p.min_throttle * 0.5:
            self.throttle = 0.0
        self.lateral = self.lateral + a_r * (c.lateral - self.lateral)
        self.torque = self.torque + a_r * (c.torque - self.torque)

        fuel_before = self.fuel
        f = lambda _t, x: self.derivative(x, atm, gravity, terrain_h)
        x_new = rk4_step(f, 0.0, self.x, dt)
        x_new[6:10] = quat_normalize(x_new[6:10])
        x_new[13] = max(x_new[13], 0.0)
        d = self.derivative(x_new, atm, gravity, terrain_h)
        self.last_accel = d[3:6]
        self.last_ang_accel = d[10:13]
        self.x = x_new
        self.fuel_used += fuel_before - self.fuel

    def specific_force_body(self) -> np.ndarray:
        """What an ideal accelerometer measures: (a - g) expressed in body frame."""
        R = quat_to_rotmat(self.quat)
        return R.T @ (self.last_accel - np.array([0.0, 0.0, -self._gravity]))

    def euler(self) -> np.ndarray:
        return quat_to_euler(self.quat)

    def tilt_deg(self) -> float:
        R = quat_to_rotmat(self.quat)
        return float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1))))

    def state_dict(self) -> dict:
        return {"position": self.pos.tolist(), "velocity": self.vel.tolist(), "quaternion": self.quat.tolist(),
                "euler": self.euler().tolist(), "omega": self.omega.tolist(), "mass": self.mass,
                "fuel": self.fuel, "acceleration": self.last_accel.tolist(),
                "angular_acceleration": self.last_ang_accel.tolist(), "throttle": self.throttle,
                "lateral": self.lateral.tolist(), "torque": self.torque.tolist(), "tilt_deg": self.tilt_deg()}
