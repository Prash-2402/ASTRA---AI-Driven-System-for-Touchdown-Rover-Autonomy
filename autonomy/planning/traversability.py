"""Traversability cost map: hard safety constraints separated from soft optimisation costs.

HARD (cell blocked):  operational-area geofence (2 m border) | lidar obstacle within inflation radius | slope > max_slope | camera-untraversable
                      (camera source can be down-weighted to 'geometry-dominant' or fully 'soft')
                      | an extra-cost cell at or above HARD_PENALTY (patches where the rover already got stuck twice)
SOFT (multiplicative cost per metre):
  1 + w_slope (slope/max_slope)^2 + w_class * class_cost + w_unknown * unknown
    + w_unc * sigma_pos + w_energy * energy_factor + w_actuator * (1 - health) * (slope + sand)
    + w_clearance * proximity (a halo just outside the hard inflation: keep distance when there is room, pass when there is not)
    + extra (mission-supplied penalties, e.g. a patch where the rover made no progress)

Inflation radius in cells = inflation_m + sigma_inflation * sigma_pos, rounded up ('ceil') or to the nearest
cell ('round'). 'round' with a small sigma factor keeps the radius from flickering between 1 and 2 cells as the
position uncertainty breathes, which otherwise opens and closes corridors and makes the route change back and forth.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.ndimage import binary_dilation, distance_transform_edt, label

from autonomy.planning.rover_perception import RoverPerceivedMap

CLASS_COST = {-1: 0.6, 0: 0.0, 1: 0.25, 2: 1.4, 3: 3.0}
HARD_PENALTY = 1e3


@dataclass
class CostWeights:
    max_slope_deg: float = 22.0
    inflation_m: float = 0.9
    w_slope: float = 2.0
    w_class: float = 1.0
    w_unknown: float = 0.4
    w_uncertainty: float = 0.5
    w_energy: float = 0.0
    w_actuator: float = 0.0
    camera_hard: bool = True          # False => geometry-dominant (camera untraversable is a soft cost where lidar sees flat ground)
    camera_soft: bool = False         # True => camera 'untraversable' never blocks on its own; lidar obstacles and slope do
    sigma_inflation: float = 1.5      # metres of extra inflation per metre of position sigma
    inflation_rounding: str = "ceil"  # 'ceil' | 'round'
    inflation_diag: bool = False      # True: radius-1 inflation is the full 3x3 block (covers diagonal passes past a rock)
    size_aware: bool = False          # True: small rocks get a 1-cell margin, only big ones the full inflation radius
    small_rock_cells: int = 1         # 'small' = a perceived rock covering at most this many cells ...
    small_rock_height_m: float = 0.35 # ... and no taller than this above the surrounding ground
    small_margin_cells: int = 1       # margin around a small rock (0 = only its own cell: narrow-passage tier)
    clearance_m: float = 0.0          # width of the soft proximity halo outside the hard inflation
    w_clearance: float = 0.0

    def with_(self, **kw) -> "CostWeights":
        return replace(self, **kw)


def inflation_cells(w: CostWeights, sigma_pos: float) -> int:
    r = w.inflation_m + w.sigma_inflation * sigma_pos
    return max(1, int(np.ceil(r)) if w.inflation_rounding == "ceil" else int(np.floor(r + 0.5)))


def build_costmap(pm: RoverPerceivedMap, w: CostWeights, sigma_pos: float, actuator_health: float = 1.0,
                  extra: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    slope = pm.slope()
    infl = inflation_cells(w, sigma_pos)
    yy, xx = np.mgrid[-infl:infl + 1, -infl:infl + 1]
    k = (xx ** 2 + yy ** 2) <= (infl ** 2 + infl if w.inflation_diag else infl ** 2)
    if w.size_aware and pm.obstacle.any():
        # margin by rock size: the clearance the 1.04 m wide rover needs grows with the rock, so a pebble-sized
        # return must not close off a 5x5 area the way a boulder does
        lab, n = label(pm.obstacle, structure=np.ones((3, 3), bool))
        elev = pm.elevation()
        big = np.zeros_like(pm.obstacle)
        for r in range(1, n + 1):
            cells = lab == r
            top = float(np.max(np.where(cells, pm.lidar_max, -np.inf)))
            ground = float(np.min(elev[binary_dilation(cells, iterations=2) & ~pm.obstacle], initial=top))
            if cells.sum() > w.small_rock_cells or top - ground > w.small_rock_height_m:
                big |= cells
        small = pm.obstacle & ~big
        plus = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
        obst = binary_dilation(big, structure=k) | (binary_dilation(small, structure=plus) if w.small_margin_cells else small)
    else:
        obst = binary_dilation(pm.obstacle, structure=k)
    cam_block = pm.cam_trav == 0
    if w.camera_soft:
        cam_block = np.zeros_like(cam_block)
    elif not w.camera_hard:
        geo_flat = (pm.lidar_cnt >= 3) & ((pm.lidar_max - pm.lidar_min) < 0.18) & ~pm.obstacle
        cam_block = cam_block & ~geo_flat
    border = np.zeros_like(obst)
    border[:2, :] = border[-2:, :] = border[:, :2] = border[:, -2:] = True     # operational-area geofence
    hard = obst | (slope > w.max_slope_deg) | cam_block | border
    if extra is not None:
        hard |= extra >= HARD_PENALTY
    cls = pm.cam_class.astype(int)
    class_cost = np.vectorize(CLASS_COST.get)(cls)
    if not w.camera_hard or w.camera_soft:
        class_cost = np.where(pm.cam_trav == 0, 1.0 if not w.camera_soft else 3.0, class_cost)
    unknown = (pm.seen_t < 0).astype(float)
    sand = (cls == 2).astype(float)
    energy = (np.clip(slope, 0, None) / w.max_slope_deg) + sand
    cost = (1 + w.w_slope * (np.minimum(slope, w.max_slope_deg) / w.max_slope_deg) ** 2 + w.w_class * class_cost
            + w.w_unknown * unknown + w.w_uncertainty * sigma_pos + w.w_energy * energy
            + w.w_actuator * (1 - actuator_health) * (slope / 10.0 + 2 * sand))
    if w.w_clearance > 0 and w.clearance_m > 0 and pm.obstacle.any():
        d = distance_transform_edt(~pm.obstacle)                     # metres (1 m cells) to the nearest obstacle cell
        prox = np.clip(1.0 - (d - infl) / w.clearance_m, 0.0, 1.0) * (d > infl)
        cost = cost + w.w_clearance * prox
    if extra is not None:
        cost = cost + np.minimum(extra, HARD_PENALTY - 1)
    info = {"hard_cells": int(hard.sum()), "inflation_cells": infl, "max_slope_deg": w.max_slope_deg,
            "camera_hard": w.camera_hard, "camera_soft": w.camera_soft}
    return cost, hard, info
