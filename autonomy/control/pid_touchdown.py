import numpy as np
from typing import Tuple, Dict, Any

class CascadePIDTouchdownController:
    """
    Cascade Proportional-Integral-Derivative Controller for Lander Descent & Touchdown:
    1. Vertical Channel:
       - Outer Loop: Altitude error -> desired vertical velocity v_z_des
       - Inner Loop: Velocity error -> throttle command u_thrust with anti-windup
    2. Horizontal Channels (X and Y):
       - Outer Loop: Position error -> desired horizontal velocity v_des
       - Inner Loop: Horizontal velocity error -> desired attitude tilt (pitch / roll)
    3. Attitude Channel (Roll, Pitch, Yaw):
       - Outer Loop: Euler angle error -> desired angular rates omega_des
       - Inner Loop: Angular rate error -> RCS torque commands [tau_x, tau_y, tau_z]
    """
    def __init__(self, dt: float = 0.02, lander_mass: float = 1100.0, gravity: float = 3.71, max_thrust: float = 5500.0):
        self.dt = dt
        self.mass = lander_mass
        self.g = gravity
        self.max_thrust = max_thrust

        # Vertical gains
        self.kp_z = 0.25
        self.kp_vz = 0.40
        self.ki_vz = 0.05
        self.kd_vz = 0.08
        self.int_vz = 0.0

        # Horizontal gains
        self.kp_xy = 0.12
        self.kp_vxy = 0.18
        self.max_tilt_rad = np.radians(20.0) # max 20 degrees tilt

        # Attitude gains
        self.kp_att = 800.0
        self.kd_att = 450.0

        self.last_vz_error = 0.0

    def compute_control(
        self,
        current_pos: np.ndarray,
        current_vel: np.ndarray,
        current_euler: np.ndarray,
        current_omega: np.ndarray,
        target_site: np.ndarray,
        current_mass: float
    ) -> Tuple[float, np.ndarray]:
        """
        Computes (throttle_command, rcs_torque_cmd)
        """
        # 1. Target touchdown profile
        # Terminal descent speed target depends on altitude
        altitude = current_pos[2] - target_site[2]

        if altitude > 500.0:
            vz_des = -25.0
        elif altitude > 100.0:
            vz_des = -12.0
        elif altitude > 20.0:
            vz_des = -4.0
        elif altitude > 2.0:
            vz_des = -1.5 # terminal soft descent
        else:
            vz_des = -0.6 # gentle touchdown

        # Vertical velocity error
        err_vz = vz_des - current_vel[2]
        self.int_vz += err_vz * self.dt
        # Anti-windup clamping
        self.int_vz = np.clip(self.int_vz, -5.0, 5.0)
        d_err_vz = (err_vz - self.last_vz_error) / self.dt
        self.last_vz_error = err_vz

        # Hover thrust requirement: F_hover = mass * g
        f_hover = current_mass * self.g
        f_demand = f_hover + current_mass * (self.kp_vz * err_vz + self.ki_vz * self.int_vz + self.kd_vz * d_err_vz)

        # Account for body tilt: F_thrust_z = F_total * cos(tilt)
        tilt = np.linalg.norm(current_euler[0:2])
        cos_tilt = max(0.5, np.cos(tilt))
        f_thrust_cmd = f_demand / cos_tilt

        throttle_cmd = float(np.clip(f_thrust_cmd / self.max_thrust, 0.15, 1.0))

        # 2. Horizontal Guidance -> Desired Pitch (theta) and Roll (phi)
        err_pos_xy = target_site[0:2] - current_pos[0:2]
        v_des_xy = np.clip(self.kp_xy * err_pos_xy, -15.0, 15.0)

        err_vxy = v_des_xy - current_vel[0:2]

        # Pitch controls X acceleration (negative pitch accelerates +X)
        # Roll controls Y acceleration (positive roll accelerates +Y)
        theta_des = float(np.clip(-self.kp_vxy * err_vxy[0], -self.max_tilt_rad, self.max_tilt_rad))
        phi_des = float(np.clip(self.kp_vxy * err_vxy[1], -self.max_tilt_rad, self.max_tilt_rad))
        psi_des = 0.0 # Maintain nominal heading

        # Near ground (< 15m), force upright attitude for safe touchdown
        if altitude < 15.0:
            theta_des *= max(0.0, altitude / 15.0)
            phi_des *= max(0.0, altitude / 15.0)

        desired_euler = np.array([phi_des, theta_des, psi_des])

        # 3. Attitude Loop -> RCS Torques
        err_att = desired_euler - current_euler
        # Normalize angle errors to [-pi, pi]
        err_att = (err_att + np.pi) % (2.0 * np.pi) - np.pi

        rcs_torques = self.kp_att * err_att - self.kd_att * current_omega
        rcs_torques = np.clip(rcs_torques, -120.0, 120.0)

        return throttle_cmd, rcs_torques
