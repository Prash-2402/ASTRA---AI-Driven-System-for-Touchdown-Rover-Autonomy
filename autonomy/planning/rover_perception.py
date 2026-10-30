"""Rover perceived map (1 m grid). Built only from sensor packets + estimated pose.

Layers
  prior_h      orbital elevation prior (2 m blocks, noisy) - available before driving
  lidar_h      mean lidar ground height per cell, lidar_max / lidar_min (for obstacle steps)
  obstacle     lidar-detected obstacle cells (step > threshold above local ground)
  cam_class    last camera class (-1 unknown), cam_trav (1/0/-1), cam_conf
  seen_t       last observation time
Also tracks a camera/lidar geometric-consistency statistic used as fault evidence.
"""
from __future__ import annotations

import numpy as np

from simulation.rover.terrain import CRES, SIZE_M

M = int(SIZE_M / CRES)


_HALF = SIZE_M / 2


def cell_of(x: float, y: float) -> tuple[int, int]:
    i = int((x + _HALF) / CRES)
    j = int((y + _HALF) / CRES)
    return (0 if i < 0 else (M - 1 if i > M - 1 else i), 0 if j < 0 else (M - 1 if j > M - 1 else j))


def center_of(i: int, j: int) -> tuple[float, float]:
    return (-SIZE_M / 2 + (i + 0.5) * CRES, -SIZE_M / 2 + (j + 0.5) * CRES)


