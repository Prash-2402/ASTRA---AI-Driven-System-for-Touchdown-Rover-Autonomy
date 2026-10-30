"""Traversability cost map: hard safety constraints separated from soft optimisation costs.

HARD (cell blocked):  operational-area geofence (2 m border) | lidar obstacle within inflation radius | slope > max_slope | camera-untraversable
                      (camera source can be down-weighted to 'geometry-dominant' mode)
SOFT (multiplicative cost per metre):
  1 + w_slope (slope/max_slope)^2 + w_class * class_cost + w_unknown * unknown
    + w_unc * sigma_pos + w_energy * energy_factor + w_actuator * (1 - health) * (slope + sand)
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.ndimage import binary_dilation

from autonomy.planning.rover_perception import RoverPerceivedMap

CLASS_COST = {-1: 0.6, 0: 0.0, 1: 0.25, 2: 1.4, 3: 3.0}


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

    def with_(self, **kw) -> "CostWeights":
        return replace(self, **kw)


def build_costmap(pm: RoverPerceivedMap, w: CostWeights, sigma_pos: float, actuator_health: float = 1.0) -> tuple[np.ndarray, np.ndarray, dict]:
    slope = pm.slope()
    infl = max(1, int(np.ceil(w.inflation_m + 1.5 * sigma_pos)))
    yy, xx = np.mgrid[-infl:infl + 1, -infl:infl + 1]
    k = (xx ** 2 + yy ** 2) <= infl ** 2
    obst = binary_dilation(pm.obstacle, structure=k)
    cam_block = pm.cam_trav == 0
    if not w.camera_hard:
        geo_flat = (pm.lidar_cnt >= 3) & ((pm.lidar_max - pm.lidar_min) < 0.18) & ~pm.obstacle
        cam_block = cam_block & ~geo_flat
    border = np.zeros_like(obst)
    border[:2, :] = border[-2:, :] = border[:, :2] = border[:, -2:] = True     # operational-area geofence
    hard = obst | (slope > w.max_slope_deg) | cam_block | border
    cls = pm.cam_class.astype(int)
    class_cost = np.vectorize(CLASS_COST.get)(cls)
    if not w.camera_hard:
        class_cost = np.where(pm.cam_trav == 0, 1.0, class_cost)
    unknown = (pm.seen_t < 0).astype(float)
    sand = (cls == 2).astype(float)
    energy = (np.clip(slope, 0, None) / w.max_slope_deg) + sand
    cost = (1 + w.w_slope * (slope / w.max_slope_deg) ** 2 + w.w_class * class_cost + w.w_unknown * unknown
            + w.w_uncertainty * sigma_pos + w.w_energy * energy
            + w.w_actuator * (1 - actuator_health) * (slope / 10.0 + 2 * sand))
    info = {"hard_cells": int(hard.sum()), "inflation_cells": infl, "max_slope_deg": w.max_slope_deg,
            "camera_hard": w.camera_hard}
    return cost, hard, info
