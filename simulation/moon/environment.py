"""Lunar environment for the ASTRA Moon Landing module (independent of the Mars modules).

Constants (NASA GSFC Moon Fact Sheet): surface gravity 1.62 m/s^2 (1.625 used), mean radius 1737.4 km.
No atmosphere: no drag, no wind, ballistic dust. Local flat frame: x downrange, y crossrange, z up.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MOON_GRAVITY = 1.625
MOON_RADIUS = 1_737_400.0
G0 = 9.80665


@dataclass
class LunarTerrainConfig:
    length_m: float = 7000.0         # along-track extent (x from -6000 to +1000)
    width_m: float = 2400.0
    resolution_m: float = 10.0
    detail_size_m: float = 400.0     # high-resolution patch around the landing target
    detail_res_m: float = 1.0
    crater_density: float = 1.0      # multiplier on the power-law crater population
    boulders_near_target: int = 220
    target: list = field(default_factory=lambda: [0.0, 0.0])


def _fractal(rng, nx, ny, power):
    noise = rng.normal(size=(nx, ny))
    fx = np.fft.fftfreq(nx)[:, None]; fy = np.fft.fftfreq(ny)[None, :]
    f = np.sqrt(fx ** 2 + fy ** 2); f[0, 0] = 1
    s = np.fft.fft2(noise) / f ** power; s[0, 0] = 0
    h = np.real(np.fft.ifft2(s))
    return (h - h.mean()) / (h.std() + 1e-9)


def _crater_profile(d):
    """Normalised fresh simple-crater profile (depth/diameter ~0.2, raised rim, ejecta falloff)."""
    bowl = np.where(d < 1.0, (d ** 2 - 1.0), 0.0)
    rim = 0.18 * np.exp(-((d - 1.0) / 0.22) ** 2)
    ejecta = np.where(d > 1.0, 0.06 * d ** -3.0, 0.0)
    return bowl + rim + ejecta


class LunarTerrain:
    """Two-level height field: a coarse regional grid and a 1 m detail patch at the landing site."""

    def __init__(self, cfg: LunarTerrainConfig, rng: np.random.Generator):
        self.cfg = cfg
        L, W, r = cfg.length_m, cfg.width_m, cfg.resolution_m
        self.x0, self.y0 = -L + 1000.0, -W / 2
        self.nx, self.ny = int(L / r) + 1, int(W / r) + 1
        X, Y = np.meshgrid(self.x0 + np.arange(self.nx) * r, self.y0 + np.arange(self.ny) * r, indexing="ij")
        h = 6.0 * _fractal(rng, self.nx, self.ny, 2.1)
        self.craters = []
        # power-law crater size-frequency distribution N(>D) ~ D^-2
        n = int(380 * cfg.crater_density)
        D = 30.0 * (1 + rng.pareto(1.8, n))
        D = np.clip(D, 30.0, 900.0)
        tx, ty = cfg.target
        for d in D:
            cx = rng.uniform(self.x0, self.x0 + L); cy = rng.uniform(self.y0, self.y0 + W)
            if np.hypot(cx - tx, cy - ty) < d * 0.6 + 60:
                continue                 # keep the nominal target out of large craters
            R = d / 2
            dist = np.hypot(X - cx, Y - cy) / R
            m = dist < 4
            h[m] += 0.2 * d * _crater_profile(dist[m]) * (0.6 + 0.4 * rng.random())
            self.craters.append((float(cx), float(cy), float(R)))
        self.coarse = h
        # detail patch: small craters + regolith roughness + boulders
        S, dr = cfg.detail_size_m, cfg.detail_res_m
        self.dn = int(S / dr) + 1
        self.dx0, self.dy0 = tx - S / 2, ty - S / 2
        DX, DY = np.meshgrid(self.dx0 + np.arange(self.dn) * dr, self.dy0 + np.arange(self.dn) * dr, indexing="ij")
        base = self._coarse_at(DX, DY)
        fine = 0.35 * _fractal(rng, self.dn, self.dn, 1.8)
        for _ in range(140):
            d = float(np.clip(2.0 * (1 + rng.pareto(1.6)), 2.0, 45.0))
            cx, cy = rng.uniform(self.dx0, self.dx0 + S, 2)
            if np.hypot(cx - tx, cy - ty) < d / 2 + 12:
                continue
            dist = np.hypot(DX - cx, DY - cy) / (d / 2)
            m = dist < 3
            fine[m] += 0.2 * d * _crater_profile(dist[m])
            self.craters.append((float(cx), float(cy), d / 2))
        # blend detail into regional terrain at the patch border
        edge = np.minimum.reduce([DX - self.dx0, self.dx0 + S - DX, DY - self.dy0, self.dy0 + S - DY]) / 40.0
        self.detail = base + fine * np.clip(edge, 0, 1)
        self.boulders = []
        for _ in range(cfg.boulders_near_target):
            a = rng.uniform(0, 2 * np.pi); rr = rng.uniform(15, S / 2 - 10)
            bx, by = tx + rr * np.cos(a), ty + rr * np.sin(a)
            size = float(np.clip(0.15 * (1 + rng.pareto(2.2)), 0.15, 2.5))
            self.boulders.append((float(bx), float(by), size))

    def _coarse_at(self, X, Y):
        r = self.cfg.resolution_m
        fx = np.clip((X - self.x0) / r, 0, self.nx - 1.001); fy = np.clip((Y - self.y0) / r, 0, self.ny - 1.001)
        i = fx.astype(int); j = fy.astype(int); dx = fx - i; dy = fy - j
        c = self.coarse
        return (1 - dx) * (1 - dy) * c[i, j] + dx * (1 - dy) * c[i + 1, j] + (1 - dx) * dy * c[i, j + 1] + dx * dy * c[i + 1, j + 1]

    def height(self, x: float, y: float) -> float:
        S, dr = self.cfg.detail_size_m, self.cfg.detail_res_m
        if self.dx0 <= x <= self.dx0 + S - dr and self.dy0 <= y <= self.dy0 + S - dr:
            fx = (x - self.dx0) / dr; fy = (y - self.dy0) / dr
            i, j = int(fx), int(fy); dx, dy = fx - i, fy - j
            d = self.detail
            return float((1 - dx) * (1 - dy) * d[i, j] + dx * (1 - dy) * d[i + 1, j] + (1 - dx) * dy * d[i, j + 1] + dx * dy * d[i + 1, j + 1])
        return float(self._coarse_at(np.array(x), np.array(y)))

    def slope_deg(self, x: float, y: float, r: float = 3.0) -> float:
        gx = (self.height(x + r, y) - self.height(x - r, y)) / (2 * r)
        gy = (self.height(x, y + r) - self.height(x, y - r)) / (2 * r)
        return float(np.degrees(np.arctan(np.hypot(gx, gy))))

    def visual(self) -> dict:
        cs = 3   # coarse grid decimated for rendering (30 m)
        ds = 2   # detail patch at 2 m
        return {"coarse": {"x0": self.x0, "y0": self.y0, "res": self.cfg.resolution_m * cs,
                           "heights": np.round(self.coarse[::cs, ::cs], 2).tolist()},
                "detail": {"x0": self.dx0, "y0": self.dy0, "res": self.cfg.detail_res_m * ds,
                           "heights": np.round(self.detail[::ds, ::ds], 3).tolist()},
                "boulders": [[round(b[0], 2), round(b[1], 2), round(self.height(b[0], b[1]), 2), b[2]] for b in self.boulders],
                "target": self.cfg.target}
