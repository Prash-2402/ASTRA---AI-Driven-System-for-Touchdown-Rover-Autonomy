import numpy as np
from typing import List, Tuple, Optional

class PurePursuitController:
    """
    Pure Pursuit Path Tracking and Velocity Regulation for Planetary Rover:
    - Calculates lookahead point on planned path
    - Regulates heading error via circular arc steering curvature: kappa = 2 * sin(alpha) / L_d
    - Speed profiling: slows down smoothly when turning sharply or approaching science target.
    """
    def __init__(
        self,
        lookahead_distance: float = 2.2,
        max_speed: float = 0.75,
        max_yaw_rate: float = 0.65
    ):
        self.L_d = lookahead_distance
        self.max_speed = max_speed
        self.max_yaw_rate = max_yaw_rate

        self.current_waypoint_idx = 0

    def compute_motion_command(
        self,
        current_pos: np.ndarray,
        current_heading: float,
        planned_path: List[List[float]],
        speed_limit_factor: float = 1.0
    ) -> Tuple[float, float, bool]:
        """
        Returns (commanded_speed, commanded_yaw_rate, target_reached)
        """
        if not planned_path or len(planned_path) == 0:
            return 0.0, 0.0, True

        # Check distance to final goal
        final_goal = np.array(planned_path[-1])
        dist_to_final = float(np.linalg.norm(current_pos[0:2] - final_goal))
        if dist_to_final <= 1.2:
            return 0.0, 0.0, True

        # Find closest path waypoint ahead of vehicle
        num_pts = len(planned_path)
        lookahead_pt = None

        # Search from current waypoint onwards
        for i in range(self.current_waypoint_idx, num_pts):
            pt = np.array(planned_path[i])
            d = np.linalg.norm(pt - current_pos[0:2])
            if d >= self.L_d:
                lookahead_pt = pt
                self.current_waypoint_idx = i
                break

        if lookahead_pt is None:
            # Reached end of lookahead, target last waypoint
            lookahead_pt = final_goal
            self.current_waypoint_idx = num_pts - 1

        # Vector from rover to lookahead point in world frame
        dx = lookahead_pt[0] - current_pos[0]
        dy = lookahead_pt[1] - current_pos[1]

        # Target angle in world frame
        target_angle = np.arctan2(dy, dx)

        # Heading error alpha in vehicle frame [-pi, pi]
        alpha = target_angle - current_heading
        alpha = (alpha + np.pi) % (2.0 * np.pi) - np.pi

        # Pure pursuit curvature: kappa = 2 * sin(alpha) / L_d
        d_look = max(0.5, float(np.linalg.norm(lookahead_pt - current_pos[0:2])))
        kappa = (2.0 * np.sin(alpha)) / d_look

        # Speed profiling: reduce speed on sharp turns or near final goal
        turn_slowdown = max(0.25, np.cos(alpha)**2)
        goal_slowdown = min(1.0, max(0.3, dist_to_final / 4.0))

        v_cmd = self.max_speed * speed_limit_factor * turn_slowdown * goal_slowdown
        # Yaw rate command = v * kappa
        omega_cmd = v_cmd * kappa
        omega_cmd = float(np.clip(omega_cmd, -self.max_yaw_rate, self.max_yaw_rate))

        return float(v_cmd), float(omega_cmd), False
