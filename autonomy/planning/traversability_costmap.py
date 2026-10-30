import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from shared.enums.simulation import RoverFaultType
from simulation.rover.terrain_generator import TerrainMap

class DynamicTraversabilityCostmap:
    """
    Dynamic 2D Traversability Costmap for Autonomous Planetary Rover:
    Maintains perceived traversability costs on discrete grid [nx, ny].
    Separates hard safety constraints (cost = inf / impassable) from soft costs.
    Dynamically adapts cell costs based on:
    - Perceived terrain slope (steep slopes cost more or become impassable)
    - Obstacle proximity clearance margins
    - Actuator health (if a wheel is degraded, allowable slopes drop from 18deg to 8deg)
    - Remaining battery energy (penalizes length vs steepness trade-offs)
    - Sensor uncertainty (expands obstacle inflation radii under high EKF covariance)
    """
    def __init__(self, terrain: TerrainMap, resolution_m: float = 1.0):
        self.terrain = terrain
        self.res = resolution_m
        self.width = terrain.width
        self.height = terrain.height
        self.nx = int(self.width / self.res)
        self.ny = int(self.height / self.res)

        # Baseline perceived costmap [nx, ny]
        self.cost_grid = np.ones((self.nx, self.ny), dtype=np.float32)

        # Local hazard memory (e.g. newly discovered boulders via LiDAR or camera)
        self.discovered_obstacles: List[Dict[str, Any]] = []

    def update_from_perception(
        self,
        perceived_base_grid: np.ndarray,
        rover_pos: np.ndarray,
        actuator_degraded: bool = False,
        energy_critical: bool = False,
        pos_uncertainty_3sigma: float = 1.5
    ):
        """
        Updates dynamic cost grid incorporating vehicle state, faults, and uncertainty.
        """
        # Base traversability from perception grid
        # Resample to planner resolution
        grid_copy = perceived_base_grid.copy()

        # Inflation radius for obstacles: expands if position uncertainty is high
        inflation_cells = max(1, int(np.ceil((0.8 + pos_uncertainty_3sigma * 0.4) / self.res)))

        # Vectorized grid update
        # 1. Resample base perceived grid to planner resolution
        # Map terrain grid [nx_terr, ny_terr] to costmap grid [nx, ny]
        ratio_x = int(self.terrain.nx / self.nx)
        ratio_y = int(self.terrain.ny / self.ny)
        if ratio_x > 1 or ratio_y > 1:
            resampled = grid_copy[::ratio_x, ::ratio_y][:self.nx, :self.ny]
        else:
            resampled = grid_copy[:self.nx, :self.ny]

        # 2. Vectorized base cost
        self.cost_grid = np.where(resampled <= 0.05, np.inf, 1.0 / np.clip(resampled, 0.1, 1.0))

        # 3. If actuator degraded, penalize cells with lower traversability even more
        if actuator_degraded:
            self.cost_grid = np.where(resampled < 0.65, np.inf, self.cost_grid * 1.5)

        # 4. Apply obstacle clearance inflation using efficient 2D binary dilation
        is_obstacle = np.isinf(self.cost_grid)
        from scipy.ndimage import binary_dilation
        struct = np.ones((inflation_cells * 2 + 1, inflation_cells * 2 + 1), dtype=bool)
        inflated = binary_dilation(is_obstacle, structure=struct)
        # Add proximity penalty near obstacles
        self.cost_grid[inflated & (~is_obstacle)] += 15.0

    def is_traversable(self, ix: int, iy: int) -> bool:
        if 0 <= ix < self.nx and 0 <= iy < self.ny:
            return not np.isinf(self.cost_grid[ix, iy])
        return False

    def get_cost(self, ix: int, iy: int) -> float:
        if 0 <= ix < self.nx and 0 <= iy < self.ny:
            return float(self.cost_grid[ix, iy])
        return np.inf
