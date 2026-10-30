from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from shared.enums.simulation import RoverMissionPhase, RoverControllerType, RoverFaultType, TerrainVariant, AnomalySeverity

class RoverPhysicalConfig(BaseModel):
    total_mass: float = Field(default=185.0, description="Rover total mass in kg")
    chassis_length: float = Field(default=1.5, description="Chassis length in meters")
    chassis_width: float = Field(default=1.2, description="Chassis width in meters")
    chassis_height: float = Field(default=0.6, description="Chassis height in meters")
    wheel_radius: float = Field(default=0.25, description="Wheel radius in meters")
    wheel_width: float = Field(default=0.20, description="Wheel width in meters")
    wheel_mass: float = Field(default=6.5, description="Individual wheel mass in kg")
    max_wheel_torque: float = Field(default=110.0, description="Max individual wheel drive torque in Nm")
    max_linear_speed: float = Field(default=0.85, description="Max speed in m/s")
    motor_nominal_efficiency: float = Field(default=0.88, description="Electrical-to-mechanical efficiency")
    battery_capacity_wh: float = Field(default=1200.0, description="Total battery capacity in Watt-hours")
    battery_nominal_voltage: float = Field(default=28.0, description="Nominal bus voltage in Volts")
    avionics_base_power_w: float = Field(default=45.0, description="Baseline computing & sensor power in Watts")

class RoverMissionConfig(BaseModel):
    terrain_variant: TerrainVariant = Field(default=TerrainVariant.DEV_MIXED_FLAT_UNEVEN)
    controller_type: RoverControllerType = Field(default=RoverControllerType.ASTRA_ADAPTIVE)
    start_position: List[float] = Field(default=[5.0, 5.0, 0.0], description="Start [x, y, z]")
    science_target: List[float] = Field(default=[85.0, 80.0, 0.0], description="Target [x, y, z]")
    dt: float = Field(default=0.02, description="Simulation dt in seconds")
    telemetry_rate_hz: float = Field(default=20.0)
    random_seed: int = Field(default=42)
    max_duration_seconds: float = Field(default=300.0)
    battery_safety_reserve_fraction: float = Field(default=0.15, description="Hard reserve fraction below which halt triggers")

class RoverFaultSchedule(BaseModel):
    fault_type: RoverFaultType = Field(default=RoverFaultType.NONE)
    trigger_time_s: float = Field(default=25.0)
    duration_s: float = Field(default=30.0)
    intensity: float = Field(default=1.0, description="Severity / ratio (e.g. 0.15 for misclassification)")
    target_component: Optional[str] = Field(default=None, description="e.g. 'wheel_front_left' or 'lidar'")

class RoverWheelState(BaseModel):
    wheel_id: str
    angular_velocity_rad_s: float
    drive_torque_nm: float
    contact_force_n: float
    longitudinal_slip: float
    effective_friction: float
    motor_temperature_c: float
    health_ratio: float = 1.0

class RoverTrueState(BaseModel):
    time: float
    position: List[float]         # [x, y, z]
    velocity: List[float]         # [vx, vy, vz]
    linear_speed: float
    quaternion: List[float]       # [w, x, y, z]
    euler: List[float]            # [roll, pitch, yaw]
    angular_velocity: List[float] # [wx, wy, wz]
    rocker_left_angle: float
    rocker_right_angle: float
    bogie_left_angle: float
    bogie_right_angle: float
    wheels: List[RoverWheelState]
    battery_soc: float            # 0.0 to 1.0
    battery_energy_remaining_wh: float
    battery_voltage: float
    power_draw_w: float
    cumulative_energy_wh: float
    distance_traveled_m: float

class RoverSensors(BaseModel):
    time: float
    imu_accel: List[float]
    imu_gyro: List[float]
    wheel_encoders_rad_s: List[float] # 6 wheel speeds
    lidar_points_count: int
    lidar_obstacle_ranges: List[float]
    camera_traversability_grid_received: bool
    battery_soc_telemetry: float
    battery_current_a: float
    battery_voltage_v: float
    sensors_healthy: bool
    dropout_active: bool

class RoverEKFState(BaseModel):
    time: float
    position: List[float]         # [x, y, z]
    linear_velocity: List[float]  # [vx, vy, vz]
    heading_rad: float
    pitch_rad: float
    roll_rad: float
    position_error: List[float]
    heading_error: float
    covariance_diag: List[float]  # [var_x, var_y, var_z, var_vx, var_vy, var_vz, var_heading]
    position_uncertainty_3sigma: float
    heading_uncertainty_3sigma: float
    innovation_norm: float

class RoverAnomalyDetectionState(BaseModel):
    anomaly_detected: bool
    severity: AnomalySeverity
    evidence_source: str
    classified_fault: RoverFaultType
    classification_confidence: float
    innovation_residual_sigma: float
    motion_residual_m: float
    recommended_action: str

class RoverPathWaypoint(BaseModel):
    x: float
    y: float
    traversability_cost: float
    slope_degrees: float

class RoverTelemetryFrame(BaseModel):
    timestamp: float
    step: int
    phase: RoverMissionPhase
    controller_type: RoverControllerType
    true_state: RoverTrueState
    sensor_state: RoverSensors
    ekf_state: RoverEKFState
    anomaly_state: RoverAnomalyDetectionState
    active_faults: List[RoverFaultType]
    planned_path: List[List[float]]   # [[x, y], ...]
    executed_path: List[List[float]]  # [[x, y], ...]
    distance_to_target: float
    safety_violations_count: int
    current_action: str
    events: List[str] = []
    success: Optional[bool] = None
    failure_reason: Optional[str] = None
