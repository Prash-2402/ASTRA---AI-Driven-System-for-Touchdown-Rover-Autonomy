import numpy as np

from simulation.touchdown.environment import G0, Atmosphere, PlanetConfig
from simulation.touchdown.lander import ActuatorCommand, Lander, LanderParams


def vacuum():
    return Atmosphere(PlanetConfig(rho0=0.0, wind=[0, 0, 0], gust_std=0.0), np.random.default_rng(0))


def test_free_fall_matches_analytic():
    g = 3.72076
    L = Lander(LanderParams(), [0, 0, 1000], [0, 0, 0], [1, 0, 0, 0])
    atm = vacuum()
    for _ in range(1000):
        L.step(ActuatorCommand(), 0.01, atm, g, 0.0)
    assert abs(L.pos[2] - (1000 - 0.5 * g * 10 ** 2)) < 1e-6
    assert abs(L.vel[2] + g * 10) < 1e-9


def test_hover_throttle_balances_gravity_and_mass_flow_follows_rocket_equation():
    p = LanderParams()
    g = 3.72076
    L = Lander(p, [0, 0, 1000], [0, 0, 0], [1, 0, 0, 0])
    L.throttle = p.wet_mass * g / p.max_thrust
    atm = vacuum()
    m0 = L.mass
    L.step(ActuatorCommand(throttle=L.throttle), 0.01, atm, g, 0.0)
    assert abs(L.last_accel[2]) < 0.01
    expected_mdot = L.throttle * p.max_thrust / (p.isp * G0)
    assert abs((m0 - L.mass) / 0.01 - expected_mdot) / expected_mdot < 0.01


def test_torque_produces_angular_acceleration_tau_over_inertia():
    p = LanderParams()
    L = Lander(p, [0, 0, 1000], [0, 0, 0], [1, 0, 0, 0])
    L.torque = np.array([1.0, 0, 0])
    L.step(ActuatorCommand(throttle=0.2, torque=np.array([1.0, 0, 0])), 0.001, vacuum(), 3.72, 0.0)
    I = p.inertia_full[0] * L.mass / p.wet_mass
    assert abs(L.last_ang_accel[0] - p.max_torque[0] / I) / (p.max_torque[0] / I) < 0.02


def test_tilted_thrust_creates_lateral_acceleration():
    from simulation.common.math3d import euler_to_quat
    p = LanderParams()
    L = Lander(p, [0, 0, 1000], [0, 0, 0], euler_to_quat(0, 0.2, 0))
    L.throttle = 0.5
    L.step(ActuatorCommand(throttle=0.5), 0.01, vacuum(), 3.72, 0.0)
    assert L.last_accel[0] > 0.5   # +pitch tilts body z toward +x


def test_drag_opposes_relative_velocity():
    atm = Atmosphere(PlanetConfig(wind=[0, 0, 0], gust_std=0.0), np.random.default_rng(0))
    L = Lander(LanderParams(), [0, 0, 100], [50, 0, 0], [1, 0, 0, 0])
    L.step(ActuatorCommand(), 0.01, atm, 3.72, 0.0)
    assert L.last_accel[0] < 0
