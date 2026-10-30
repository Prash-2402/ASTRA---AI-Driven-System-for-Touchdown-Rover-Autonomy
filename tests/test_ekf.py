"""Unit tests for Extended Kalman Filters (EKF) in ASTRA Touchdown and Rover modules."""
import pytest
import numpy as np
from autonomy.estimation.ekf_touchdown import TouchdownEKF
from autonomy.estimation.ekf_rover import RoverEKF
from shared.schemas.touchdown import LanderSensors
from shared.schemas.rover import RoverSensors

def test_touchdown_ekf_prediction_and_update():
    ekf = TouchdownEKF(dt=0.02, gravity=3.71)
    ekf.initialize(initial_pos=[0.0, 0.0, 1500.0], initial_vel=[0.0, 0.0, -25.0], initial_euler=[0.0, 0.0, 0.0])
    
    assert ekf.P.shape == (9, 9)
    assert np.all(np.linalg.eigvals(ekf.P) >= 0.0), "Covariance must be positive semi-definite"
    
    # Predict step with typical Mars gravity and net acceleration
    accel_meas = np.array([0.1, 0.0, 2.0])
    gyro_meas = np.array([0.01, 0.0, 0.0])
    
    ekf.predict(imu_accel=accel_meas, imu_gyro=gyro_meas)
    assert ekf.x[5] < 0.0, "Vertical velocity should remain negative downwards"
    
    # Update with altimeter and radar measurements
    sensors = LanderSensors(
        time=0.02,
        altimeter=1498.0,
        imu_accel=[0.1, 0.0, 2.0],
        imu_gyro=[0.01, 0.0, 0.0],
        velocity_measured=[0.0, 0.0, -24.8],
        position_radar=[0.0, 0.0],
        radar_terrain_range=1498.0,
        fuel_sensor=350.0,
        valid=True
    )
    ekf.update(sensors=sensors, surface_elevation=0.0)
    
    # Check Joseph form stability: covariance must remain symmetric and positive semi-definite
    assert np.allclose(ekf.P, ekf.P.T, atol=1e-5)
    eigvals = np.linalg.eigvals(ekf.P)
    assert np.all(eigvals >= -1e-6), f"Eigenvalues must be non-negative: {eigvals}"

def test_rover_ekf_prediction_and_update():
    ekf = RoverEKF(dt=0.02, wheel_radius=0.25)
    ekf.initialize(start_pos=[10.0, 10.0, 0.0], start_heading=0.0)
    
    assert ekf.P.shape == (7, 7)
    assert np.all(np.linalg.eigvals(ekf.P) >= 0.0)
    
    # Predict forward motion: speed 0.5 m/s, forward accel
    for _ in range(10):
        ekf.predict(imu_accel=np.array([0.2, 0.0, 0.0]), imu_gyro=np.array([0.0, 0.0, 0.02]))
        
    assert ekf.x[3] > 0.0, "Forward velocity should increase with positive ax"
    assert ekf.x[5] > 0.0, "Yaw angle should increase with positive yaw rate"
    
    # Update with sensors
    sensors = RoverSensors(
        time=0.2,
        imu_accel=[0.2, 0.0, 0.0],
        imu_gyro=[0.0, 0.0, 0.02],
        wheel_encoders_rad_s=[2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        lidar_points_count=36,
        lidar_obstacle_ranges=[5.0] * 36,
        camera_traversability_grid_received=True,
        battery_soc_telemetry=0.85,
        battery_current_a=4.5,
        battery_voltage_v=28.0,
        sensors_healthy=True,
        dropout_active=False
    )
    ekf.update(sensors=sensors, ground_truth_beacon=np.array([10.1, 10.0]))
    
    # Verify symmetry and positive semi-definiteness
    assert np.allclose(ekf.P, ekf.P.T, atol=1e-5)
    eigvals = np.linalg.eigvals(ekf.P)
    assert np.all(eigvals >= -1e-6)
