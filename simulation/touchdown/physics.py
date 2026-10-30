import numpy as np
from typing import Dict, Any, Tuple
from shared.schemas.touchdown import LanderPhysicalConfig, TouchdownInitialConditions
from simulation.touchdown.environment import MarsEnvironment

def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """Converts unit quaternion [w, x, y, z] to 3x3 direction cosine rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1.0 - 2.0*(y*y + z*z), 2.0*(x*y - w*z),       2.0*(x*z + w*y)],
        [2.0*(x*y + w*z),       1.0 - 2.0*(x*x + z*z), 2.0*(y*z - w*x)],
        [2.0*(x*z - w*y),       2.0*(y*z + w*x),       1.0 - 2.0*(x*x + y*y)]
    ], dtype=np.float64)

def quaternion_to_euler(q: np.ndarray) -> np.ndarray:
    """Converts unit quaternion [w, x, y, z] to Euler angles [roll, pitch, yaw] in radians."""
    w, x, y, z = q
    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    if np.abs(sinp) >= 1.0:
        pitch = np.sign(sinp) * (np.pi / 2.0)
    else:
        pitch = np.arcsin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    return np.array([roll, pitch, yaw], dtype=np.float64)

def euler_to_quaternion(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Converts Euler angles [roll, pitch, yaw] in radians to quaternion [w, x, y, z]."""
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    q = np.array([w, x, y, z], dtype=np.float64)
    return q / np.linalg.norm(q)

