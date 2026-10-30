"""Independent rover safety supervisor.

Shared by ASTRA and the FSM baseline with identical thresholds. It does not import
or call any planner / response logic. It reads raw sensor-derived signals and the
estimator output and returns an action with reasons:
  continue | slow_down | replan | conserve_energy | safe_halt
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from autonomy.framework import SafetySupervisorBase
from shared.enums import SafetyAction


@dataclass
class SafetyConfig:
    collision_stop_m: float = 0.55        # obstacle range in forward sector -> halt
    collision_slow_m: float = 1.3
    max_tilt_deg: float = 24.0             # roll/pitch -> halt
    slow_tilt_deg: float = 16.0
    slip_slow: float = 0.45
    battery_reserve_soc: float = 0.15
    battery_warn_soc: float = 0.22
    sensor_stale_s: float = 1.5           # lidar unavailable -> blind speed limit
    blind_speed_factor: float = 0.35
    max_pos_sigma: float = 1.2            # estimator uncertainty -> halt
    slow_pos_sigma: float = 0.6
    min_wheel_capability: float = 0.15    # fraction of nominal per wheel
    geofence_half_m: float = 30.0
    geofence_margin_m: float = 1.2


class RoverSafetySupervisor(SafetySupervisorBase):
    def __init__(self, cfg: SafetyConfig):
        self.cfg = cfg
        self.violations: list[dict] = []
        self.last: dict = {"action": SafetyAction.CONTINUE.value, "reasons": [], "speed_cap": 1.0}

    def check(self, obs: dict) -> dict:
        c = self.cfg
        reasons, cap, action = [], 1.0, SafetyAction.CONTINUE
        def escalate(a: SafetyAction):
            nonlocal action
            order = [SafetyAction.CONTINUE, SafetyAction.SLOW_DOWN, SafetyAction.CONSERVE_ENERGY, SafetyAction.REPLAN, SafetyAction.SAFE_HALT]
            if order.index(a) > order.index(action):
                action = a
        fr = obs.get("front_range")
        if obs.get("lidar_stale", 0.0) > c.sensor_stale_s:
            cap = min(cap, c.blind_speed_factor); escalate(SafetyAction.SLOW_DOWN); reasons.append("lidar unavailable: blind speed limit")
        elif fr is not None:
            if fr < c.collision_stop_m:
                cap = 0.0; escalate(SafetyAction.REPLAN); reasons.append(f"obstacle at {fr:.2f} m")
            elif fr < c.collision_slow_m:
                cap = min(cap, 0.5); escalate(SafetyAction.SLOW_DOWN); reasons.append(f"obstacle at {fr:.2f} m")
        tilt = max(abs(obs.get("roll_deg", 0.0)), abs(obs.get("pitch_deg", 0.0)))
        if tilt > c.max_tilt_deg:
            cap = 0.0; escalate(SafetyAction.REPLAN); reasons.append(f"tilt {tilt:.1f}° > {c.max_tilt_deg}°")
        elif tilt > c.slow_tilt_deg:
            cap = min(cap, 0.5); escalate(SafetyAction.SLOW_DOWN); reasons.append(f"tilt {tilt:.1f}°")
        if obs.get("slip", 0.0) > c.slip_slow:
            cap = min(cap, 0.6); escalate(SafetyAction.SLOW_DOWN); reasons.append(f"wheel slip {obs['slip']:.2f}")
        soc = obs.get("soc", 1.0)
        if soc < c.battery_reserve_soc:
            cap = 0.0; escalate(SafetyAction.SAFE_HALT); reasons.append(f"battery {soc:.3f} below hard reserve")
        elif soc < c.battery_warn_soc:
            escalate(SafetyAction.CONSERVE_ENERGY); reasons.append(f"battery {soc:.3f} low")
        if obs.get("route_energy_infeasible"):
            escalate(SafetyAction.REPLAN); reasons.append("route energy exceeds reserve-limited budget")
        sig = obs.get("pos_sigma", 0.0)
        if sig > c.max_pos_sigma:
            cap = 0.0; escalate(SafetyAction.SAFE_HALT); reasons.append(f"position sigma {sig:.2f} m")
        elif sig > c.slow_pos_sigma:
            cap = min(cap, 0.5); escalate(SafetyAction.SLOW_DOWN); reasons.append(f"position sigma {sig:.2f} m")
        pos = obs.get("position")
        if pos is not None and max(abs(pos[0]), abs(pos[1])) > c.geofence_half_m - c.geofence_margin_m:
            cap = 0.0; escalate(SafetyAction.REPLAN); reasons.append("operational-area geofence")
        cap_w = obs.get("wheel_capability")
        if cap_w is not None and np.min(cap_w) < c.min_wheel_capability:
            cap = min(cap, 0.6); escalate(SafetyAction.SLOW_DOWN); reasons.append("wheel capability critically low")
        self.last = {"action": action.value, "reasons": reasons, "speed_cap": cap}
        return self.last
