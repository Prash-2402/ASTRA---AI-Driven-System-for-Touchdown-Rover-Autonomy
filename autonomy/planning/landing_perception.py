"""Perceived terrain for the lander: orbital a-priori DEM + close-range lidar hazard mapping.

Nothing in this module is read by the autonomy stack *except* the perceived
products it builds. The true terrain is accessed only inside the sensing
functions to synthesise measurements, with sensor-limited resolution,
noise, detection probability and navigation-induced registration error.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.touchdown.terrain import Terrain, heights_at


class OrbitalDEM:
    """Low-resolution prior map (HiRISE-like DEM): block-averaged truth + noise, no rocks."""

    def __init__(self, terrain: Terrain, rng: np.random.Generator, block: int = 5, noise_m: float = 0.5):
        h = terrain.heights
        n = (h.shape[0] // block) * block
        coarse = h[:n, :n].reshape(n // block, block, n // block, block).mean(axis=(1, 3))
        coarse += rng.normal(0, noise_m, coarse.shape)
        self.res = terrain.res * block
        self.origin = terrain.origin + terrain.res * (block - 1) / 2
        self.h = coarse
        self.n = coarse.shape[0]

    def height(self, x: float, y: float) -> float:
        fx = min(max((x - self.origin) / self.res, 0.0), self.n - 1.001)
        fy = min(max((y - self.origin) / self.res, 0.0), self.n - 1.001)
        i, j = int(fx), int(fy)
        dx, dy = fx - i, fy - j
        h = self.h
        return float((1 - dx) * (1 - dy) * h[i, j] + dx * (1 - dy) * h[i + 1, j]
                     + (1 - dx) * dy * h[i, j + 1] + dx * dy * h[i + 1, j + 1])

    def gradient(self, x: float, y: float):
        e = self.res * 0.5
        return ((self.height(x + e, y) - self.height(x - e, y)) / (2 * e),
                (self.height(x, y + e) - self.height(x, y - e)) / (2 * e))


@dataclass
class LidarConfig:
    max_range: float = 900.0
    fov_radius_frac: float = 0.45      # scanned ground radius = frac * AGL (+ min)
    min_radius: float = 40.0
    max_radius: float = 220.0
    cell: float = 2.0
    range_noise_base: float = 0.08
    range_noise_per_m: float = 0.0006
    rock_thresh_base: float = 0.15     # smallest detectable rock height at 0 range [m]
    rock_thresh_per_m: float = 0.0009
    detect_prob: float = 0.95


class PerceivedHazardMap:
    """Accumulated perceived terrain in the lander's *estimated* navigation frame."""

    def __init__(self, cfg: LidarConfig):
        self.cfg = cfg
        self.cells: dict[tuple[int, int], tuple[float, float]] = {}   # (i, j) -> (height, quality_range)
        self.rocks: list[tuple[float, float, float, float]] = []      # x, y, radius, height (perceived)
        self.scans = 0
        self.scan_regions: list[tuple[float, float, float]] = []

    def scan(self, terrain: Terrain, true_pos: np.ndarray, est_pos: np.ndarray, agl: float,
             center_est: np.ndarray, rng: np.random.Generator) -> dict:
        c = self.cfg
        if agl > c.max_range:
            return {"performed": False, "reason": "out of range"}
        radius = float(np.clip(c.fov_radius_frac * agl, c.min_radius, c.max_radius))
        reg_err = np.asarray(est_pos[:2]) - np.asarray(true_pos[:2])   # map registration error from nav error
        sigma_h = c.range_noise_base + c.range_noise_per_m * agl
        ci = np.arange(-radius, radius + 1e-9, c.cell)
        GX, GY = np.meshgrid(center_est[0] + ci, center_est[1] + ci, indexing="ij")
        mask = (GX - center_est[0]) ** 2 + (GY - center_est[1]) ** 2 <= radius ** 2
        gx, gy = GX[mask], GY[mask]
        h_true = heights_at(terrain, gx - reg_err[0], gy - reg_err[1])
        h_meas = h_true + rng.normal(0, sigma_h, h_true.shape)
        for x, y, h in zip(gx, gy, h_meas):
            key = (int(round(x / c.cell)), int(round(y / c.cell)))
            old = self.cells.get(key)
            if old is None or agl <= old[1]:
                self.cells[key] = (float(h), float(agl))
        # rocks
        thresh = c.rock_thresh_base + c.rock_thresh_per_m * agl
        cand = terrain.rocks_near(center_est[0] - reg_err[0], center_est[1] - reg_err[1], radius)
        new_rocks = []
        pos_noise = 0.3 + 0.002 * agl
        for x, y, r, hgt in cand:
            if hgt < thresh or rng.random() > c.detect_prob:
                continue
            px, py = x + reg_err[0] + rng.normal(0, pos_noise), y + reg_err[1] + rng.normal(0, pos_noise)
            new_rocks.append((float(px), float(py), float(r), float(hgt + rng.normal(0, sigma_h))))
        # replace previously perceived rocks inside this region (newer scan supersedes)
        self.rocks = [rk for rk in self.rocks if (rk[0] - center_est[0]) ** 2 + (rk[1] - center_est[1]) ** 2 > radius ** 2]
        self.rocks.extend(new_rocks)
        self.scans += 1
        self.scan_regions.append((float(center_est[0]), float(center_est[1]), radius))
        return {"performed": True, "radius": radius, "rock_threshold_m": thresh, "cells": int(mask.sum()),
                "rocks_detected": len(new_rocks), "height_noise_m": sigma_h}

    def covered(self, x: float, y: float, r: float) -> bool:
        c = self.cfg.cell
        for dx in (-r, 0, r):
            for dy in (-r, 0, r):
                if (int(round((x + dx) / c)), int(round((y + dy) / c))) not in self.cells:
                    return False
        return True

    def patch(self, x: float, y: float, r: float) -> np.ndarray:
        c = self.cfg.cell
        pts = []
        k = int(np.ceil(r / c))
        ix, iy = int(round(x / c)), int(round(y / c))
        for i in range(ix - k, ix + k + 1):
            for j in range(iy - k, iy + k + 1):
                v = self.cells.get((i, j))
                if v is not None and (i * c - x) ** 2 + (j * c - y) ** 2 <= r * r:
                    sig = self.cfg.range_noise_base + self.cfg.range_noise_per_m * v[1]
                    pts.append((i * c, j * c, v[0], sig))
        return np.array(pts) if pts else np.zeros((0, 4))

    def to_dict(self, max_cells: int = 4000) -> dict:
        items = list(self.cells.items())
        step = max(1, len(items) // max_cells)
        return {"cell": self.cfg.cell, "scans": self.scans, "regions": self.scan_regions[-5:],
                "rocks": [list(r) for r in self.rocks],
                "cells": [[k[0] * self.cfg.cell, k[1] * self.cfg.cell, round(v[0], 2)] for k, v in items[::step]]}
