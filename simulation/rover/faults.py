"""Fault injectors for the four primary fault classes (closed taxonomy).

Each injector modifies the *simulated world or sensors*; none of them tells the
autonomy stack that a fault exists. Schedules are explicit and identical across
matched trials.
  sensor_dropout            params: sensors ['lidar','camera'], mode 'missing'|'corrupted'
  terrain_misclassification params: fraction (default 0.15)
  power_drain               params: factor (default 3.0), parasitic_w (default 60)
  actuator_degradation      params: wheel (0..5, default 0 = front-left), torque_factor (default 0.3)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shared.enums import FaultType

DEFAULT_PARAMS = {
    FaultType.SENSOR_DROPOUT.value: {"sensors": ["lidar", "camera"], "mode": "missing"},
    FaultType.TERRAIN_MISCLASSIFICATION.value: {"fraction": 0.15},
    FaultType.POWER_DRAIN.value: {"factor": 3.0, "parasitic_w": 60.0},
    FaultType.ACTUATOR_DEGRADATION.value: {"wheel": 0, "torque_factor": 0.3},
}


@dataclass
class FaultSpec:
    fault_type: str
    start: float = 15.0
    duration: float | None = None          # None = persists to end of mission
    params: dict = field(default_factory=dict)
    active: bool = False
    done: bool = False

    def __post_init__(self):
        FaultType(self.fault_type)         # validates against the closed taxonomy
        self.params = {**DEFAULT_PARAMS[self.fault_type], **(self.params or {})}

    def to_dict(self):
        return {"fault_type": self.fault_type, "start": self.start, "duration": self.duration, "params": self.params,
                "active": self.active, "done": self.done}


class FaultInjector:
    def __init__(self, specs: list[FaultSpec], sensors, battery, actuator_factor):
        self.specs = specs
        self.sensors = sensors
        self.battery = battery
        self.actuator_factor = actuator_factor     # np.ndarray shared with the mission (true torque capability)
        self.log: list[dict] = []

    def _apply(self, s: FaultSpec, on: bool):
        p = s.params
        if s.fault_type == FaultType.SENSOR_DROPOUT.value:
            for name in p["sensors"]:
                self.sensors.dropout[name] = on
            self.sensors.dropout_mode = p["mode"]
        elif s.fault_type == FaultType.TERRAIN_MISCLASSIFICATION.value:
            self.sensors.misclass_fraction = p["fraction"] if on else 0.0
        elif s.fault_type == FaultType.POWER_DRAIN.value:
            self.battery.drain_factor = p["factor"] if on else 1.0
            self.battery.parasitic_w = p["parasitic_w"] if on else 0.0
        elif s.fault_type == FaultType.ACTUATOR_DEGRADATION.value:
            self.actuator_factor[int(p["wheel"])] = p["torque_factor"] if on else 1.0

    def update(self, t: float) -> list[dict]:
        out = []
        for s in self.specs:
            if not s.active and not s.done and t >= s.start:
                s.active = True
                self._apply(s, True)
                out.append({"t": t, "fault_type": s.fault_type, "phase": "injected", "params": s.params})
            elif s.active and s.duration is not None and t >= s.start + s.duration:
                s.active, s.done = False, True
                self._apply(s, False)
                out.append({"t": t, "fault_type": s.fault_type, "phase": "cleared"})
        self.log.extend(out)
        return out

    def inject_now(self, t: float, fault_type: str, duration: float | None, params: dict) -> FaultSpec:
        s = FaultSpec(fault_type, start=t, duration=duration, params=params)
        self.specs.append(s)
        return s

    def active_types(self) -> list[str]:
        return [s.fault_type for s in self.specs if s.active]
