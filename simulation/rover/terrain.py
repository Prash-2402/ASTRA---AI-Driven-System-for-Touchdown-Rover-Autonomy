"""ASTRA ROVER terrain variants (exactly five, deterministic).

Ground truth (simulator + evaluator only):
  heights   [n x n] at 0.25 m      elevation field (PyBullet heightfield)
  classes   [m x m] at 1 m          0 bedrock | 1 regolith | 2 loose sand | 3 rock-field (impassable)
  obstacles list of rocks (x, y, radius, height) -> separate collision bodies
The rover's planner never reads these arrays; it receives perceived maps
built from simulated sensors (autonomy/planning/rover_perception.py).

Variants 1-3: development.   Variants 4-5: held-out evaluation (never used for tuning).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SIZE_M = 60.0
HRES = 0.25
CRES = 1.0

CLASS_NAMES = ["bedrock", "regolith", "loose_sand", "rock_field"]
CLASS_FRICTION = [0.95, 0.75, 0.45, 0.9]
CLASS_ROLLING_RESISTANCE = [0.03, 0.06, 0.16, 0.05]   # coefficient (force / normal force)
CLASS_TRAVERSABLE = [True, True, True, False]
CLIMBABLE_HEIGHT = 0.25    # rocker-bogie can climb rocks up to ~1.5 wheel radii

VARIANTS = {
    1: {"name": "Mixed flat and uneven", "split": "development", "gen_seed": 101, "relief": 0.35, "slope": (2.0, 0.0),
        "rocks": 35, "rock_r": (0.15, 0.45), "sand_frac": 0.12, "fields": 1, "ridges": 0,
        "start": (-24.0, -22.0), "target": (22.0, 20.0)},
    2: {"name": "Rocky distributed obstacles", "split": "development", "gen_seed": 202, "relief": 0.25, "slope": (0.5, 1.0),
        "rocks": 120, "rock_r": (0.2, 0.7), "sand_frac": 0.08, "fields": 2, "ridges": 0,
        "start": (-24.0, 0.0), "target": (24.0, 2.0)},
    3: {"name": "Sloped narrow corridors", "split": "development", "gen_seed": 303, "relief": 0.3, "slope": (6.0, 2.0),
        "rocks": 50, "rock_r": (0.2, 0.6), "sand_frac": 0.1, "fields": 0, "ridges": 3,
        "start": (-25.0, -20.0), "target": (24.0, 22.0)},
    4: {"name": "Irregular complex (held-out)", "split": "held_out", "gen_seed": 404, "relief": 0.6, "slope": (3.0, -3.0),
        "rocks": 90, "rock_r": (0.2, 0.65), "sand_frac": 0.18, "fields": 2, "ridges": 1,
        "start": (-24.0, 22.0), "target": (23.0, -22.0)},
    5: {"name": "Complex alternate hazards (held-out)", "split": "held_out", "gen_seed": 505, "relief": 0.45, "slope": (-4.0, 4.5),
        "rocks": 110, "rock_r": (0.2, 0.8), "sand_frac": 0.15, "fields": 3, "ridges": 2,
        "start": (24.0, -24.0), "target": (-22.0, 23.0)},
}

DEVELOPMENT = (1, 2, 3)
HELD_OUT = (4, 5)


@dataclass
class RoverTerrain:
    variant: int
    heights: np.ndarray
    classes: np.ndarray
    obstacles: list = field(default_factory=list)
    start: tuple = (0.0, 0.0)
    target: tuple = (0.0, 0.0)
    name: str = ""
    split: str = ""

    @property
    def n(self): return self.heights.shape[0]

    @property
    def m(self): return self.classes.shape[0]

    def height(self, x: float, y: float) -> float:
        fx = np.clip((x + SIZE_M / 2) / HRES, 0, self.n - 1.001)
        fy = np.clip((y + SIZE_M / 2) / HRES, 0, self.n - 1.001)
        i, j = int(fx), int(fy)
        dx, dy = fx - i, fy - j
        h = self.heights
        return float((1 - dx) * (1 - dy) * h[i, j] + dx * (1 - dy) * h[i + 1, j] + (1 - dx) * dy * h[i, j + 1] + dx * dy * h[i + 1, j + 1])

    def cell(self, x: float, y: float) -> tuple[int, int]:
        m = self.m
        i = int((x + SIZE_M / 2) / CRES)
        j = int((y + SIZE_M / 2) / CRES)
        return (0 if i < 0 else (m - 1 if i > m - 1 else i), 0 if j < 0 else (m - 1 if j > m - 1 else j))

    def class_at(self, x: float, y: float) -> int:
        return int(self.classes[self.cell(x, y)])

    def slope_grid(self) -> np.ndarray:
        """True slope [deg] on the 1 m class grid."""
        k = int(CRES / HRES)
        hc = self.heights[: self.m * k, : self.m * k].reshape(self.m, k, self.m, k).mean(axis=(1, 3))
        gx, gy = np.gradient(hc, CRES)
        return np.degrees(np.arctan(np.hypot(gx, gy)))

    def rock_cells(self) -> np.ndarray:
        """Cells occupied by non-climbable rocks (h > CLIMBABLE_HEIGHT)."""
        if getattr(self, "_rock_cells", None) is None:
            mask = np.zeros((self.m, self.m), bool)
            for (x, y, r, h) in self.obstacles:
                if h > CLIMBABLE_HEIGHT:
                    for dx in (-r, 0, r):
                        for dy in (-r, 0, r):
                            mask[self.cell(x + dx, y + dy)] = True
            self._rock_cells = mask
        return self._rock_cells

    def summary(self) -> dict:
        return {"gen_attempt": getattr(self, "gen_attempt", 0), "variant": self.variant, "name": self.name, "split": self.split, "size_m": SIZE_M,
                "start": self.start, "target": self.target, "n_obstacles": len(self.obstacles)}

    def visual(self, step: int = 2) -> dict:
        return {"size_m": SIZE_M, "resolution_m": HRES * step, "heights": np.round(self.heights[::step, ::step], 3).tolist(),
                "classes": self.classes.tolist(), "obstacles": [list(map(float, o)) for o in self.obstacles],
                "start": self.start, "target": self.target}


def _smooth_noise(rng, n, power):
    noise = rng.normal(size=(n, n))
    f = np.sqrt(np.fft.fftfreq(n)[:, None] ** 2 + np.fft.fftfreq(n)[None, :] ** 2)
    f[0, 0] = 1
    s = np.fft.fft2(noise) / f ** power
    s[0, 0] = 0
    h = np.real(np.fft.ifft2(s))
    return (h - h.mean()) / (h.std() + 1e-9)


def oracle_feasible(t: "RoverTerrain", max_slope: float = 22.0) -> bool:
    """Feasibility check with TRUE terrain (generator validation only - never used by autonomy):
    a path must exist that avoids slopes > max_slope, rock fields and dilated non-climbable rocks."""
    from scipy.ndimage import binary_dilation

    from autonomy.planning.astar import astar
    hard = (t.slope_grid() > max_slope) | binary_dilation(t.rock_cells() | (t.classes == 3), structure=np.ones((3, 3), bool))
    hard[:2, :] = hard[-2:, :] = hard[:, :2] = hard[:, -2:] = True
    return astar(np.ones(hard.shape), hard, t.start, t.target)["found"]


def generate(variant: int) -> RoverTerrain:
    """Deterministic: the variant's generation seed is tried first; if the oracle finds no feasible
    route, the next sub-seed is used (recorded in RoverTerrain.gen_attempt)."""
    if variant not in VARIANTS:
        raise ValueError("terrain variant must be 1..5")
    for attempt in range(20):
        t = _generate(variant, VARIANTS[variant]["gen_seed"] + 7919 * attempt)
        t.gen_attempt = attempt
        if oracle_feasible(t):
            return t
    raise RuntimeError(f"terrain variant {variant}: no feasible layout found")


def _generate(variant: int, gen_seed: int) -> RoverTerrain:
    v = VARIANTS[variant]
    rng = np.random.default_rng(gen_seed)
    n = int(SIZE_M / HRES) + 1
    m = int(SIZE_M / CRES)
    xs = -SIZE_M / 2 + np.arange(n) * HRES
    X, Y = np.meshgrid(xs, xs, indexing="ij")
    h = _smooth_noise(rng, n, 2.2) * v["relief"]
    h += np.tan(np.radians(v["slope"][0])) * X + np.tan(np.radians(v["slope"][1])) * Y
    sx, sy = v["start"]; tx, ty = v["target"]
    # ridges (raised berms with gaps -> narrow traversable corridors)
    for k in range(v["ridges"]):
        frac = (k + 1) / (v["ridges"] + 1)
        cx, cy = sx + frac * (tx - sx), sy + frac * (ty - sy)
        ang = np.arctan2(ty - sy, tx - sx) + np.pi / 2
        d = (X - cx) * np.cos(ang - np.pi / 2) + (Y - cy) * np.sin(ang - np.pi / 2)
        along = (X - cx) * np.cos(ang) + (Y - cy) * np.sin(ang)
        gap_c = rng.uniform(-12, 12)
        gap = np.exp(-((along - gap_c) / 3.0) ** 4)
        h += 1.4 * np.exp(-(d / 1.3) ** 2) * (1 - gap)
    h -= h[(n - 1) // 2, (n - 1) // 2]
    # classes on 1 m grid
    cxs = -SIZE_M / 2 + (np.arange(m) + 0.5) * CRES
    CX, CY = np.meshgrid(cxs, cxs, indexing="ij")
    field_noise = _smooth_noise(rng, m, 1.6)
    classes = np.where(field_noise > 0.3, 1, 0)
    sand = _smooth_noise(rng, m, 2.0)
    classes[sand > np.quantile(sand, 1 - v["sand_frac"])] = 2
    for _ in range(v["fields"]):
        for _try in range(50):
            fx, fy = rng.uniform(-22, 22, 2)
            if np.hypot(fx - sx, fy - sy) > 8 and np.hypot(fx - tx, fy - ty) > 8:
                break
        r = rng.uniform(3, 6)
        classes[np.hypot(CX - fx, CY - fy) < r] = 3
    # obstacles
    obstacles = []
    for _ in range(v["rocks"]):
        for _try in range(50):
            ox, oy = rng.uniform(-28, 28, 2)
            if np.hypot(ox - sx, oy - sy) > 3 and np.hypot(ox - tx, oy - ty) > 3:
                break
        r = float(rng.uniform(*v["rock_r"]))
        obstacles.append((float(ox), float(oy), r, float(r * rng.uniform(0.8, 1.4))))
    # rock fields contain dense boulders
    for i in range(m):
        for j in range(m):
            if classes[i, j] == 3 and rng.random() < 0.35:
                obstacles.append((float(cxs[i] + rng.uniform(-.3, .3)), float(cxs[j] + rng.uniform(-.3, .3)),
                                  float(rng.uniform(0.25, 0.5)), float(rng.uniform(0.35, 0.7))))
    # keep start/target cells clear
    for (px, py) in (v["start"], v["target"]):
        i, j = int((px + SIZE_M / 2) / CRES), int((py + SIZE_M / 2) / CRES)
        classes[max(i - 2, 0):i + 3, max(j - 2, 0):j + 3] = 0
    return RoverTerrain(variant, h.astype(np.float64), classes.astype(np.int8), obstacles, v["start"], v["target"],
                        v["name"], v["split"])
