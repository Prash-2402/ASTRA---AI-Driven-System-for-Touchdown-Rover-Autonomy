"""Reference descent profile shared by the guidance laws (velocity field toward the target)."""
from __future__ import annotations

import numpy as np


def desired_velocity(p: np.ndarray, target: np.ndarray, agl: float, a_prof: float = 1.0,
                     v_td: float = 0.7, vz_max: float = 75.0, k_h: float = 0.12, vh_max: float = 40.0) -> np.ndarray:
    """Vertical: v = min(sqrt(2 a h), v_td + 0.15 h).  Horizontal: proportional, capped by altitude.

    At low altitude with remaining horizontal error the vertical rate is reduced
    so that lateral alignment completes before touchdown.
    """
    h = max(agl, 0.0)
    vz = min(np.sqrt(2 * a_prof * h), v_td + 0.15 * h, vz_max)
    vz = max(vz, v_td)
    dxy = np.asarray(target[:2]) - np.asarray(p[:2])
    dist = float(np.linalg.norm(dxy))
    vh_cap = min(vh_max, 0.08 * h + 1.0)
    vh = k_h * dxy
    n = np.linalg.norm(vh)
    if n > vh_cap:
        vh = vh / n * vh_cap
    if h < 120 and dist > 4.0:
        vz *= float(np.clip(1.0 - (dist - 4.0) / 40.0, 0.15, 1.0))
    return np.array([vh[0], vh[1], -vz])