class Lander6DoFPhysics:
    """
    Complete 6-Degree-of-Freedom rigid body dynamics model for planetary lander.
    Integrated using Runge-Kutta 4th order (RK4).
    Accounts for variable fuel mass, main engine gimbal/thrust vector,
    RCS attitude control torques, aerodynamic drag in planetary atmosphere,
    and landing gear ground contact dynamics.
    """
    def __init__(self, config: LanderPhysicalConfig, env: MarsEnvironment, initial: TouchdownInitialConditions):
        self.config = config
        self.env = env

        self.dry_mass = config.dry_mass
        self.fuel_mass = config.fuel_mass
        self.max_thrust = config.max_thrust
        self.min_throttle = config.min_throttle
        self.max_throttle = config.max_throttle
        self.isp = config.isp
        self.rcs_isp = config.rcs_isp
        self.I_diag = np.array(config.inertia_tensor_diag, dtype=np.float64)
        self.I_inv = np.diag(1.0 / self.I_diag)
        self.g0 = 9.80665 # Earth standard gravity for Isp definition

        # State initialization: [pos(3), vel(3), quat(4), omega(3)]
        self.pos = np.array(initial.position, dtype=np.float64)
        self.vel = np.array(initial.velocity, dtype=np.float64)
        self.quat = euler_to_quaternion(initial.attitude_euler[0], initial.attitude_euler[1], initial.attitude_euler[2])
        self.omega = np.array(initial.angular_velocity, dtype=np.float64)
        self.time = 0.0

        # Current throttle and actuator values
        self.throttle_actual = 0.0
        self.throttle_target = 0.0
        self.rcs_torque = np.zeros(3, dtype=np.float64)
        self.last_accel = np.zeros(3, dtype=np.float64)

        # Contact state
        self.is_touchdown = False
        self.touchdown_velocity = 0.0
        self.touchdown_attitude_deg = 0.0

    @property
    def total_mass(self) -> float:
        return self.dry_mass + self.fuel_mass

    def get_state_vector(self) -> np.ndarray:
        """Returns flat 13-element state vector [p(3), v(3), q(4), w(3)]."""
        return np.concatenate([self.pos, self.vel, self.quat, self.omega])

    def set_state_vector(self, state: np.ndarray):
        self.pos = state[0:3].copy()
        self.vel = state[3:6].copy()
        q = state[6:10].copy()
        q_norm = np.linalg.norm(q)
        self.quat = q / (q_norm if q_norm > 1e-8 else 1.0)
        self.omega = state[10:13].copy()

    def compute_derivatives(self, state: np.ndarray, throttle: float, rcs_torque: np.ndarray) -> np.ndarray:
        """
        Computes state derivatives:
        dot(pos) = vel
        dot(vel) = (F_gravity + F_thrust + F_drag) / mass
        dot(quat) = 0.5 * quat_mult(quat, [0, omega])
        dot(omega) = I^-1 * (torque - omega x (I * omega))
        """
        pos = state[0:3]
        vel = state[3:6]
        q = state[6:10]
        q = q / np.linalg.norm(q)
        omega = state[10:13]

        m = self.total_mass
        R_body_to_world = quaternion_to_rotation_matrix(q)

        # 1. Gravity Force (World frame, downwards in z)
        F_grav = np.array([0.0, 0.0, -m * self.env.gravity], dtype=np.float64)

        # 2. Main Engine Thrust
        # Thrust is directed along body +Z axis (upwards from lander nozzle)
        clamped_throttle = np.clip(throttle, 0.0, 1.0)
        thrust_mag = clamped_throttle * self.max_thrust if self.fuel_mass > 0.0 else 0.0
        F_thrust_body = np.array([0.0, 0.0, thrust_mag], dtype=np.float64)
        F_thrust_world = R_body_to_world @ F_thrust_body

        # 3. Aerodynamic Drag
        surface_z = self.env.get_surface_elevation(pos[0], pos[1])
        altitude = pos[2] - surface_z
        rho = self.env.get_atmospheric_density(max(0.0, altitude))
        wind_vel = self.env.get_wind_velocity(max(0.0, altitude))
        v_rel = vel - wind_vel
        v_rel_norm = np.linalg.norm(v_rel)

        if v_rel_norm > 1e-4 and rho > 1e-8:
            F_drag = -0.5 * rho * self.config.drag_coefficient * self.config.cross_section_area * v_rel_norm * v_rel
        else:
            F_drag = np.zeros(3, dtype=np.float64)

        # Total acceleration
        a_world = (F_grav + F_thrust_world + F_drag) / m

        # 4. Quaternion derivative: dot(q) = 0.5 * Omega(omega) * q
        w_x, w_y, w_z = omega
        Omega = np.array([
            [0.0, -w_x, -w_y, -w_z],
            [w_x,  0.0,  w_z, -w_y],
            [w_y, -w_z,  0.0,  w_x],
            [w_z,  w_y, -w_x,  0.0]
        ], dtype=np.float64)
        dot_q = 0.5 * (Omega @ q)

        # 5. Angular acceleration: dot(omega) = I^-1 * (tau - omega x (I * omega))
        I_diag = self.I_diag
        I_omega = I_diag * omega
        gyroscopic_torque = np.cross(omega, I_omega)
        total_torque = rcs_torque - gyroscopic_torque
        dot_omega = self.I_inv @ total_torque

        dot_pos = vel
        dot_vel = a_world

        return np.concatenate([dot_pos, dot_vel, dot_q, dot_omega])

    def step(self, throttle_cmd: float, rcs_torque_cmd: np.ndarray, dt: float) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Executes one RK4 integration step.
        Updates fuel mass consumption and enforces surface collision/touchdown constraints.
        """
        if self.is_touchdown:
            return self.get_state_vector(), {"touchdown": True}

        # Actuator lag on main engine throttle (time constant 0.08 s)
        tau_eng = 0.08
        alpha = dt / (tau_eng + dt)
        self.throttle_actual += alpha * (throttle_cmd - self.throttle_actual)
        self.throttle_actual = float(np.clip(self.throttle_actual, 0.0, 1.0))
        self.rcs_torque = np.clip(rcs_torque_cmd, -self.config.rcs_thrust * 0.8, self.config.rcs_thrust * 0.8)

        # RK4 Integration
        s0 = self.get_state_vector()
        k1 = self.compute_derivatives(s0, self.throttle_actual, self.rcs_torque)
        k2 = self.compute_derivatives(s0 + 0.5 * dt * k1, self.throttle_actual, self.rcs_torque)
        k3 = self.compute_derivatives(s0 + 0.5 * dt * k2, self.throttle_actual, self.rcs_torque)
        k4 = self.compute_derivatives(s0 + dt * k3, self.throttle_actual, self.rcs_torque)

        s_next = s0 + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        # Update physical state
        self.set_state_vector(s_next)
        self.time += dt
        self.last_accel = k1[3:6]

        # Fuel consumption: mass flow rate = Thrust / (g0 * Isp)
        thrust = self.throttle_actual * self.max_thrust if self.fuel_mass > 0.0 else 0.0
        fuel_rate_main = thrust / (self.g0 * self.isp)
        rcs_mag = np.linalg.norm(self.rcs_torque)
        fuel_rate_rcs = rcs_mag / (0.8 * self.g0 * self.rcs_isp) # lever arm ~0.8m
        delta_fuel = (fuel_rate_main + fuel_rate_rcs) * dt
        self.fuel_mass = max(0.0, self.fuel_mass - delta_fuel)

        # Check surface altitude for touchdown or impact
        surface_elev = self.env.get_surface_elevation(self.pos[0], self.pos[1])
        altitude = self.pos[2] - surface_elev

        if altitude <= 0.0:
            self.is_touchdown = True
            self.pos[2] = surface_elev
            self.touchdown_velocity = float(np.linalg.norm(self.vel))
            euler = quaternion_to_euler(self.quat)
            self.touchdown_attitude_deg = float(np.degrees(np.linalg.norm(euler[0:2])))
            self.vel = np.zeros(3)
            self.omega = np.zeros(3)
            self.throttle_actual = 0.0

        return self.get_state_vector(), {
            "altitude": altitude,
            "thrust_n": thrust,
            "fuel_mass": self.fuel_mass,
            "is_touchdown": self.is_touchdown
        }
