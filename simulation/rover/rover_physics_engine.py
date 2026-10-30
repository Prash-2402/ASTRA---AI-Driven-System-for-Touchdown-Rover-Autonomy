import numpy as np
from typing import List, Dict, Any, Tuple
from shared.schemas.rover import RoverPhysicalConfig, RoverWheelState
from simulation.rover.terrain_generator import TerrainMap

class RoverDynamicPhysicsEngine:
    """
    First-Principles Multi-Body Physics Engine for Rocker-Bogie 6-Wheel Planetary Rover:
    - 6 independently actuated wheels with individual motor torque and wheel inertia.
    - Rocker-bogie suspension kinematics:
      Differential pivot links left & right rockers such that theta_rocker_L + theta_rocker_R = 2 * theta_chassis.
      Front & middle wheels mounted on articulated bogies.
    - Non-linear wheel-ground contact mechanics:
      Normal forces F_N,i calculated from vehicle mass, local terrain normal, and suspension equilibrium.
      Slip ratio s_i = (omega_i * R - v_i) / max(|omega_i * R|, |v_i|)
      Tractive force F_x,i modeled via Pacejka-Coulomb friction: F_x,i = mu * F_N,i * tanh(6.0 * s_i)
      Rolling resistance F_rr,i = C_rr * F_N,i
    - Skid-steering yaw dynamics from differential wheel velocities.
    - Electrochemical battery model tracking voltage sag, current draw, and State of Charge (SoC).
    """
    def __init__(self, config: RoverPhysicalConfig, terrain: TerrainMap, start_pos: List[float], random_seed: int = 42):
        self.config = config
        self.terrain = terrain
        self.rng = np.random.RandomState(random_seed)

        # Vehicle physical properties
        self.mass = config.total_mass
        self.g = 3.71 # Mars gravity
        self.R = config.wheel_radius
        self.I_wheel = config.wheel_mass * (config.wheel_radius**2) * 0.5
        self.I_yaw = config.total_mass * ((config.chassis_length**2 + config.chassis_width**2) / 12.0)
        self.C_rr = 0.035 # Rolling resistance coefficient on regolith
        self.mu_base = 0.72 # Friction coefficient on Mars soil

        # 6 Wheels geometry offsets from chassis CoG [x_offset, y_offset]
        self.wheel_names = [
            "wheel_front_left", "wheel_mid_left", "wheel_rear_left",
            "wheel_front_right", "wheel_mid_right", "wheel_rear_right"
        ]
        self.wheel_offsets = {
            "wheel_front_left":  np.array([ 0.72,  0.60]),
            "wheel_mid_left":    np.array([ 0.08,  0.60]),
            "wheel_rear_left":   np.array([-0.65,  0.60]),
            "wheel_front_right": np.array([ 0.72, -0.60]),
            "wheel_mid_right":   np.array([ 0.08, -0.60]),
            "wheel_rear_right":  np.array([-0.65, -0.60])
        }

        # Dynamic state: [x, y, z, vx, vy, vz, heading, omega_z]
        z_start = terrain.get_elevation(start_pos[0], start_pos[1]) + self.R
        self.pos = np.array([start_pos[0], start_pos[1], z_start], dtype=np.float64)
        self.vel = np.zeros(3, dtype=np.float64) # in world frame
        self.heading = 0.0 # radians
        self.omega_z = 0.0 # rad/s
        self.pitch = 0.0
        self.roll = 0.0

        # Rocker-bogie joint angles
        self.rocker_left = 0.0
        self.rocker_right = 0.0
        self.bogie_left = 0.0
        self.bogie_right = 0.0

        # Wheel angular velocities [rad/s]
        self.wheel_omegas = {w: 0.0 for w in self.wheel_names}
        # Wheel health multiplier [0.0 to 1.0] (Fault 04 degradation)
        self.wheel_health = {w: 1.0 for w in self.wheel_names}

        # Battery and power state
        self.battery_capacity_wh = config.battery_capacity_wh
        self.battery_energy_wh = config.battery_capacity_wh
        self.battery_voltage = config.battery_nominal_voltage
        self.power_draw_w = config.avionics_base_power_w
        self.cumulative_energy_wh = 0.0
        self.distance_traveled = 0.0

        # Fault injection state
        self.fault_power_multiplier = 1.0 # Fault 03 power spike

        # Simulation step memory
        self.time = 0.0
        self.last_wheel_states: List[RoverWheelState] = []

    @property
    def battery_soc(self) -> float:
        return float(self.battery_energy_wh / max(1.0, self.battery_capacity_wh))

    def set_wheel_health(self, wheel_id: str, health: float):
        """Used by FAULT 04 (Actuator degradation) to reduce effective motor torque."""
        if wheel_id in self.wheel_health:
            self.wheel_health[wheel_id] = float(np.clip(health, 0.0, 1.0))

    def set_power_spike(self, multiplier: float):
        """Used by FAULT 03 (Power drain spike) to increase electrical power consumption."""
        self.fault_power_multiplier = float(multiplier)

    def step(self, commanded_speed: float, commanded_yaw_rate: float, dt: float) -> Tuple[np.ndarray, List[RoverWheelState]]:
        """
        Executes one authoritative physical integration step driven by actual wheel torques.
        """
        self.time += dt

        # 1. Kinematics of differential steering: compute target wheel speeds
        # v_left = v - (omega * width / 2), v_right = v + (omega * width / 2)
        track_width = self.config.chassis_width
        v_target_left = commanded_speed - (commanded_yaw_rate * track_width * 0.5)
        v_target_right = commanded_speed + (commanded_yaw_rate * track_width * 0.5)

        # 2. Local terrain surface normal and suspension articulation
        chassis_norm, slope_deg = self.terrain.get_surface_normal_and_slope(self.pos[0], self.pos[1])
        # Approximate chassis pitch and roll from terrain normal
        self.pitch = float(np.arctan2(-chassis_norm[0], chassis_norm[2]))
        self.roll = float(np.arctan2(chassis_norm[1], chassis_norm[2]))

        # Calculate wheel ground elevations and articulate rocker-bogie
        wheel_elevations = {}
        for w_name, offset in self.wheel_offsets.items():
            # World position of wheel
            c_h, s_h = np.cos(self.heading), np.sin(self.heading)
            w_x = self.pos[0] + offset[0] * c_h - offset[1] * s_h
            w_y = self.pos[1] + offset[0] * s_h + offset[1] * c_h
            wheel_elevations[w_name] = self.terrain.get_elevation(w_x, w_y)

        # Rocker angles adapt to front-vs-rear elevation gradient
        delta_z_left = wheel_elevations["wheel_front_left"] - wheel_elevations["wheel_rear_left"]
        delta_z_right = wheel_elevations["wheel_front_right"] - wheel_elevations["wheel_rear_right"]
        self.rocker_left = float(np.arctan2(delta_z_left, 1.35))
        self.rocker_right = float(np.arctan2(delta_z_right, 1.35))
        self.bogie_left = float(np.arctan2(wheel_elevations["wheel_front_left"] - wheel_elevations["wheel_mid_left"], 0.64))
        self.bogie_right = float(np.arctan2(wheel_elevations["wheel_front_right"] - wheel_elevations["wheel_mid_right"], 0.64))

        # 3. Wheel dynamics and contact forces
        # Normal force per wheel roughly equals m*g/6 with slope load transfer
        f_norm_base = (self.mass * self.g / 6.0) * max(0.2, np.cos(np.radians(slope_deg)))
        # Pitch slope load transfer (weight shifts to rear wheels when climbing slope)
        slope_rad = np.radians(slope_deg)
        f_norm_pitch_shift = (self.mass * self.g * np.sin(self.pitch) * 0.3) / 2.0

        current_fwd_speed = float(np.cos(self.heading) * self.vel[0] + np.sin(self.heading) * self.vel[1])
        total_longitudinal_force = 0.0
        total_yaw_torque = 0.0
        total_motor_power = 0.0
        wheel_states = []

        for w_name in self.wheel_names:
            is_left = "left" in w_name
            is_rear = "rear" in w_name
            is_front = "front" in w_name

            v_des = v_target_left if is_left else v_target_right
            omega_des = v_des / self.R

            # Normal force calculation with load transfer
            fn = f_norm_base
            if is_rear:
                fn += f_norm_pitch_shift
            elif is_front:
                fn -= f_norm_pitch_shift
            fn = max(10.0, fn)

            # Motor drive torque controller (proportional-integral speed control)
            omega_err = omega_des - self.wheel_omegas[w_name]
            kp_motor = 45.0
            tau_demand = kp_motor * omega_err
            # Clamp to max motor torque scaled by health (Fault 04)
            health = self.wheel_health[w_name]
            tau_max = self.config.max_wheel_torque * health
            tau_actual = float(np.clip(tau_demand, -tau_max, tau_max))

            # Wheel acceleration: I * d_omega = tau - F_tract * R
            # Wheel longitudinal velocity
            v_wheel_linear = current_fwd_speed + (-self.omega_z * self.wheel_offsets[w_name][1])
            omega_wheel = self.wheel_omegas[w_name]
            v_tread = omega_wheel * self.R

            # Slip ratio: s = (v_tread - v_wheel) / max(|v_tread|, |v_wheel|, 0.01)
            denominator = max(abs(v_tread), abs(v_wheel_linear), 0.05)
            slip = float(np.clip((v_tread - v_wheel_linear) / denominator, -1.0, 1.0))

            # Tractive contact force via Pacejka-Coulomb non-linear curve
            f_tractive = float(self.mu_base * fn * np.tanh(5.5 * slip))
            f_rr = float(self.C_rr * fn * np.sign(v_wheel_linear + 1e-4))

            # Net force on wheel
            f_net_wheel = f_tractive - f_rr

            # Wheel rotational acceleration
            d_omega = (tau_actual - f_tractive * self.R) / self.I_wheel
            self.wheel_omegas[w_name] += d_omega * dt

            # Accumulate vehicle forces
            total_longitudinal_force += f_net_wheel
            # Yaw torque: arm = y_offset
            arm_y = self.wheel_offsets[w_name][1]
            total_yaw_torque += f_net_wheel * (-arm_y)

            # Electrical power: P = tau * omega / efficiency
            eff = self.config.motor_nominal_efficiency
            p_motor = abs(tau_actual * self.wheel_omegas[w_name]) / max(0.1, eff)
            total_motor_power += p_motor

            wheel_states.append(RoverWheelState(
                wheel_id=w_name,
                angular_velocity_rad_s=float(self.wheel_omegas[w_name]),
                drive_torque_nm=float(tau_actual),
                contact_force_n=float(fn),
                longitudinal_slip=float(slip),
                effective_friction=float(self.mu_base),
                motor_temperature_c=25.0 + 0.05 * abs(tau_actual),
                health_ratio=float(health)
            ))

        self.last_wheel_states = wheel_states

        # 4. Integrate Chassis Accelerations and Velocities
        # Slope resistance force: m * g * sin(slope)
        f_slope_res = self.mass * self.g * np.sin(self.pitch)
        f_total_forward = total_longitudinal_force - f_slope_res

        # Forward acceleration in body frame
        a_forward = f_total_forward / self.mass
        v_forward = current_fwd_speed + a_forward * dt
        v_forward = np.clip(v_forward, -self.config.max_linear_speed, self.config.max_linear_speed)

        # Yaw acceleration: I_yaw * d_omega_z = total_yaw_torque
        # Rotational drag damping
        damping_yaw = 80.0 * self.omega_z
        d_omega_z = (total_yaw_torque - damping_yaw) / self.I_yaw
        self.omega_z += d_omega_z * dt
        self.heading += self.omega_z * dt
        # Normalize heading to [-pi, pi]
        self.heading = (self.heading + np.pi) % (2.0 * np.pi) - np.pi

        # Update world velocity vector
        self.vel[0] = v_forward * np.cos(self.heading)
        self.vel[1] = v_forward * np.sin(self.heading)

        # World position update
        delta_p = self.vel[0:2] * dt
        self.pos[0] += delta_p[0]
        self.pos[1] += delta_p[1]
        self.pos[2] = self.terrain.get_elevation(self.pos[0], self.pos[1]) + self.R
        step_dist = float(np.linalg.norm(delta_p))
        self.distance_traveled += step_dist

        # 5. Energy and Battery Depletion Model
        # Electrical power with fault spike multiplier (Fault 03)
        base_power = self.config.avionics_base_power_w
        total_power = (base_power + total_motor_power) * self.fault_power_multiplier
        self.power_draw_w = float(total_power)

        # Energy consumed in Watt-hours: P * (dt / 3600)
        delta_wh = total_power * (dt / 3600.0)
        self.battery_energy_wh = max(0.0, self.battery_energy_wh - delta_wh)
        self.cumulative_energy_wh += delta_wh

        # Battery Voltage sag: V = V_nom * (0.85 + 0.15 * SoC) - I * R_int
        soc = self.battery_energy_wh / self.battery_capacity_wh
        current_amps = total_power / max(15.0, self.battery_voltage)
        r_internal = 0.08 # Ohms
        self.battery_voltage = self.config.battery_nominal_voltage * (0.85 + 0.15 * soc) - (current_amps * r_internal)

        return self.pos, wheel_states
