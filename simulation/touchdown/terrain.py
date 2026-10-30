"""Landing-region terrain: ground truth.

The true terrain is a height field plus a discrete rock population. Rocks are
kept as a list (rather than rasterised) because they are smaller than the grid
cell size and matter for footprint clearance. The *perceived* terrain is built
separately by ``autonomy/planning/landing_perception.py`` from simulated
sensing and is the only terrain the autonomy stack may read.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TerrainConfig:
    size_m: float = 2000.0
    resolution_m: float = 4.0
    roughness_m: float = 6.0          # amplitude of fractal relief
    regional_slope_deg: float = 1.5
    n_craters: int = 14
    rock_density_per_km2: float = 900.0
    hazard_at_target: bool = False    # place a hidden boulder field at the target (demo / diversion test)
    target: list[float] = field(default_factory=lambda: [0.0, 0.0])


@dataclass
class Rock:
    x: float
    y: float
    radius: float
    height: float


class Terrain:
    def __init__(self, cfg: TerrainConfig, rng: np.random.Generator):
        self.cfg = cfg
        n = int(cfg.size_m / cfg.resolution_m) + 1
        self.n = n
        self.res = cfg.resolution_m
        self.origin = -cfg.size_m / 2.0
        self.xs = self.origin + np.arange(n) * self.res
        self.heights = self._generate_relief(rng)
        self.craters: list[tuple[float, float, float]] = []
        self._add_craters(rng)
        self.rocks: list[Rock] = []
        self._add_rocks(rng)
        if cfg.hazard_at_target:
            self.add_hazard_field(cfg.target[0], cfg.target[1], radius=30.0, rng=rng)
        self._update_slope()

    # -- generation -----------------------------------------------------
    def _generate_relief(self, rng) -> np.ndarray:
        n = self.n
        noise = rng.normal(size=(n, n))
        fx = np.fft.fftfreq(n)[:, None]
        fy = np.fft.fftfreq(n)[None, :]
        f = np.sqrt(fx ** 2 + fy ** 2)
        f[0, 0] = 1.0
        spectrum = np.fft.fft2(noise) / f ** 1.9        # ~fractal (Brownian-like) relief
        spectrum[0, 0] = 0
        h = np.real(np.fft.ifft2(spectrum))
        h = (h - h.mean()) / (h.std() + 1e-9) * self.cfg.roughness_m
        X, Y = np.meshgrid(self.xs, self.xs, indexing="ij")
        h += np.tan(np.radians(self.cfg.regional_slope_deg)) * (0.7 * X + 0.3 * Y)
        return h

    def _add_craters(self, rng) -> None:
        X, Y = np.meshgrid(self.xs, self.xs, indexing="ij")
        tx, ty = self.cfg.target
        for _ in range(self.cfg.n_craters):
            r = float(rng.uniform(15, 90))
            for _try in range(20):
                cx, cy = rng.uniform(self.origin + 100, -self.origin - 100, 2)
                if np.hypot(cx - tx, cy - ty) > r + 60:   # keep nominal target outside large craters
                    break
            depth = 0.2 * r
            d = np.hypot(X - cx, Y - cy) / r
            bowl = np.where(d < 1.0, depth * (d ** 2 - 1.0), 0.0)
            rim = 0.06 * r * np.exp(-((d - 1.0) / 0.25) ** 2)
            self.heights += bowl + rim
            self.craters.append((float(cx), float(cy), r))

    def _add_rocks(self, rng) -> None:
        area_km2 = (self.cfg.size_m / 1000.0) ** 2
        count = rng.poisson(self.cfg.rock_density_per_km2 * area_km2)
        # Pareto-like size distribution: many small rocks, few boulders
        radii = 0.15 * (1.0 + rng.pareto(2.5, count))
        radii = np.clip(radii, 0.15, 3.0)
        # cluster a fraction of rocks around crater rims (ejecta)
        for i in range(count):
            if self.craters and rng.random() < 0.4:
                cx, cy, r = self.craters[rng.integers(len(self.craters))]
                ang = rng.uniform(0, 2 * np.pi)
                dist = r * rng.uniform(0.9, 1.8)
                x, y = cx + dist * np.cos(ang), cy + dist * np.sin(ang)
            else:
                x, y = rng.uniform(self.origin, -self.origin, 2)
            rr = float(radii[i])
            self.rocks.append(Rock(float(x), float(y), rr, rr * float(rng.uniform(0.6, 1.2))))

    def add_hazard_field(self, x: float, y: float, radius: float, rng: np.random.Generator) -> None:
        """Boulder field (hazard that is only discoverable by close-range sensing)."""
        n = int(25 + radius)
        for _ in range(n):
            a = rng.uniform(0, 2 * np.pi)
            d = radius * np.sqrt(rng.random())
            rr = float(rng.uniform(0.5, 1.6))
            self.rocks.append(Rock(float(x + d * np.cos(a)), float(y + d * np.sin(a)), rr, rr * 0.9))
        self._rock_arr = None

    def _update_slope(self) -> None:
        gx, gy = np.gradient(self.heights, self.res)
        self.slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))
        self._rock_arr = None

    # -- queries --------------------------------------------------------
    def height(self, x: float, y: float) -> float:
        """Bilinear interpolation of the height field (clamped at borders)."""
        fx = (x - self.origin) / self.res
        fy = (y - self.origin) / self.res
        fx = min(max(fx, 0.0), self.n - 1.001)
        fy = min(max(fy, 0.0), self.n - 1.001)
        i, j = int(fx), int(fy)
        dx, dy = fx - i, fy - j
        h = self.heights
        return float((1 - dx) * (1 - dy) * h[i, j] + dx * (1 - dy) * h[i + 1, j]
                     + (1 - dx) * dy * h[i, j + 1] + dx * dy * h[i + 1, j + 1])

    def gradient(self, x: float, y: float) -> tuple[float, float]:
        e = self.res * 0.5
        return ((self.height(x + e, y) - self.height(x - e, y)) / (2 * e),
                (self.height(x, y + e) - self.height(x, y - e)) / (2 * e))

    def slope_at(self, x: float, y: float, radius: float = 4.0) -> float:
        """Plane-fit slope [deg] over a footprint of given radius."""
        pts = []
        for ang in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            px, py = x + radius * np.cos(ang), y + radius * np.sin(ang)
            pts.append((px, py, self.height(px, py)))
        pts.append((x, y, self.height(x, y)))
        A = np.array([[p[0], p[1], 1.0] for p in pts])
        z = np.array([p[2] for p in pts])
        coef, *_ = np.linalg.lstsq(A, z, rcond=None)
        return float(np.degrees(np.arctan(np.hypot(coef[0], coef[1]))))

    def rock_array(self) -> np.ndarray:
        if getattr(self, "_rock_arr", None) is None:
            self._rock_arr = np.array([[r.x, r.y, r.radius, r.height] for r in self.rocks]) if self.rocks else np.zeros((0, 4))
        return self._rock_arr

    def rocks_near(self, x: float, y: float, radius: float) -> np.ndarray:
        arr = self.rock_array()
        if arr.size == 0:
            return arr
        d = np.hypot(arr[:, 0] - x, arr[:, 1] - y)
        return arr[d < radius + arr[:, 2]]

    def summary(self) -> dict:
        return {"size_m": self.cfg.size_m, "resolution_m": self.res, "n": self.n, "origin": self.origin,
                "n_rocks": len(self.rocks), "craters": self.craters}

    def downsampled(self, step: int = 5) -> dict:
        """Height grid for visualisation (not used by autonomy)."""
        return {"origin": self.origin, "resolution_m": self.res * step,
                "heights": np.round(self.heights[::step, ::step], 2).tolist()}


def heights_at(terrain: "Terrain", xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Vectorised bilinear height lookup."""
    fx = np.clip((xs - terrain.origin) / terrain.res, 0.0, terrain.n - 1.001)
    fy = np.clip((ys - terrain.origin) / terrain.res, 0.0, terrain.n - 1.001)
    i = fx.astype(int); j = fy.astype(int)
    dx = fx - i; dy = fy - j
    h = terrain.heights
    return ((1 - dx) * (1 - dy) * h[i, j] + dx * (1 - dy) * h[i + 1, j]
            + (1 - dx) * dy * h[i, j + 1] + dx * dy * h[i + 1, j + 1])
