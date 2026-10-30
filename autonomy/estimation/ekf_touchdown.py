import numpy as np
from typing import Tuple, Dict, Any, List
from shared.schemas.touchdown import EKFStateEstimate, LanderSensors, LanderState

class TouchdownEKF:
    """
    9-State Extended Kalman Filter for Planetary Lander EDL:
    States x = [px, py, pz, vx, vy, vz, roll, pitch, yaw]^T (9x1)

    Prediction model:
    dot(p) = v
    dot(v) = R(euler) * a_imu_body + [0, 0, -g]
    dot(euler) = T(euler) * omega_imu_body

    Measurement model:
    z = [altimeter_z, v_radar_x, v_radar_y, v_radar_z, pos_radar_x, pos_radar_y]^T
    Uses Joseph stabilized covariance update: P = (I - KH) P (I - KH)^T + K R K^T
    """
    def __init__(self, dt: float = 0.02, gravity: float = 3.71):
        self.dt = dt
        self.g = gravity
        self.dim_x = 9

        # State vector [px, py, pz, vx, vy, vz, roll, pitch, yaw]
        self.x = np.zeros(9, dtype=np.float64)

        # State Error Covariance Matrix P (9x9)
        self.P = np.diag([
            25.0, 25.0, 10.0,    # pos var (5m, 5m, 3.16m std)
            4.0, 4.0, 4.0,       # vel var (2m/s std)
            0.05, 0.05, 0.05     # attitude var (~12 deg std)
        ])

        # Process Noise Covariance Q (9x9)
        q_pos = 0.01
        q_vel = 0.15
        q_att = 0.002
        self.Q = np.diag([
            q_pos, q_pos, q_pos,
            q_vel, q_vel, q_vel,
            q_att, q_att, q_att
        ]) * dt

        # Measurement Noise Covariance R (6x6)
        # measurements: [altimeter_z, vx, vy, vz, px, py]
        self.R = np.diag([
            0.5**2,              # altimeter variance
            0.15**2, 0.15**2, 0.15**2, # Doppler velocity variance
            1.2**2, 1.2**2       # radar horizontal position variance
        ])

        self.last_innovation = np.zeros(6, dtype=np.float64)
        self.innovation_covariance = np.eye(6, dtype=np.float64)

    def initialize(self, initial_pos: List[float], initial_vel: List[float], initial_euler: List[float]):
        self.x[0:3] = initial_pos
        self.x[3:6] = initial_vel
        self.x[6:9] = initial_euler

    def predict(self, imu_accel: np.ndarray, imu_gyro: np.ndarray):
        """
        Nonlinear state transition and Jacobian evaluation.
        f(x, u):
        px_new = px + vx * dt
        vx_new = vx + (R * a_body + g_world) * dt
        euler_new = euler + (T * w_body) * dt
        """
        dt = self.dt
        phi, theta, psi = self.x[6], self.x[7], self.x[8]

        # Rotation matrix from body to world
        c_phi, s_phi = np.cos(phi), np.sin(phi)
        c_th, s_th = np.cos(theta), np.sin(theta)
        c_psi, s_psi = np.cos(psi), np.sin(psi)

        R = np.array([
            [c_th*c_psi, s_phi*s_th*c_psi - c_phi*s_psi, c_phi*s_th*c_psi + s_phi*s_psi],
            [c_th*s_psi, s_phi*s_th*s_psi + c_phi*c_psi, c_phi*s_th*s_psi - s_phi*c_psi],
            [-s_th,      s_phi*c_th,                      c_phi*c_th]
        ], dtype=np.float64)

        # Angular rate kinematics matrix T
        t_th = np.tan(theta) if np.abs(np.cos(theta)) > 1e-4 else 0.0
        sec_th = 1.0 / np.cos(theta) if np.abs(np.cos(theta)) > 1e-4 else 1.0
        T = np.array([
            [1.0, s_phi * t_th, c_phi * t_th],
            [0.0, c_phi,        -s_phi],
            [0.0, s_phi * sec_th, c_phi * sec_th]
        ], dtype=np.float64)

        # Acceleration in world frame
        a_world = R @ imu_accel + np.array([0.0, 0.0, -self.g])
        d_euler = T @ imu_gyro

        # Nonlinear State Propagation
        self.x[0:3] += self.x[3:6] * dt + 0.5 * a_world * (dt**2)
        self.x[3:6] += a_world * dt
        self.x[6:9] += d_euler * dt

        # State transition Jacobian F = df / dx
        F = np.eye(self.dim_x, dtype=np.float64)
        F[0:3, 3:6] = np.eye(3) * dt

        # Derivatives of R @ imu_accel with respect to Euler angles
        # Approximate attitude-coupling submatrices for stability
        ax, ay, az = imu_accel
        F[3, 6] = (c_phi*s_th*c_psi + s_phi*s_psi)*ay + (-s_phi*s_th*c_psi + c_phi*s_psi)*az
        F[3, 7] = -s_th*c_psi*ax + s_phi*c_th*c_psi*ay + c_phi*c_th*c_psi*az
        F[4, 6] = (c_phi*s_th*s_psi - s_phi*c_psi)*ay + (-s_phi*s_th*s_psi - c_phi*c_psi)*az
        F[4, 7] = -s_th*s_psi*ax + s_phi*c_th*s_psi*ay + c_phi*c_th*s_psi*az
        F[5, 6] = c_phi*c_th*ay - s_phi*c_th*az
        F[5, 7] = -c_th*ax - s_phi*s_th*ay - c_phi*s_th*az
        F[3:6, 6:9] *= dt

        # Propagate Covariance: P = F * P * F^T + Q
        self.P = F @ self.P @ F.T + self.Q

        # Ensure symmetry
        self.P = 0.5 * (self.P + self.P.T)

    def update(self, sensors: LanderSensors, surface_elevation: float):
        """
        Measurement update step.
        Measurement vector: z = [pz_altimeter, vx, vy, vz, px, py]^T (6x1)
        """
        z_list = []
        h_list = []
        H_rows = []
        R_diag = []

        # 1. Altimeter measurement (altitude above local terrain)
        if sensors.altimeter >= 0.0 and sensors.valid:
            # Expected altitude is pz - surface_elev
            z_list.append(sensors.altimeter)
            h_list.append(self.x[2] - surface_elevation)
            h_row = np.zeros(self.dim_x)
            h_row[2] = 1.0 # d(pz)/d(pz)
            H_rows.append(h_row)
            R_diag.append(self.R[0, 0])

        # 2. Doppler Velocity Radar measurements
        if sensors.velocity_measured:
            for i in range(3):
                z_list.append(sensors.velocity_measured[i])
                h_list.append(self.x[3 + i])
                h_row = np.zeros(self.dim_x)
                h_row[3 + i] = 1.0
                H_rows.append(h_row)
                R_diag.append(self.R[1 + i, 1 + i])

        # 3. Horizontal Position Radar
        if sensors.position_radar:
            for i in range(2):
                z_list.append(sensors.position_radar[i])
                h_list.append(self.x[i])
                h_row = np.zeros(self.dim_x)
                h_row[i] = 1.0
                H_rows.append(h_row)
                R_diag.append(self.R[4 + i, 4 + i])

        if not z_list:
            return

        z = np.array(z_list, dtype=np.float64)
        h = np.array(h_list, dtype=np.float64)
        H = np.array(H_rows, dtype=np.float64)
        R_mat = np.diag(R_diag)

        # Innovation: y = z - h
        y = z - h
        self.last_innovation = y

        # Innovation Covariance: S = H * P * H^T + R
        S = H @ self.P @ H.T + R_mat
        self.innovation_covariance = S

        # Kalman Gain: K = P * H^T * S^-1
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.P @ H.T @ np.linalg.pinv(S)

        # State Update: x = x + K * y
        self.x += K @ y

        # Joseph Form Covariance Update for guaranteed positive semi-definiteness:
        # P = (I - K*H) * P * (I - K*H)^T + K * R * K^T
        I_KH = np.eye(self.dim_x) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R_mat @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    def get_estimate_telemetry(self, true_state: LanderState) -> EKFStateEstimate:
        """Returns typed telemetry comparing estimate vs ground truth with 3-sigma bounds."""
        pos_est = self.x[0:3].tolist()
        vel_est = self.x[3:6].tolist()
        att_est = self.x[6:9].tolist()

        pos_err = (self.x[0:3] - np.array(true_state.position)).tolist()
        vel_err = (self.x[3:6] - np.array(true_state.velocity)).tolist()
        att_err = (self.x[6:9] - np.array(true_state.euler)).tolist()

        cov_diag = np.diag(self.P).tolist()
        pos_var_sum = cov_diag[0] + cov_diag[1] + cov_diag[2]
        vel_var_sum = cov_diag[3] + cov_diag[4] + cov_diag[5]

        pos_3sigma = float(3.0 * np.sqrt(max(0.0, pos_var_sum / 3.0)))
        vel_3sigma = float(3.0 * np.sqrt(max(0.0, vel_var_sum / 3.0)))

        return EKFStateEstimate(
            time=true_state.time,
            estimated_position=pos_est,
            estimated_velocity=vel_est,
            estimated_euler=att_est,
            position_error=pos_err,
            velocity_error=vel_err,
            euler_error=att_err,
            covariance_diag=cov_diag,
            position_uncertainty_3sigma=pos_3sigma,
            velocity_uncertainty_3sigma=vel_3sigma
        )
