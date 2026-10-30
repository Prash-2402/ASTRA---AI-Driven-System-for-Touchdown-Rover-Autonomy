"""Fixed rule-based Finite State Machine baseline.

Same EKF state, sensors, perceived map, planner (A* with DEFAULT weights), motion
controller, safety supervisor and anomaly detector as ASTRA. What it lacks is
fault classification and fault-specific adaptive replanning. Rules are fixed:
  NOMINAL       follow the current route at full speed; replan only when the route is blocked
  DEGRADED      any anomaly flag -> fixed 50 % speed, keep the route
  SENSOR_WAIT   lidar or camera unavailable -> stop and wait for sensors (safe-halt after 60 s)
  HALT          battery below a fixed threshold (supervisor reserve + 0.03) -> safe-halt
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FSMConfig:
    degraded_speed: float = 0.5
    sensor_wait_timeout: float = 60.0
    battery_halt_soc: float = 0.18


class FSMBaseline:
    def __init__(self, cfg: FSMConfig | None = None):
        self.cfg = cfg or FSMConfig()
        self.state = "NOMINAL"
        self.wait_since: float | None = None
        self.transitions: list[dict] = []

    def _go(self, s: str, t: float, why: str):
        if s != self.state:
            self.transitions.append({"t": round(t, 2), "from": self.state, "to": s, "reason": why})
            self.state = s

    def decide(self, t: float, anomaly: dict, ev, soc: float) -> dict:
        c = self.cfg
        if self.state == "HALT":
            return {"speed_factor": 0.0, "halt": True, "state": self.state}
        if soc < c.battery_halt_soc:
            self._go("HALT", t, f"battery {soc:.3f} < fixed threshold {c.battery_halt_soc}")
            return {"speed_factor": 0.0, "halt": True, "state": self.state}
        sensors_out = ev.lidar_stale > 1.2 or ev.camera_stale > 1.2
        if sensors_out:
            if self.state != "SENSOR_WAIT":
                self.wait_since = t
            self._go("SENSOR_WAIT", t, "lidar/camera unavailable")
            if t - (self.wait_since or t) > c.sensor_wait_timeout:
                self._go("HALT", t, "sensor wait timeout")
                return {"speed_factor": 0.0, "halt": True, "state": self.state}
            return {"speed_factor": 0.0, "halt": False, "state": self.state}
        if anomaly["anomaly"]:
            self._go("DEGRADED", t, "anomaly flags: " + ",".join(anomaly["flags"]))
            return {"speed_factor": c.degraded_speed, "halt": False, "state": self.state}
        self._go("NOMINAL", t, "no anomaly")
        return {"speed_factor": 1.0, "halt": False, "state": self.state}
