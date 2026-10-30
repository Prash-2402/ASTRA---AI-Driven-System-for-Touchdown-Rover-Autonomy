import numpy as np
from shared.schemas.touchdown import LanderSensors
from simulation.touchdown.physics import Lander6DoFPhysics, quaternion_to_rotation_matrix, quaternion_to_euler

class LanderSensorSuite:
    """
    Simulated planetary lander sensor suite with realistic sensor physics:
    - IMU 3-axis Accelerometer & Gyroscope (bias drift, Gaussian white noise)
    - Radar Altimeter (terrain range, altitude dropout at high bank angles)
    - Doppler Velocity Radar (3-axis velocity tracking)
    - Surface Beacon / Optical Terrain Position Radar
    - Fuel Telemetry Gauge
    Strictly separates sensor observations from ground truth.
    """
    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)

        # Sensor Noise Standard Deviations
        self.accel_noise_std = 0.08      # m/s^2
        self.accel_bias = np.array([0.02, -0.015, 0.03], dtype=np.float64)

        self.gyro_noise_std = 0.003      # rad/s (~0.17 deg/s)
        self.gyro_bias = np.array([-0.001, 0.0015, 0.0008], dtype=np.float64)

        self.altimeter_noise_std = 0.45  # meters
        self.radar_vel_noise_std = 0.12  # m/s
        self.radar_pos_noise_std = 0.85  # meters
        self.fuel_noise_std = 0.25       # kg

        # Sensor health & degradation flags
        self.dropout_active = False

    def sample(self, physics: Lander6DoFPhysics) -> LanderSensors:
        time = physics.time
        pos_true = physics.pos
        vel_true = physics.vel
        q_true = physics.quat
        omega_true = physics.omega
        surface_elev = physics.env.get_surface_elevation(pos_true[0], pos_true[1])
        true_altitude = pos_true[2] - surface_elev

        R_body_to_world = quaternion_to_rotation_matrix(q_true)
        R_world_to_body = R_body_to_world.T

        # 1. IMU Accelerometer: measures specific force in body frame
        # f_specific = R_world_to_body * (a_world - g_world)
        g_world = np.array([0.0, 0.0, -physics.env.gravity])
        a_specific_world = physics.last_accel - g_world
        a_specific_body = R_world_to_body @ a_specific_world
        accel_noise = self.rng.normal(0.0, self.accel_noise_std, size=3)
        imu_accel = a_specific_body + self.accel_bias + accel_noise

        # 2. IMU Gyroscope: measures body angular rate
        gyro_noise = self.rng.normal(0.0, self.gyro_noise_std, size=3)
        imu_gyro = omega_true + self.gyro_bias + gyro_noise

        # 3. Radar Altimeter: degraded or dropped if lander attitude > 30 degrees tilt
        euler = quaternion_to_euler(q_true)
        tilt_angle = np.linalg.norm(euler[0:2])
        if tilt_angle > np.radians(35.0) or self.dropout_active:
            altimeter_reading = -1.0 # Invalid / dropout
            valid = False
        else:
            alt_noise = self.rng.normal(0.0, self.altimeter_noise_std)
            altimeter_reading = max(0.0, float(true_altitude + alt_noise))
            valid = True

        # 4. Doppler Velocity Radar
        vel_noise = self.rng.normal(0.0, self.radar_vel_noise_std, size=3)
        velocity_measured = (vel_true + vel_noise).tolist()

        # 5. Position Radar / Range Sensor
        pos_noise = self.rng.normal(0.0, self.radar_pos_noise_std, size=3)
        position_radar = (pos_true + pos_noise).tolist()

        # 6. Fuel Telemetry
        fuel_noise = self.rng.normal(0.0, self.fuel_noise_std)
        fuel_telemetry = max(0.0, float(physics.fuel_mass + fuel_noise))

        return LanderSensors(
            time=time,
            altimeter=altimeter_reading,
            imu_accel=imu_accel.tolist(),
            imu_gyro=imu_gyro.tolist(),
            velocity_measured=velocity_measured,
            position_radar=position_radar,
            radar_terrain_range=altimeter_reading,
            fuel_sensor=fuel_telemetry,
            valid=valid
        )