class RoverPerceivedMap:
    def __init__(self, prior_heights: np.ndarray):
        self.prior_h = prior_heights
        self.lidar_sum = np.zeros((M, M)); self.lidar_cnt = np.zeros((M, M))
        self.lidar_max = np.full((M, M), -np.inf); self.lidar_min = np.full((M, M), np.inf)
        self.obstacle = np.zeros((M, M), bool)
        self.obstacle_t = np.full((M, M), -1.0)
        self.high_hits = np.zeros((M, M), np.int32)
        self.cam_class = np.full((M, M), -1, np.int8)
        self.cam_trav = np.full((M, M), -1, np.int8)
        self.seen_t = np.full((M, M), -1.0)
        self.consistency_window: list[tuple[float, int, int]] = []   # (t, n_checked, n_inconsistent)
        self.version = 0

    # -- updates ---------------------------------------------------------
    def integrate_lidar(self, t: float, pts_body: np.ndarray, est_pose: np.ndarray, roll_pitch) -> int:
        """Place lidar hits in the map with the ESTIMATED pose, then test touched cells for obstacles.

        Obstacle test (robust to slopes and grazing-incidence micro-relief):
          ground(i,j) = median of the neighbouring cells' MEAN hit heights (symmetric -> slope-invariant)
          a hit is 'high' if z - ground > 0.20 + 0.03 * range
          cell is an obstacle once it has accumulated >= 2 high hits.
        """
        x, y, z, psi = est_pose
        roll, pitch = roll_pitch
        cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(psi), np.sin(psi)
        R = np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                      [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                      [-sp, cp * sr, cp * cr]])
        finite = np.all(np.isfinite(pts_body), axis=1)
        pb = pts_body[finite]
        rng = np.hypot(pb[:, 0], pb[:, 1])
        P = pb @ R.T + np.array([x, y, z])
        cells = []
        for px, py, pz in P:
            i, j = cell_of(px, py)
            self.lidar_sum[i, j] += pz; self.lidar_cnt[i, j] += 1
            self.lidar_max[i, j] = max(self.lidar_max[i, j], pz); self.lidar_min[i, j] = min(self.lidar_min[i, j], pz)
            self.seen_t[i, j] = t
            cells.append((i, j))
        new_obs = 0
        ground_cache: dict = {}
        for (i, j), pz, r in zip(cells, P[:, 2], rng):
            if (i, j) not in ground_cache:
                ground_cache[(i, j)] = self._local_ground(i, j)
            if pz - ground_cache[(i, j)] > 0.20 + 0.03 * r:
                self.high_hits[i, j] += 1
                if self.high_hits[i, j] >= 2 and not self.obstacle[i, j]:
                    self.obstacle[i, j] = True
                    self.obstacle_t[i, j] = t
                    new_obs += 1
        if new_obs:
            self.version += 1
        return new_obs

    def _local_ground(self, i, j) -> float:
        vals = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if (di or dj) and 0 <= i + di < M and 0 <= j + dj < M and self.lidar_cnt[i + di, j + dj] > 0:
                    vals.append(self.lidar_sum[i + di, j + dj] / self.lidar_cnt[i + di, j + dj])
        if len(vals) >= 3:
            return float(np.median(vals))
        return float(self.prior_h[i, j])

    def integrate_camera(self, t: float, cells: list, est_pose: np.ndarray) -> dict:
        x, y, _, psi = est_pose
        checked = inconsistent = 0
        changed = 0
        for (r, bearing, cls, trav) in cells:
            a = psi + bearing
            i, j = cell_of(x + r * np.cos(a), y + r * np.sin(a))
            if self.cam_trav[i, j] != int(trav):
                changed += 1
            self.cam_class[i, j] = cls
            self.cam_trav[i, j] = int(trav)
            self.seen_t[i, j] = t
            # geometric consistency: camera vs lidar where lidar has dense coverage
            if self.lidar_cnt[i, j] >= 3 and r < 6.0:
                checked += 1
                geo_flat = (self.lidar_max[i, j] - self.lidar_min[i, j]) < 0.18 and not self.obstacle[i, j]
                if (not trav) and geo_flat:
                    # salt-and-pepper test: an isolated 'untraversable' label on flat ground is suspicious;
                    # contiguous untraversable regions (rock fields) are not counted
                    nb = self.cam_trav[max(i - 1, 0):i + 2, max(j - 1, 0):j + 2]
                    if np.sum(nb == 0) <= 2:
                        inconsistent += 1
                elif trav and self.obstacle[i, j] and self._cell_slope(i, j) < 12.0:
                    inconsistent += 1
        self.consistency_window.append((t, checked, inconsistent))
        self.consistency_window = [w for w in self.consistency_window if w[0] > t - 6.0]
        if changed:
            self.version += 1
        return {"checked": checked, "inconsistent": inconsistent}

    def _cell_slope(self, i, j) -> float:
        sl = getattr(self, "_slope", None)
        return float(sl[i, j]) if sl is not None else 0.0

    def inconsistency_rate(self) -> tuple[float, int]:
        n = sum(w[1] for w in self.consistency_window)
        k = sum(w[2] for w in self.consistency_window)
        return (k / n if n else 0.0), n

    # -- derived layers ------------------------------------------------------
    def elevation(self) -> np.ndarray:
        """Ground elevation: lower envelope of lidar hits (robust to rock returns) where sensed,
        otherwise the orbital prior shifted to agree with sensed ground (avoids seams at the boundary)."""
        h = self.prior_h.copy()
        m = self.lidar_cnt > 0
        if m.any():
            ground = self.lidar_min[m] + 0.02
            h = h + float(np.median(ground - self.prior_h[m]))
            h[m] = ground
        return h

    def slope(self) -> np.ndarray:
        if getattr(self, "_slope_version", None) == (self.version, int(self.lidar_cnt.sum())):
            return self._slope
        from scipy.ndimage import uniform_filter
        e = uniform_filter(self.elevation(), size=3, mode="nearest")
        gx, gy = np.gradient(e, CRES)
        self._slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        self._slope_version = (self.version, int(self.lidar_cnt.sum()))
        return self._slope

    def to_dict(self) -> dict:
        return {"cell": CRES, "size_m": SIZE_M, "obstacle": np.argwhere(self.obstacle).tolist(),
                "cam_trav": self.cam_trav.tolist(), "seen": (self.seen_t >= 0).astype(np.int8).tolist()}


def orbital_prior(terrain_heights: np.ndarray, hres: float, rng: np.random.Generator) -> np.ndarray:
    """2 m block-averaged elevation + 0.1 m noise, resampled to the 1 m grid (no rocks, no classes)."""
    k = int(2 * CRES / hres)
    n = (terrain_heights.shape[0] // k) * k
    coarse = terrain_heights[:n, :n].reshape(n // k, k, n // k, k).mean(axis=(1, 3))
    coarse += rng.normal(0, 0.1, coarse.shape)
    fine = np.repeat(np.repeat(coarse, 2, axis=0), 2, axis=1)
    out = np.zeros((M, M))
    out[: fine.shape[0], : fine.shape[1]] = fine[:M, :M]
    return out
