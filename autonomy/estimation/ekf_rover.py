import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from shared.schemas.rover import RoverSensors, RoverTrueState, RoverEKFState

class RoverEKF:
    """
    7-State Extended Kalman Filter for Autonomous Rover:
    State x = [px, py, pz, vx, vy, heading, omega_z]^T (7x1)

    Process Model:
    px_new = px + (vx * cos(h) - vy * sin(h)) * dt
    py_new = py + (vx * sin(h) + vy * cos(h)) * dt
    pz_new = terrain_elevation(px, py)
    vx_new = vx + a_x_body * dt
    vy_new = vy + a_y_body * dt
    heading_new = heading + omega_z * dt
    omega_z_new = omega_z

    Measurement Model:
    z = [v_odometry, omega_gyro, px_beacon, py_beacon]^T
    Uses Joseph stabilized covariance propagation.
    """
    def __init__(self, dt: float = 0.02, wheel_radius: float = 0.25):
        self.dt = dt
        self.R_wheel = wheel_radius
        self.dim = 7

        # State vector
        self.x = np.zeros(7, dtype=np.float64)

        # State error covariance P (7x7)
        self.P = np.diag([
            1.5**2, 1.5**2, 0.5**2, # pos variance
            0.2**2, 0.2**2,         # velocity variance
            np.radians(5.0)**2,     # heading variance
            0.02**2                 # angular velocity variance
        ])

        # Process noise covariance Q
        self.Q = np.diag([
            0.04, 0.04, 0.01,
            0.10, 0.10,
            0.005,
            0.008
        ]) * dt

        # Measurement noise covariance R
        self.R_cov = np.diag([
            0.08**2,            # wheel odometry speed variance
            np.radians(0.8)**2, # gyro yaw rate variance
            0.65**2, 0.65**2    # beacon/optical position variance
        ])

        self.last_innovation = np.zeros(4, dtype=np.float64)
        self.innovation_norm = 0.0

    def initialize(self, start_pos: List[float], start_heading: float = 0.0):
        self.x[0:3] = start_pos
        self.x[5] = start_heading

    def predict(self, imu_accel: np.ndarray, imu_gyro: np.ndarray):
        """Nonlinear state prediction step."""
        dt = self.dt
        h = self.x[5]
        vx = self.x[3]
        vy = self.x[4]
        omega_z = imu_gyro[2]

        c_h = np.cos(h)
        s_h = np.sin(h)

        # Longitudinal and lateral acceleration from IMU
        ax = imu_accel[0]
        ay = imu_accel[1]

        # Propagate states
        self.x[0] += (vx * c_h - vy * s_h) * dt
        self.x[1] += (vx * s_h + vy * c_h) * dt
        self.x[3] += ax * dt
        self.x[4] += ay * dt
        self.x[5] += omega_z * dt
        # Normalize heading
        self.x[5] = (self.x[5] + np.pi) % (2.0 * np.pi) - np.pi
        self.x[6] = omega_z

        # Jacobian F = df / dx
        F = np.eye(self.dim, dtype=np.float64)
        F[0, 3] = c_h * dt
        F[0, 4] = -s_h * dt
        F[0, 5] = (-vx * s_h - vy * c_h) * dt
        F[1, 3] = s_h * dt
        F[1, 4] = c_h * dt
        F[1, 5] = (vx * c_h - vy * s_h) * dt
        F[5, 6] = dt

        # Covariance prediction
        self.P = F @ self.P @ F.T + self.Q
        self.P = 0.5 * (self.P + self.P.T)

    def update(self, sensors: RoverSensors, ground_truth_beacon: Optional[np.ndarray] = None):
        """
        Measurement update from wheel encoders, gyroscope, and periodic position beacon.
        """
        # Wheel odometry speed is average of 6 encoders
        if sensors.wheel_encoders_rad_s:
            mean_encoder = float(np.mean(sensors.wheel_encoders_rad_s))
            v_odo = mean_encoder * self.R_wheel
        else:
            v_odo = self.x[3]

        gyro_z = sensors.imu_gyro[2]

        z_list = [v_odo, gyro_z]
        h_list = [self.x[3], self.x[6]]

        H_rows = [
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        ]
        R_diag = [self.R_cov[0, 0], self.R_cov[1, 1]]

        # Optional position reference (e.g. periodic orbital beacon/visual odometry)
        if ground_truth_beacon is not None and sensors.sensors_healthy:
            z_list.extend([ground_truth_beacon[0], ground_truth_beacon[1]])
            h_list.extend([self.x[0], self.x[1]])
            H_rows.append([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            H_rows.append([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
            R_diag.extend([self.R_cov[2, 2], self.R_cov[3, 3]])

        z = np.array(z_list, dtype=np.float64)
        h = np.array(h_list, dtype=np.float64)
        H = np.array(H_rows, dtype=np.float64)
        R_mat = np.diag(R_diag)

        # Innovation residual
        y = z - h
        self.last_innovation = y
        self.innovation_norm = float(np.linalg.norm(y))

        # Innovation covariance S = H * P * H^T + R
        S = H @ self.P @ H.T + R_mat

        # Kalman gain K = P * H^T * S^-1
        try:
            K = self.P @ H.T @ np.linalg.inv(S)
        except np.linalg.LinAlgError:
            K = self.P @ H.T @ np.linalg.pinv(S)

        # State update
        self.x += K @ y
        self.x[5] = (self.x[5] + np.pi) % (2.0 * np.pi) - np.pi

        # Joseph form covariance update
        I_KH = np.eye(self.dim) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R_mat @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    def get_telemetry(self, true_state: RoverTrueState) -> RoverEKFState:
        """Returns typed telemetry comparing estimated state to ground truth."""
        pos_err = (self.x[0:3] - np.array(true_state.position)).tolist()
        h_diff = self.x[5] - true_state.euler[2]
        h_diff = float((h_diff + np.pi) % (2.0 * np.pi) - np.pi)

        cov_diag = np.diag(self.P).tolist()
        pos_var = cov_diag[0] + cov_diag[1]
        pos_3sigma = float(3.0 * np.sqrt(max(0.0, pos_var / 2.0)))
        heading_3sigma = float(3.0 * np.sqrt(max(0.0, cov_diag[5])))

        return RoverEKFState(
            time=true_state.time,
            position=self.x[0:3].tolist(),
            linear_velocity=[float(self.x[3]), float(self.x[4]), 0.0],
            heading_rad=float(self.x[5]),
            pitch_rad=float(true_state.euler[1]),
            roll_rad=float(true_state.euler[0]),
            position_error=pos_err,
            heading_error=h_diff,
            covariance_diag=cov_diag,
            position_uncertainty_3sigma=pos_3sigma,
            heading_uncertainty_3sigma=heading_3sigma,
            innovation_norm=self.innovation_norm
        )
