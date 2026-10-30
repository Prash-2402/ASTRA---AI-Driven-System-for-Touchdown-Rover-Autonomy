"""Lunar Module-class lander dynamics (separate from the Mars lander model).

State (13): p[3] (m), v[3] (m/s), pitch theta, roll phi (rad), pitch rate q, roll rate r (rad/s), mass m (kg)
Thrust axis in the world frame: d = [sin(theta) cos(phi), -sin(phi), cos(theta) cos(phi)]
  p' = v
  v' = (T d) / m + [0, 0, -g_moon]                       (no atmosphere: no drag)
  theta'' = tau_theta / I_yy ,  phi'' = tau_phi / I_xx   (two-axis rigid attitude, RCS torques)
  m' = -T / (Isp g0) - |tau| / (r_rcs Isp_rcs g0)
Integrated with RK4 at 50 Hz. Parameters follow the Apollo LM Descent Propulsion System (DPS):
max thrust 45.04 kN, Isp 311 s, throttle range 10 %-92.5 % (the real engine avoided 65-92.5 %; here continuous -
documented simplification); RCS: 16 x 445 N thrusters, ~1.7 m moment arm, Isp 290 s.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.moon.environment import G0, MOON_GRAVITY


@dataclass
class LunarLanderParams:
    dry_mass: float = 6_600.0          # descent stage dry + ascent stage (wet) at high gate, kg
    propellant: float = 1_900.0        # descent propellant remaining at high gate, kg
    max_thrust: float = 45_040.0
    min_throttle: float = 0.10
    max_throttle: float = 0.925
    isp: float = 311.0
    rcs_thrust: float = 445.0
    rcs_arm: float = 1.7
    rcs_isp: float = 290.0
    inertia_pitch: float = 28_000.0
    inertia_roll: float = 25_000.0
    throttle_tau: float = 0.25          # DPS throttle response, s
    probe_length: float = 1.73          # lunar surface sensing probes below footpads
    leg_height: float = 2.3             # CoM height above footpad plane, m
    footprint_radius: float = 4.6       # footpad circle radius, m

    @property
    def max_torque(self) -> float:
        return 2 * self.rcs_thrust * self.rcs_arm   # two thrusters per axis couple


class LunarLander:
    def __init__(self, p: LunarLanderParams, pos, vel, pitch=0.0, roll=0.0):
        self.p = p
        self.x = np.zeros(11)
        self.x[0:3] = pos; self.x[3:6] = vel; self.x[6] = pitch; self.x[7] = roll
        self.x[10] = p.dry_mass + p.propellant
        self.throttle = 0.0
        self.tau = np.zeros(2)
        self.engine_on = True
        self.last_accel = np.zeros(3)

    @property
    def pos(self): return self.x[0:3]
    @property
    def vel(self): return self.x[3:6]
    @property
    def mass(self): return float(self.x[10])
    @property
    def propellant(self): return max(self.mass - self.p.dry_mass, 0.0)

    def thrust_dir(self, x=None) -> np.ndarray:
        x = self.x if x is None else x
        th, ph = x[6], x[7]
        return np.array([np.sin(th) * np.cos(ph), -np.sin(ph), np.cos(th) * np.cos(ph)])

    def thrust(self, x=None) -> float:
        x = self.x if x is None else x
        if not self.engine_on or x[10] <= self.p.dry_mass:
            return 0.0
        return self.throttle * self.p.max_thrust

    def deriv(self, x: np.ndarray) -> np.ndarray:
        p = self.p
        T = self.thrust(x)
        d = self.thrust_dir(x)
        tau = self.tau if x[10] > p.dry_mass else np.zeros(2)
        dx = np.zeros(11)
        dx[0:3] = x[3:6]
        dx[3:6] = T * d / x[10] + np.array([0.0, 0.0, -MOON_GRAVITY])
        dx[6] = x[8]; dx[7] = x[9]
        dx[8] = tau[0] / p.inertia_pitch; dx[9] = tau[1] / p.inertia_roll
        dx[10] = -T / (p.isp * G0) - np.sum(np.abs(tau)) / (p.rcs_arm * p.rcs_isp * G0)
        return dx

    def step(self, throttle_cmd: float, tau_cmd: np.ndarray, dt: float) -> None:
        p = self.p
        cmd = 0.0 if not self.engine_on else float(np.clip(throttle_cmd, p.min_throttle, p.max_throttle))
        self.throttle += (1 - np.exp(-dt / p.throttle_tau)) * (cmd - self.throttle)
        self.tau = np.clip(tau_cmd, -p.max_torque, p.max_torque)
        x = self.x
        k1 = self.deriv(x); k2 = self.deriv(x + dt / 2 * k1); k3 = self.deriv(x + dt / 2 * k2); k4 = self.deriv(x + dt * k3)
        self.x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        self.x[10] = max(self.x[10], p.dry_mass)
        self.last_accel = self.deriv(self.x)[3:6]
