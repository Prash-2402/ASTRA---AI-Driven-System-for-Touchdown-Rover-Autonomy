"""Battery and power model.

Electrical demand:  P = sum_i max(tau_i w_i, 0) / eta + k_cu * sum_i tau_i^2 + P_elec
Battery:            V = V_oc(SoC) - I R_int,   V_oc = V_empty + (V_full - V_empty) SoC
                    I solves  P = (V_oc - I R) I   (smaller root)
                    dSoC/dt = - P_actual / (3600 * C_Wh)
The POWER_DRAIN fault multiplies actual consumption and adds a parasitic load
(e.g. a shorted heater) - it changes the physics, not just the reported value.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BatteryConfig:
    capacity_wh: float = 20.0          # energy allocated to this traverse
    initial_soc: float = 0.6
    v_full: float = 28.0
    v_empty: float = 23.0
    r_internal: float = 0.08
    motor_efficiency: float = 0.72
    copper_loss_k: float = 0.004       # W per (N m)^2
    electronics_w: float = 22.0
    reserve_soc: float = 0.15          # hard reserve used by the safety supervisor


class Battery:
    def __init__(self, cfg: BatteryConfig):
        self.cfg = cfg
        self.soc = cfg.initial_soc
        self.drain_factor = 1.0
        self.parasitic_w = 0.0
        self.voltage = self.v_oc()
        self.current = 0.0
        self.power = 0.0
        self.motor_power = 0.0
        self.energy_used_wh = 0.0

    def v_oc(self) -> float:
        c = self.cfg
        return c.v_empty + (c.v_full - c.v_empty) * max(self.soc, 0.0)

    def demand(self, torques: np.ndarray, speeds: np.ndarray) -> float:
        c = self.cfg
        mech = np.maximum(torques * speeds, 0.0).sum() / c.motor_efficiency
        return float(mech + c.copper_loss_k * np.sum(torques ** 2) + c.electronics_w)

    def step(self, torques: np.ndarray, speeds: np.ndarray, dt: float) -> None:
        c = self.cfg
        p_nom = self.demand(torques, speeds)
        self.motor_power = p_nom - c.electronics_w
        p = p_nom * self.drain_factor + self.parasitic_w
        voc = self.v_oc()
        disc = voc * voc - 4 * c.r_internal * p
        i = (voc - np.sqrt(max(disc, 0.0))) / (2 * c.r_internal)
        self.current, self.voltage, self.power = float(i), float(voc - i * c.r_internal), float(p)
        e = p * dt / 3600.0
        self.energy_used_wh += e
        self.soc = max(self.soc - e / c.capacity_wh, 0.0)

    @property
    def remaining_wh(self) -> float:
        return self.soc * self.cfg.capacity_wh
