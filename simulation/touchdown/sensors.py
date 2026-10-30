"""Touchdown sensor suite. Ground truth -> timestamped noisy measurements.

Channels (defaults, overridable per mission):
  imu_accel  100 Hz  body specific force      [m/s^2]
  imu_gyro   100 Hz  body angular rate        [rad/s]
  altimeter   20 Hz  radar range along local vertical to terrain (AGL) [m], valid < 6 km
  velocimeter 10 Hz  Doppler velocity (world)  [m/s], valid < 4 km
  position     2 Hz  terrain-relative navigation fix (world) [m]
  attitude    10 Hz  star-tracker Euler angles [rad]
  fuel         1 Hz  propellant gauge [kg]
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from simulation.common.rng import SeedManager
from simulation.common.sensor_model import Measurement, SensorChannel, SensorSpec


def default_specs() -> dict[str, SensorSpec]:
    return {
        "imu_accel": SensorSpec(rate_hz=100, noise_std=0.03, bias=[0.02, -0.015, 0.01], bias_walk_std=0.0005),
        "imu_gyro": SensorSpec(rate_hz=100, noise_std=0.0015, bias=0.0002),
        "altimeter": SensorSpec(rate_hz=20, noise_std=0.6, dropout_prob=0.01),
        "velocimeter": SensorSpec(rate_hz=10, noise_std=0.12, dropout_prob=0.01),
        "position": SensorSpec(rate_hz=2, noise_std=[4.0, 4.0, 6.0], delay_s=0.1, dropout_prob=0.02),
        "attitude": SensorSpec(rate_hz=10, noise_std=0.002),
        "fuel": SensorSpec(rate_hz=1, noise_std=1.5),
    }

DIMS = {"imu_accel": 3, "imu_gyro": 3, "altimeter": 1, "velocimeter": 3, "position": 3, "attitude": 3, "fuel": 1}
MAX_RANGE = {"altimeter": 6000.0, "velocimeter": 4000.0}


@dataclass
class SensorConfig:
    overrides: dict[str, dict] = field(default_factory=dict)   # channel -> SensorSpec field overrides


class LanderSensorSuite:
    def __init__(self, cfg: SensorConfig, seeds: SeedManager):
        specs = default_specs()
        for ch, ov in cfg.overrides.items():
            if ch in specs:
                for k, v in ov.items():
                    setattr(specs[ch], k, v)
        self.channels = {name: SensorChannel(name, spec, seeds.stream(f"sensor:{name}"), DIMS[name])
                         for name, spec in specs.items()}
        self.drift: dict[str, dict] = {}       # channel -> {"rate", "t0", "axis"}: the "lying sensor" fault

    def set_drift(self, channel: str, rate: float, t0: float, axis: int | None = None) -> dict:
        """Slowly growing bias (rate x time since onset). The sensor keeps its noise, rate and validity flag:
        nothing about an individual reading looks wrong."""
        axis = (0 if DIMS[channel] == 1 else 2) if axis is None else axis
        self.drift[channel] = {"rate": float(rate), "t0": float(t0), "axis": int(axis)}
        return self.drift[channel]

    def drift_bias(self, channel: str, t: float) -> float:
        d = self.drift.get(channel)
        return 0.0 if d is None or t < d["t0"] else d["rate"] * (t - d["t0"])

    def sample(self, t: float, lander, agl: float) -> list[Measurement]:
        truth = {
            "imu_accel": lander.specific_force_body(),
            "imu_gyro": lander.omega.copy(),
            "altimeter": np.array([agl]),
            "velocimeter": lander.vel.copy(),
            "position": lander.pos.copy(),
            "attitude": lander.euler(),
            "fuel": np.array([lander.fuel]),
        }
        out = []
        for name, ch in self.channels.items():
            for m in ch.sample(t, truth[name]):
                if name in MAX_RANGE and agl > MAX_RANGE[name]:
                    m.value, m.valid = None, False
                if m.valid and m.value is not None and name in self.drift:
                    v = np.array(m.value, float)
                    v[self.drift[name]["axis"]] += self.drift_bias(name, t)
                    m.value = v
                out.append(m)
        return out

    def set_degradation(self, channel: str, factor: float) -> None:
        self.channels[channel].spec.degradation = factor

    def set_dropout(self, channel: str, on: bool) -> None:
        self.channels[channel].forced_dropout = on
