import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from shared.schemas.rover import RoverSensors
from simulation.rover.rover_physics_engine import RoverDynamicPhysicsEngine

class RoverSensorSuite:
    """
    Simulated sensor payload for autonomous planetary rover:
    1. IMU: 3-axis linear acceleration + 3-axis gyroscope with bias & white noise.
    2. Wheel Encoders: 6 rotary encoders measuring wheel rotational velocities [rad/s].
    3. LiDAR Scanner: 36-beam 360-degree radial distance scanner detecting obstacles up to 25m.
    4. Optical Perception Camera: local traversability grid perception.
    5. Battery Management System (BMS): telemetry for voltage, current, and SoC.
    Supports FAULT 01 (Sensor Dropout): drops LiDAR points and marks sensors invalid.
    """
    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)

        # Noise parameters
        self.accel_noise_std = 0.05       # m/s^2
        self.gyro_noise_std = 0.002       # rad/s (~0.1 deg/s)
        self.encoder_noise_std = 0.02     # rad/s
        self.lidar_noise_std = 0.08       # meters
        self.bms_voltage_noise = 0.05     # Volts
        self.bms_current_noise = 0.1      # Amps

        # Biases
        self.accel_bias = np.array([0.015, -0.01, 0.02])
        self.gyro_bias = np.array([-0.0008, 0.001, 0.0005])

        # Fault state
        self.sensor_dropout_active = False

    def set_dropout(self, active: bool):
        """Toggles FAULT 01 (Sensor dropout)."""
        self.sensor_dropout_active = active

    @property
    def sensors_healthy(self) -> bool:
        """Returns True if sensors are operating nominally, False if FAULT 01 sensor dropout is active."""
        return not self.sensor_dropout_active

    def sample(self, physics: RoverDynamicPhysicsEngine) -> RoverSensors:
        time = physics.time

        # 1. IMU Accelerations (Body frame)
        # Specific force: a_body = R * a_world - g
        g_acc = 3.71
        a_fwd = (physics.vel[0] * np.cos(physics.heading) + physics.vel[1] * np.sin(physics.heading))
        # Forward and lateral accelerations with pitch/roll components
        acc_x = (a_fwd / 0.1) * 0.05 + g_acc * np.sin(physics.pitch)
        acc_y = g_acc * np.sin(physics.roll)
        acc_z = g_acc * np.cos(physics.pitch) * np.cos(physics.roll)
        raw_acc = np.array([acc_x, acc_y, acc_z]) + self.accel_bias + self.rng.normal(0, self.accel_noise_std, size=3)

        # Gyroscope
        raw_gyro = np.array([0.0, 0.0, physics.omega_z]) + self.gyro_bias + self.rng.normal(0, self.gyro_noise_std, size=3)

        # 2. Wheel Encoders (6 wheels)
        encoder_readings = []
        for w_name in physics.wheel_names:
            true_omega = physics.wheel_omegas[w_name]
            noise = self.rng.normal(0, self.encoder_noise_std)
            encoder_readings.append(float(true_omega + noise))

        # 3. LiDAR Range Scan (36 beams spanning 360 degrees)
        lidar_ranges = []
        max_lidar_range = 25.0
        angles = np.linspace(-np.pi, np.pi, 36, endpoint=False)

        if not self.sensor_dropout_active:
            for angle in angles:
                beam_dir = physics.heading + angle
                dx = np.cos(beam_dir)
                dy = np.sin(beam_dir)
                # Raycast against known terrain obstacles
                min_dist = max_lidar_range
                for obs in physics.terrain.obstacles:
                    # Vector from rover to obstacle center
                    v_to_obs = obs["pos"] - physics.pos[0:2]
                    # Project along beam
                    proj = np.dot(v_to_obs, np.array([dx, dy]))
                    if proj > 0:
                        perp = np.linalg.norm(v_to_obs - proj * np.array([dx, dy]))
                        if perp <= obs["radius"]:
                            dist = max(0.2, proj - np.sqrt(max(0.0, obs["radius"]**2 - perp**2)))
                            if dist < min_dist:
                                min_dist = dist

                # Add measurement noise
                measured_dist = min_dist + self.rng.normal(0, self.lidar_noise_std)
                lidar_ranges.append(float(np.clip(measured_dist, 0.2, max_lidar_range)))
            lidar_count = 36
            sensors_healthy = True
        else:
            # During FAULT 01 sensor dropout, LiDAR returns zeros or nulls
            lidar_ranges = [0.0] * 36
            lidar_count = 0
            sensors_healthy = False

        # 4. BMS Telemetry
        soc = physics.battery_energy_wh / physics.battery_capacity_wh
        v_telemetry = physics.battery_voltage + self.rng.normal(0, self.bms_voltage_noise)
        current = physics.power_draw_w / max(10.0, physics.battery_voltage)
        i_telemetry = current + self.rng.normal(0, self.bms_current_noise)

        return RoverSensors(
            time=time,
            imu_accel=raw_acc.tolist(),
            imu_gyro=raw_gyro.tolist(),
            wheel_encoders_rad_s=encoder_readings,
            lidar_points_count=lidar_count,
            lidar_obstacle_ranges=lidar_ranges,
            camera_traversability_grid_received=not self.sensor_dropout_active,
            battery_soc_telemetry=float(np.clip(soc, 0.0, 1.0)),
            battery_current_a=float(max(0.0, i_telemetry)),
            battery_voltage_v=float(max(0.0, v_telemetry)),
            sensors_healthy=sensors_healthy,
            dropout_active=self.sensor_dropout_active
        )
