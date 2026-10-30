import pytest
import numpy as np
from shared.schemas.touchdown import LanderPhysicalConfig, TouchdownEnvironmentConfig, TouchdownInitialConditions
from simulation.touchdown.environment import MarsEnvironment
from simulation.touchdown.physics import Lander6DoFPhysics, quaternion_to_euler

def test_mars_environment_barometric_density():
    env = MarsEnvironment(TouchdownEnvironmentConfig())
    rho_0 = env.get_atmospheric_density(0.0)
    rho_scale = env.get_atmospheric_density(11100.0)
    assert np.isclose(rho_0, 0.020, rtol=1e-3)
    # At scale height H, density is rho_0 * exp(-1)
    assert np.isclose(rho_scale, rho_0 * np.exp(-1.0), rtol=1e-3)

def test_lander_rk4_freefall_gravity():
    env = MarsEnvironment(TouchdownEnvironmentConfig())
    phys = Lander6DoFPhysics(
        LanderPhysicalConfig(),
        env,
        TouchdownInitialConditions(position=[0, 0, 1000], velocity=[0, 0, 0])
    )
    dt = 0.02
    initial_mass = phys.total_mass

    # Step without thrust
    for _ in range(50): # 1.0 second
        phys.step(throttle_cmd=0.0, rcs_torque_cmd=np.zeros(3), dt=dt)

    # After 1 sec in Mars gravity (g=3.71 m/s^2), vz should be approx -3.71 m/s (accounting for slight drag)
    assert phys.vel[2] < -3.5 and phys.vel[2] > -3.9
    # Altitude should have decreased
    assert phys.pos[2] < 1000.0
    # Mass should not decrease if throttle is 0
    assert np.isclose(phys.total_mass, initial_mass, rtol=1e-5)

def test_lander_thrust_and_fuel_consumption():
    env = MarsEnvironment(TouchdownEnvironmentConfig())
    phys = Lander6DoFPhysics(
        LanderPhysicalConfig(),
        env,
        TouchdownInitialConditions(position=[0, 0, 1000], velocity=[0, 0, 0])
    )
    dt = 0.02
    initial_fuel = phys.fuel_mass

    # Step with 100% throttle
    for _ in range(50): # 1.0 second
        phys.step(throttle_cmd=1.0, rcs_torque_cmd=np.zeros(3), dt=dt)

    # Fuel must be consumed
    assert phys.fuel_mass < initial_fuel
    # Upward acceleration must overcome Mars gravity:
    # F_thrust = 5500 N, mass ~ 1100 kg -> a_thrust ~ 5.0 m/s^2 > g (3.71 m/s^2)
    assert phys.vel[2] > -2.0
