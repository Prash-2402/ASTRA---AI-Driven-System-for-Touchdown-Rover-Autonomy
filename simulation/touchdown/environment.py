"""Mars planetary environment for ASTRA TOUCHDOWN.

Single consistent body: Mars. Sources (documented in docs/TOUCHDOWN_PHYSICS.md):
  * NASA GSFC Mars Fact Sheet: g = 3.71 m/s^2 (equatorial 3.72076), mean radius 3389.5 km
  * Surface density ~0.020 kg/m^3, scale height ~11.1 km (exponential model)
Local frame: flat East-North-Up (ENU) tangent plane centred on the landing
region; at the altitudes simulated (<~10 km) curvature error is < 0.02 %.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MARS_GRAVITY = 3.72076          # m/s^2
MARS_RADIUS = 3_389_500.0       # m
MARS_RHO0 = 0.020               # kg/m^3 at datum
MARS_SCALE_HEIGHT = 11_100.0    # m
G0 = 9.80665                    # standard gravity for Isp conversion


@dataclass
class PlanetConfig:
    gravity: float = MARS_GRAVITY
    radius: float = MARS_RADIUS
    rho0: float = MARS_RHO0
    scale_height: float = MARS_SCALE_HEIGHT
    surface_elevation: float = 0.0              # datum offset of terrain [m]
    wind: list[float] = field(default_factory=lambda: [4.0, -2.0, 0.0])   # mean wind, world [m/s]
    gust_std: float = 1.5                       # OU gust std [m/s]
    gust_tau: float = 3.0                       # OU correlation time [s]


class Atmosphere:
    def __init__(self, cfg: PlanetConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.gust = np.zeros(3)
        self.extra_wind = np.zeros(3)       # injectable disturbance

    def density(self, altitude: float) -> float:
        return self.cfg.rho0 * float(np.exp(-max(altitude, 0.0) / self.cfg.scale_height))

    def step(self, dt: float) -> None:
        """Ornstein-Uhlenbeck gust process (horizontal components)."""
        tau, s = self.cfg.gust_tau, self.cfg.gust_std
        a = np.exp(-dt / tau)
        noise = self.rng.normal(0, s * np.sqrt(1 - a * a), 3)
        noise[2] *= 0.3
        self.gust = a * self.gust + noise

    def wind(self) -> np.ndarray:
        return np.asarray(self.cfg.wind, dtype=float) + self.gust + self.extra_wind
