import numpy as np
from typing import Tuple, List, Dict, Any
from shared.enums.simulation import TerrainVariant

class TerrainMap:
    """
    Continuous 2D ground-truth terrain surface with discrete grid rasterization:
    - Elevation function z = f(x, y)
    - Surface normal and gradient/slope
    - Boulder / Rock obstacles (center, radius, height)
    - Traversability classification (0.0 = impassable obstacle, 1.0 = smooth flat surface)
    - Held-out evaluation separation (Terrains 4 & 5 are never used for planner tuning)
    """
    def __init__(self, variant: TerrainVariant, width_m: float = 100.0, height_m: float = 100.0, resolution_m: float = 0.5):
        self.variant = variant
        self.width = width_m
        self.height = height_m
        self.res = resolution_m
        self.nx = int(width_m / resolution_m)
        self.ny = int(height_m / resolution_m)

        # Deterministic seed per variant
        self.seed = 1000 + int(variant)
        self.rng = np.random.RandomState(self.seed)

        self.obstacles: List[Dict[str, Any]] = []
        self._generate_terrain_features()

        # Precompute discrete ground-truth traversability grid
        self.grid_x = np.linspace(0, self.width, self.nx)
        self.grid_y = np.linspace(0, self.height, self.ny)
        self.traversability_ground_truth = self._build_ground_truth_grid()

    def _generate_terrain_features(self):
        """Generates rocks and obstacles based on the exact variant specification."""
        if self.variant == TerrainVariant.DEV_MIXED_FLAT_UNEVEN:
            # Variant 1: gentle slopes, few scattered rocks
            for _ in range(35):
                cx = self.rng.uniform(15.0, 85.0)
                cy = self.rng.uniform(15.0, 85.0)
                r = self.rng.uniform(0.6, 1.4)
                self.obstacles.append({"pos": np.array([cx, cy]), "radius": r, "height": 0.45})

        elif self.variant == TerrainVariant.DEV_ROCKY_DISTRIBUTED:
            # Variant 2: Dense distributed rocky field
            for _ in range(85):
                cx = self.rng.uniform(8.0, 92.0)
                cy = self.rng.uniform(8.0, 92.0)
                r = self.rng.uniform(0.7, 1.8)
                self.obstacles.append({"pos": np.array([cx, cy]), "radius": r, "height": 0.65})

        elif self.variant == TerrainVariant.DEV_SLOPED_NARROW_CORRIDORS:
            # Variant 3: Steep ridge with narrow traversable passes
            # Wall 1 at y = 40 with a pass at x = 30
            for x in np.linspace(5.0, 95.0, 30):
                if not (24.0 <= x <= 36.0): # Corridor at x=30
                    self.obstacles.append({"pos": np.array([x, 40.0]), "radius": 2.2, "height": 1.2})
            # Wall 2 at y = 65 with a pass at x = 70
            for x in np.linspace(5.0, 95.0, 30):
                if not (64.0 <= x <= 76.0): # Corridor at x=70
                    self.obstacles.append({"pos": np.array([x, 65.0]), "radius": 2.2, "height": 1.2})

        elif self.variant == TerrainVariant.EVAL_IRREGULAR_COMPLEX:
            # Variant 4: Held-out evaluation environment with complex irregular boulder clusters
            for _ in range(110):
                cx = self.rng.uniform(10.0, 90.0)
                cy = self.rng.uniform(10.0, 90.0)
                r = self.rng.uniform(0.8, 2.2)
                self.obstacles.append({"pos": np.array([cx, cy]), "radius": r, "height": 0.85})

        elif self.variant == TerrainVariant.EVAL_EXTREME_HAZARDS:
            # Variant 5: Held-out evaluation environment with severe elevation steps and crater rims
            for _ in range(130):
                cx = self.rng.uniform(8.0, 92.0)
                cy = self.rng.uniform(8.0, 92.0)
                r = self.rng.uniform(0.9, 2.5)
                self.obstacles.append({"pos": np.array([cx, cy]), "radius": r, "height": 1.1})

    def get_elevation(self, x: float, y: float) -> float:
        """Continuous elevation function with slopes and obstacles."""
        # Regional slope
        if self.variant == TerrainVariant.DEV_SLOPED_NARROW_CORRIDORS:
            elev = 0.08 * y + 0.02 * x
        elif self.variant in [TerrainVariant.EVAL_IRREGULAR_COMPLEX, TerrainVariant.EVAL_EXTREME_HAZARDS]:
            elev = 0.04 * x + 0.05 * y + 2.5 * np.sin(0.06 * x) * np.cos(0.05 * y)
        else:
            elev = 0.02 * x + 0.015 * y + 1.0 * np.sin(0.04 * x) * np.cos(0.04 * y)

        # Rocks elevation contribution
        p_xy = np.array([x, y])
        for obs in self.obstacles:
            d = np.linalg.norm(p_xy - obs["pos"])
            r = obs["radius"]
            if d < r:
                elev += obs["height"] * np.cos((np.pi * 0.5) * (d / r))

        return float(elev)

    def get_surface_normal_and_slope(self, x: float, y: float, delta: float = 0.4) -> Tuple[np.ndarray, float]:
        """Calculates 3D surface normal and slope angle in degrees."""
        z_c = self.get_elevation(x, y)
        z_dx = self.get_elevation(x + delta, y)
        z_dy = self.get_elevation(x, y + delta)

        dz_dx = (z_dx - z_c) / delta
        dz_dy = (z_dy - z_c) / delta

        normal = np.array([-dz_dx, -dz_dy, 1.0])
        normal = normal / np.linalg.norm(normal)

        slope_rad = np.arccos(np.clip(normal[2], -1.0, 1.0))
        slope_deg = float(np.degrees(slope_rad))
        return normal, slope_deg

    def _build_ground_truth_grid(self) -> np.ndarray:
        """Vectorized rasterization into [nx, ny] ground-truth traversability cost grid."""
        X, Y = np.meshgrid(self.grid_x, self.grid_y, indexing='ij')
        grid = np.ones((self.nx, self.ny), dtype=np.float32)

        # Vectorized regional slopes
        if self.variant == TerrainVariant.DEV_SLOPED_NARROW_CORRIDORS:
            dz_dx = 0.02
            dz_dy = 0.08
        elif self.variant in [TerrainVariant.EVAL_IRREGULAR_COMPLEX, TerrainVariant.EVAL_EXTREME_HAZARDS]:
            dz_dx = 0.04 + 2.5 * 0.06 * np.cos(0.06 * X) * np.cos(0.05 * Y)
            dz_dy = 0.05 - 2.5 * 0.05 * np.sin(0.06 * X) * np.sin(0.05 * Y)
        else:
            dz_dx = 0.02 + 1.0 * 0.04 * np.cos(0.04 * X) * np.cos(0.04 * Y)
            dz_dy = 0.015 - 1.0 * 0.04 * np.sin(0.04 * X) * np.sin(0.04 * Y)

        grad_norm = np.sqrt(dz_dx**2 + dz_dy**2)
        slope_rad = np.arctan(grad_norm)
        slope_deg = np.degrees(slope_rad)

        # Apply slope cost
        grid[slope_deg > 8.0] = 0.70
        grid[slope_deg > 14.0] = 0.35
        grid[slope_deg > 22.0] = 0.0

        # Vectorized rock obstacles
        for obs in self.obstacles:
            dist_sq = (X - obs["pos"][0])**2 + (Y - obs["pos"][1])**2
            r_sq = (obs["radius"] * 1.05)**2
            grid[dist_sq <= r_sq] = 0.0

        return grid

    def get_ground_truth_traversability(self, x: float, y: float) -> float:
        ix = int(np.clip(x / self.res, 0, self.nx - 1))
        iy = int(np.clip(y / self.res, 0, self.ny - 1))
        return float(self.traversability_ground_truth[ix, iy])

    def generate_perceived_grid(self, corruption_ratio: float = 0.0) -> np.ndarray:
        """
        Generates perception grid with optional FAULT 02 (Terrain Misclassification).
        When corruption_ratio = 0.15 (default for fault 02), exactly 15% of eligible cells are inverted.
        """
        perceived = self.traversability_ground_truth.copy()

        if corruption_ratio > 0.0:
            # Deterministic corruption mask
            corrupt_rng = np.random.RandomState(self.seed + 99)
            eligible_mask = (perceived > 0.0) & (perceived < 1.0)
            eligible_indices = np.argwhere(eligible_mask)

            if len(eligible_indices) == 0:
                eligible_indices = np.argwhere(perceived >= 0.0)

            n_to_corrupt = int(len(eligible_indices) * corruption_ratio)
            chosen_indices = corrupt_rng.choice(len(eligible_indices), size=n_to_corrupt, replace=False)

            for idx in chosen_indices:
                ix, iy = eligible_indices[idx]
                # Invert: smooth becomes hazardous or vice versa
                perceived[ix, iy] = 0.0 if perceived[ix, iy] > 0.5 else 1.0

        return perceived
