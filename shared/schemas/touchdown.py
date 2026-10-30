from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from shared.enums.simulation import TouchdownPhase, TouchdownControllerType

class TouchdownEnvironmentConfig(BaseModel):
    gravity: float = Field(default=3.71, description="Mars surface gravity in m/s^2")
    planetary_radius: float = Field(default=3389500.0, description="Mars radius in meters")
    atmospheric_density_surface: float = Field(default=0.020, description="Surface atmospheric density kg/m^3")
    scale_height: float = Field(default=11100.0, description="Mars atmospheric scale height in meters")
    wind_velocity: List[float] = Field(default=[2.5, -1.0, 0.0], description="Steady wind vector [Vx, Vy, Vz] in m/s")
    wind_gust_std: float = Field(default=1.2, description="Wind gust standard deviation in m/s")
    terrain_seed: int = Field(default=42, description="Seed for deterministic fractal terrain")

class LanderPhysicalConfig(BaseModel):
    dry_mass: float = Field(default=650.0, description="Dry mass of lander in kg")
    fuel_mass: float = Field(default=450.0, description="Initial fuel mass in kg")
    max_thrust: float = Field(default=5500.0, description="Maximum main engine thrust in Newtons")
    min_throttle: float = Field(default=0.15, description="Minimum engine throttle fraction")
    max_throttle: float = Field(default=1.0, description="Maximum engine throttle fraction")
    isp: float = Field(default=285.0, description="Specific impulse of main engine in seconds")
    rcs_thrust: float = Field(default=120.0, description="RCS thruster force in Newtons")
    rcs_isp: float = Field(default=210.0, description="RCS specific impulse in seconds")
    inertia_tensor_diag: List[float] = Field(default=[480.0, 480.0, 320.0], description="Diagonal inertia [Ixx, Iyy, Izz] kg*m^2")
    drag_coefficient: float = Field(default=1.2, description="Aerodynamic drag coefficient")
    cross_section_area: float = Field(default=4.5, description="Effective drag area in m^2")

class TouchdownInitialConditions(BaseModel):
    position: List[float] = Field(default=[150.0, -80.0, 2200.0], description="Initial [x, y, z] in meters (z = altitude)")
    velocity: List[float] = Field(default=[-12.0, 6.0, -48.0], description="Initial [vx, vy, vz] in m/s")
    attitude_euler: List[float] = Field(default=[0.05, -0.04, 0.0], description="Initial [roll, pitch, yaw] in radians")
    angular_velocity: List[float] = Field(default=[0.01, -0.02, 0.0], description="Initial [wx, wy, wz] in rad/s")
    target_site: List[float] = Field(default=[0.0, 0.0, 0.0], description="Primary landing target [x, y, z]")

class TouchdownConfig(BaseModel):
    env: TouchdownEnvironmentConfig = Field(default_factory=TouchdownEnvironmentConfig)
    lander: LanderPhysicalConfig = Field(default_factory=LanderPhysicalConfig)
    initial: TouchdownInitialConditions = Field(default_factory=TouchdownInitialConditions)
    controller_type: TouchdownControllerType = Field(default=TouchdownControllerType.MPC)
    dt: float = Field(default=0.02, description="Physics integration timestep in seconds (50 Hz)")
    sensor_rate_hz: float = Field(default=25.0, description="Sensor sampling rate in Hz")
    control_rate_hz: float = Field(default=10.0, description="Controller execution rate in Hz")
    random_seed: int = Field(default=42)

class Vector3D(BaseModel):
    x: float
    y: float
    z: float

class Quaternion(BaseModel):
    w: float
    x: float
    y: float
    z: float

class LanderState(BaseModel):
    time: float
    position: List[float]       # [x, y, z]
    velocity: List[float]       # [vx, vy, vz]
    quaternion: List[float]     # [w, x, y, z]
    euler: List[float]          # [roll, pitch, yaw] in rad
    angular_velocity: List[float] # [wx, wy, wz] in rad/s
    acceleration: List[float]   # [ax, ay, az] in m/s^2
    total_mass: float
    fuel_mass: float
    fuel_fraction: float
    altitude: float
    vertical_speed: float
    horizontal_speed: float

class LanderSensors(BaseModel):
    time: float
    altimeter: float
    imu_accel: List[float]
    imu_gyro: List[float]
    velocity_measured: List[float]
    position_radar: List[float]
    radar_terrain_range: float
    fuel_sensor: float
    valid: bool = True

class EKFStateEstimate(BaseModel):
    time: float
    estimated_position: List[float]
    estimated_velocity: List[float]
    estimated_euler: List[float]
    position_error: List[float]
    velocity_error: List[float]
    euler_error: List[float]
    covariance_diag: List[float] # Variance of states [px, py, pz, vx, vy, vz, roll, pitch, yaw]
    position_uncertainty_3sigma: float
    velocity_uncertainty_3sigma: float

class LandingSiteCandidate(BaseModel):
    id: str
    position: List[float]
    slope_degrees: float
    roughness: float
    hazard_score: float
    reachable: bool
    required_fuel_kg: float
    feasibility_score: float

class TouchdownTelemetryFrame(BaseModel):
    timestamp: float
    step: int
    phase: TouchdownPhase
    true_state: LanderState
    sensor_state: LanderSensors
    ekf_estimate: EKFStateEstimate
    throttle_command: float
    thrust_vector: List[float]
    rcs_torque: List[float]
    landing_target: List[float]
    predicted_touchdown_point: List[float]
    active_hazard_detected: bool
    diversion_active: bool
    candidate_sites: List[LandingSiteCandidate] = []
    events: List[str] = []
    success: Optional[bool] = None
    failure_reason: Optional[str] = None
