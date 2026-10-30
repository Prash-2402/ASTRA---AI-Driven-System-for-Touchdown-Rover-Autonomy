import numpy as np

from autonomy.control.lander_allocation import AllocationConfig, allocate
from autonomy.control.lander_mpc import LanderMPCConfig, LanderMPCController
from autonomy.control.pid import PID, PIDGains
from autonomy.control.pure_pursuit import PurePursuit, PurePursuitConfig
from simulation.touchdown.lander import LanderParams


def test_pid_converges_first_order_plant():
    pid = PID(PIDGains(kp=2.0, ki=1.0, out_min=-5, out_max=5))
    x = 0.0
    for _ in range(2000):
        x += pid(1.0 - x, 0.01)[0] * 0.01
    assert abs(x - 1.0) < 1e-3


def test_pid_anti_windup_limits_integrator_under_saturation():
    pid = PID(PIDGains(kp=1.0, ki=1.0, out_min=-1, out_max=1, i_limit=100))
    for _ in range(1000):
        pid(10.0, 0.01)                   # permanently saturated
    assert abs(pid.i[0]) < 1.0            # conditional integration stops wind-up


def test_mpc_respects_thrust_and_tilt_constraints():
    c = LanderMPCController(LanderMPCConfig())
    est = {"p": np.array([300.0, -200.0, 800.0]), "v": np.array([20.0, 10.0, -40.0]), "agl": 800.0, "g": 3.72,
           "mass": 1500.0, "max_thrust": 10000.0, "min_thrust": 1500.0}
    sol = c.solve(est, np.array([0.0, 0.0, 0.0]))
    U = c.u_prev
    amax = 10000 / 1500
    tan_t = np.tan(np.radians(30))
    for u in U:
        assert np.linalg.norm(u) <= amax * 0.98 + 1e-6
        assert np.hypot(u[0], u[1]) <= tan_t * u[2] + 1e-6
        assert u[2] >= 1500 / 1500 - 1e-9
    assert len(sol["predicted_positions"]) == c.cfg.horizon + 1


def test_allocation_limits_tilt_and_never_commands_downward_thrust():
    p = LanderParams()
    cmd, info = allocate(np.array([20.0, 0.0, 1.0]), np.zeros(3), np.zeros(3), 1500.0, p, AllocationConfig(tilt_max_deg=25))
    assert info["tilt_cmd_deg"] <= 25.0 + 1e-6
    cmd2, _ = allocate(np.array([0.0, 0.0, -10.0]), np.zeros(3), np.zeros(3), 1500.0, p, AllocationConfig())
    assert cmd2.throttle >= 0.0


def test_pure_pursuit_turns_toward_path_and_degraded_wheel_reallocation():
    pp = PurePursuit(PurePursuitConfig())
    pp.set_path([(0, 0), (1, 1), (2, 2), (3, 3)])
    speeds, torques, info = pp.compute((0.0, 0.0, 0.0), 1.0, 0.0, np.ones(6))
    assert speeds[3] > speeds[0]                       # left turn: right wheels faster
    health = np.ones(6); health[0] = 0.3
    _, t2, _ = pp.compute((0.0, 0.0, np.pi / 4), 1.0, 0.0, health)
    assert t2[0] < t2[1] and t2[1] > PurePursuitConfig().wheel_torque    # same-side healthy wheels get headroom
