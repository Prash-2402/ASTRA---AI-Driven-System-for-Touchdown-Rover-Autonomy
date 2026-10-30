import numpy as np
from typing import Tuple, List, Dict, Any
from scipy.optimize import minimize

class ModelPredictiveTouchdownController:
    """
    Constrained Receding-Horizon Model Predictive Controller (MPC) for Lander EDL:
    - Horizon N = 12 steps (prediction horizon)
    - Optimization vector: candidate sequence of throttles and attitude pitch/roll angles
    - Dynamics: linearized discrete-time point-mass & attitude kinematic prediction
    - Cost function:
      J = sum_k [ ||p_k - p_target||^2_Qp + ||v_k - v_ref_k||^2_Qv + R_u * (u_k - u_hover)^2 ]
          + ||p_N - p_target||^2_Qf + ||v_N - v_N_target||^2_Qvf
    - Constraints:
      0.15 <= u_k <= 1.0 (throttle limits)
      |pitch_k| <= 20 deg, |roll_k| <= 20 deg
      Terminal descent velocity <= 2.0 m/s
    """
    def __init__(
        self,
        dt_control: float = 0.1,
        horizon_steps: int = 12,
        gravity: float = 3.71,
        max_thrust: float = 5500.0
    ):
        self.dt = dt_control
        self.N = horizon_steps
        self.g = gravity
        self.max_thrust = max_thrust

        # Weighting matrices
        self.w_pos = np.array([2.5, 2.5, 5.0])
        self.w_vel = np.array([1.2, 1.2, 3.5])
        self.w_thrust = 0.05
        self.w_terminal_pos = 15.0
        self.w_terminal_vel = 25.0

        # Memory of previous optimal solution for warm starting
        self.u_prev = np.full(self.N, 0.45)
        self.pitch_prev = np.zeros(self.N)
        self.roll_prev = np.zeros(self.N)

        # Attitude rate tracking gains for RCS execution
        self.kp_att = 750.0
        self.kd_att = 400.0

    def compute_control(
        self,
        current_pos: np.ndarray,
        current_vel: np.ndarray,
        current_euler: np.ndarray,
        current_omega: np.ndarray,
        target_site: np.ndarray,
        current_mass: float
    ) -> Tuple[float, np.ndarray, List[List[float]]]:
        """
        Solves MPC optimization problem and returns:
        (throttle_command, rcs_torque_command, predicted_trajectory)
        """
        N = self.N
        dt = self.dt
        m = max(100.0, current_mass)
        u_hover = (m * self.g) / self.max_thrust

        # Reference trajectory generation over horizon
        alt = current_pos[2] - target_site[2]
        vz_ref_base = -1.5 if alt < 25.0 else -8.0 if alt < 150.0 else -20.0

        # Optimization variables: X = [u_0..u_{N-1}, pitch_0..pitch_{N-1}, roll_0..roll_{N-1}] (3*N)
        x0 = np.concatenate([self.u_prev, self.pitch_prev, self.roll_prev])

        bounds = []
        # Throttle bounds [0.15, 1.0]
        for _ in range(N):
            bounds.append((0.15, 1.0))
        # Pitch bounds [-20 deg, 20 deg]
        max_tilt = np.radians(20.0)
        for _ in range(N):
            bounds.append((-max_tilt, max_tilt))
        # Roll bounds [-20 deg, 20 deg]
        for _ in range(N):
            bounds.append((-max_tilt, max_tilt))

        def objective(x_opt):
            u_seq = x_opt[0:N]
            pitch_seq = x_opt[N:2*N]
            roll_seq = x_opt[2*N:3*N]

            p = current_pos.copy()
            v = current_vel.copy()
            cost = 0.0

            for k in range(N):
                u = u_seq[k]
                th = pitch_seq[k]
                phi = roll_seq[k]

                # Accelerations from thrust and gravity
                f_thrust = u * self.max_thrust
                # Accelerations in world frame
                ax = (-f_thrust * np.sin(th)) / m
                ay = (f_thrust * np.sin(phi)) / m
                az = (f_thrust * np.cos(th) * np.cos(phi) - m * self.g) / m
                a = np.array([ax, ay, az])

                # State update
                p += v * dt + 0.5 * a * (dt**2)
                v += a * dt

                # Stage cost
                err_p = p - target_site
                err_v = v - np.array([0.0, 0.0, vz_ref_base])

                cost += np.sum(self.w_pos * (err_p**2))
                cost += np.sum(self.w_vel * (err_v**2))
                cost += self.w_thrust * ((u - u_hover)**2)

            # Terminal cost
            err_p_term = p - target_site
            cost += self.w_terminal_pos * np.sum(err_p_term**2)
            cost += self.w_terminal_vel * (v[2] - (-0.8))**2 # soft touchdown velocity
            return cost

        res = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            options={'maxiter': 25, 'ftol': 1e-3, 'disp': False}
        )

        if res.success:
            u_opt = res.x[0:N]
            pitch_opt = res.x[N:2*N]
            roll_opt = res.x[2*N:3*N]
        else:
            # Fallback to previous shifted solution or proportional hover
            u_opt = np.roll(self.u_prev, -1)
            u_opt[-1] = u_hover
            pitch_opt = np.roll(self.pitch_prev, -1)
            pitch_opt[-1] = 0.0
            roll_opt = np.roll(self.roll_prev, -1)
            roll_opt[-1] = 0.0

        # Store for next warm start
        self.u_prev = u_opt
        self.pitch_prev = pitch_opt
        self.roll_prev = roll_opt

        # First control actions
        throttle_cmd = float(u_opt[0])
        des_pitch = float(pitch_opt[0])
        des_roll = float(roll_opt[0])

        if alt < 10.0:
            des_pitch *= (alt / 10.0)
            des_roll *= (alt / 10.0)

        desired_euler = np.array([des_roll, des_pitch, 0.0])
        err_att = desired_euler - current_euler
        err_att = (err_att + np.pi) % (2.0 * np.pi) - np.pi
        rcs_torques = self.kp_att * err_att - self.kd_att * current_omega
        rcs_torques = np.clip(rcs_torques, -120.0, 120.0)

        # Compute predicted trajectory for visualization
        predicted_traj = []
        p_pred = current_pos.copy()
        v_pred = current_vel.copy()
        for k in range(N):
            predicted_traj.append(p_pred.tolist())
            u = u_opt[k]
            th = pitch_opt[k]
            phi = roll_opt[k]
            f_thrust = u * self.max_thrust
            ax = (-f_thrust * np.sin(th)) / m
            ay = (f_thrust * np.sin(phi)) / m
            az = (f_thrust * np.cos(th) * np.cos(phi) - m * self.g) / m
            a = np.array([ax, ay, az])
            p_pred += v_pred * dt + 0.5 * a * (dt**2)
            v_pred += a * dt

        return throttle_cmd, rcs_torques, predicted_traj
