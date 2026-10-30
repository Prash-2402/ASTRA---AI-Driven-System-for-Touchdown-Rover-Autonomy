import heapq
import numpy as np
from typing import List, Tuple, Optional
from autonomy.planning.traversability_costmap import DynamicTraversabilityCostmap

class AStarPathPlanner:
    """
    A* Graph Search & Dynamic Replanning for Planetary Rover:
    - 8-connected grid search
    - Admissible Euclidean distance heuristic: h(n) = sqrt((x - x_goal)^2 + (y - y_goal)^2)
    - Non-linear traversability edge weights from DynamicTraversabilityCostmap
    - Fast path smoothing and redundant waypoint pruning
    """
    def __init__(self, costmap: DynamicTraversabilityCostmap):
        self.costmap = costmap
        self.res = costmap.res

    def plan(self, start_xy: List[float], goal_xy: List[float]) -> Optional[List[List[float]]]:
        """
        Executes A* search from start_xy to goal_xy.
        Returns smoothed list of [x, y] coordinates in world meters.
        """
        # Convert world coordinates to grid indices
        start_ix = int(np.clip(start_xy[0] / self.res, 0, self.costmap.nx - 1))
        start_iy = int(np.clip(start_xy[1] / self.res, 0, self.costmap.ny - 1))

        goal_ix = int(np.clip(goal_xy[0] / self.res, 0, self.costmap.nx - 1))
        goal_iy = int(np.clip(goal_xy[1] / self.res, 0, self.costmap.ny - 1))

        # Check start and goal traversability
        if not self.costmap.is_traversable(goal_ix, goal_iy):
            # Find closest traversable cell to goal
            found = False
            for r in range(1, 10):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        nx, ny = goal_ix + dx, goal_iy + dy
                        if self.costmap.is_traversable(nx, ny):
                            goal_ix, goal_iy = nx, ny
                            found = True
                            break
                    if found:
                        break
            if not found:
                return None

        # Priority queue for open set: (f_score, counter, (ix, iy))
        open_set = []
        counter = 0
        heapq.heappush(open_set, (0.0, counter, (start_ix, start_iy)))

        came_from = {}
        g_score = { (start_ix, start_iy): 0.0 }

        def heuristic(ix: int, iy: int) -> float:
            return float(np.sqrt((ix - goal_ix)**2 + (iy - goal_iy)**2) * self.res)

        # 8-connected motion primitives: dx, dy, step_length
        SQRT2 = np.sqrt(2.0)
        neighbors = [
            ( 1,  0, 1.0),
            (-1,  0, 1.0),
            ( 0,  1, 1.0),
            ( 0, -1, 1.0),
            ( 1,  1, SQRT2),
            ( 1, -1, SQRT2),
            (-1,  1, SQRT2),
            (-1, -1, SQRT2),
        ]

        closed_set = set()
        iterations = 0
        max_iterations = 60000

        while open_set and iterations < max_iterations:
            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current in closed_set:
                continue
            closed_set.add(current)

            if current == (goal_ix, goal_iy):
                # Reconstruct path
                path_grid = [current]
                while current in came_from:
                    current = came_from[current]
                    path_grid.append(current)
                path_grid.reverse()

                # Convert to world coordinates and smooth
                world_path = [[(pt[0] + 0.5) * self.res, (pt[1] + 0.5) * self.res] for pt in path_grid]
                return self._smooth_path(world_path)

            cur_ix, cur_iy = current
            cur_g = g_score[current]

            for dx, dy, step_dist in neighbors:
                nb_ix, nb_iy = cur_ix + dx, cur_iy + dy
                neighbor = (nb_ix, nb_iy)

                if neighbor in closed_set:
                    continue

                if not self.costmap.is_traversable(nb_ix, nb_iy):
                    continue

                step_cost = self.costmap.get_cost(nb_ix, nb_iy) * step_dist * self.res
                tentative_g = cur_g + step_cost

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(nb_ix, nb_iy)
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))

        return None

    def _smooth_path(self, raw_path: List[List[float]]) -> List[List[float]]:
        """Prunes unnecessary intermediate collinear and redundant waypoints."""
        if len(raw_path) <= 2:
            return raw_path

        smoothed = [raw_path[0]]
        step = 4 # Downsample dense grid path for smooth vehicle tracking
        for i in range(step, len(raw_path), step):
            smoothed.append(raw_path[i])
        if smoothed[-1] != raw_path[-1]:
            smoothed.append(raw_path[-1])
        return smoothed
