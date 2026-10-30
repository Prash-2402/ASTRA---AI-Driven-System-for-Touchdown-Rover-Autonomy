import numpy as np

from simulation.moon.environment import MOON_GRAVITY
from simulation.moon.lander import LunarLander, LunarLanderParams
from simulation.moon.mission import MoonConfig, MoonLandingMission
from simulation.rover.skycrane import simulate_skycrane


def test_lunar_free_fall_matches_analytic_and_has_no_drag():
    L = LunarLander(LunarLanderParams(), [0, 0, 1000], [30.0, 0, 0])
    L.engine_on = False
    for _ in range(500):
        L.step(0.0, np.zeros(2), 0.02)
    assert abs(L.pos[2] - (1000 - 0.5 * MOON_GRAVITY * 10 ** 2)) < 1e-6
    assert abs(L.vel[0] - 30.0) < 1e-9          # no atmosphere: horizontal speed conserved


def test_lunar_engine_mass_flow_follows_isp():
    p = LunarLanderParams()
    L = LunarLander(p, [0, 0, 1000], [0, 0, 0])
    L.throttle = 0.5
    m0 = L.mass
    L.step(0.5, np.zeros(2), 0.02)
    mdot = (m0 - L.mass) / 0.02
    assert abs(mdot - L.throttle * p.max_thrust / (p.isp * 9.80665)) / mdot < 0.05


def test_moon_landing_succeeds_and_is_deterministic():
    a = MoonLandingMission(MoonConfig(seed=11)).run()
    b = MoonLandingMission(MoonConfig(seed=11)).run()
    assert a["outcome"] == "landed" and abs(a["touchdown"]["vertical_speed"]) <= 3.0
    assert a["phase_history"][0]["to"] == "TERMINAL DESCENT (P66)"
    assert a["landing_error_m"] == b["landing_error_m"]


def test_moon_dust_only_near_surface():
    m = MoonLandingMission(MoonConfig(seed=11))
    m.run(max_time=20)
    assert m.dust_rate() == 0.0                  # high above the surface: no erosion
    m.run()
    assert m.max_dust > 0.1 and m.dust_total > 0


def test_skycrane_touchdown_speed_swing_and_flyaway():
    r = simulate_skycrane((0.0, 0.0), lambda x, y: 0.0, heading=0.3, seed=1, rover_mass=64.0)
    td = r["touchdown"]
    assert abs(abs(td["vertical_speed"]) - 0.75) < 0.05 and td["error_m"] < 0.5
    swing = np.degrees(np.max(np.abs([f["swing"] for f in r["frames"]])))
    assert swing < 5.0
    phases = [f["phase"] for f in r["frames"]]
    assert phases.index("SKY CRANE") < phases.index("TOUCHDOWN") < phases.index("FLYAWAY")
    assert r["frames"][-1]["ds"][2] > 50              # descent stage departed
