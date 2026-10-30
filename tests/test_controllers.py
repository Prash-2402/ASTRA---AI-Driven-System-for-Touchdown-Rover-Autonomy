"""Unit tests for classical, optimal, and learned controllers in ASTRA."""
import pytest
import numpy as np
from autonomy.control.pid_touchdown import CascadePIDTouchdownController
from autonomy.control.mpc_touchdown import ModelPredictiveTouchdownController
from autonomy.control.pure_pursuit import PurePursuitController
from machine_learning.environments.touchdown_env import LanderEDLEnv

def test_touchdown_cascade_pid():
    pid = CascadePIDTouchdownController(dt=0.02, lander_mass=1100.0, gravity=3.71, max_thrust=5500.0)
    
    pos = np.array([0.0, 0.0, 1050.0])
    vel = np.array([0.0, 0.0, -10.0])
    euler = np.array([0.0, 0.0, 0.0])
    omega = np.array([0.0, 0.0, 0.0])
    target = np.array([0.0, 0.0, 0.0])
    
    throttle, rcs_torque = pid.compute_control(
        current_pos=pos, current_vel=vel, current_euler=euler,
        current_omega=omega, target_site=target, current_mass=1100.0
    )
    
    assert 0.15 <= throttle <= 1.0, f"Throttle must be bounded in [0.15, 1.0], got {throttle}"
    assert len(rcs_torque) == 3, "RCS torque command must be 3-axis"

def test_touchdown_mpc():
    mpc = ModelPredictiveTouchdownController(dt_control=0.1, horizon_steps=8, gravity=3.71, max_thrust=5500.0)
    
    pos = np.array([10.0, -5.0, 500.0])
    vel = np.array([1.0, -0.5, -15.0])
    euler = np.array([0.02, -0.01, 0.0])
    omega = np.array([0.0, 0.0, 0.0])
    target = np.array([0.0, 0.0, 0.0])
    
    throttle, rcs_torque, predicted_traj = mpc.compute_control(
        current_pos=pos, current_vel=vel, current_euler=euler,
        current_omega=omega, target_site=target, current_mass=1100.0
    )
    
    assert 0.15 <= throttle <= 1.0
    assert len(rcs_torque) == 3
    assert len(predicted_traj) == 8
    # Trajectory should descend in altitude
    assert predicted_traj[-1][2] < pos[2]

def test_touchdown_rl_gym_environment():
    env = LanderEDLEnv()
    obs, info = env.reset(seed=42)
    
    assert obs.shape == (13,), f"Observation dimension mismatch: {obs.shape}"
    assert "fuel_kg" in info
    
    # Step with valid control action
    action = np.array([0.5, 0.0, 0.0, 0.0], dtype=np.float32)
    next_obs, reward, terminated, truncated, step_info = env.step(action)
    
    assert next_obs.shape == (13,)
    assert isinstance(reward, (float, np.floating))
    assert isinstance(terminated, bool)

def test_rover_pure_pursuit():
    controller = PurePursuitController(lookahead_distance=2.5, max_speed=0.6)
    
    path = [[0.0, 0.0], [2.0, 2.0], [4.0, 4.0], [6.0, 6.0], [10.0, 10.0]]
    current_pos = np.array([0.0, 0.0, 0.0])
    current_heading = 0.0
    
    speed, yaw_rate, reached = controller.compute_motion_command(
        current_pos=current_pos,
        current_heading=current_heading,
        planned_path=path,
        speed_limit_factor=1.0
    )
    
    assert speed > 0.0, "Speed should be positive to advance along path"
    assert yaw_rate > 0.0, "Yaw rate command should be positive to turn towards y > 0"
    assert not reached
