import numpy as np
import pytest

from autonomy.decision.fsm_baseline import FSMBaseline
from autonomy.fault_detection.detector import AnomalyDetector, ClassificationDebouncer, DetectorConfig, FaultClassifier
from autonomy.fault_detection.evidence import Evidence
from autonomy.planning.astar import astar
from autonomy.safety.rover_supervisor import RoverSafetySupervisor, SafetyConfig
from simulation.rover.power import Battery, BatteryConfig
from simulation.rover.terrain import DEVELOPMENT, HELD_OUT, VARIANTS, generate, oracle_feasible


def test_exactly_five_deterministic_feasible_terrains_with_split():
    assert sorted(VARIANTS) == [1, 2, 3, 4, 5] and DEVELOPMENT == (1, 2, 3) and HELD_OUT == (4, 5)
    for v in VARIANTS:
        a, b = generate(v), generate(v)
        assert np.array_equal(a.heights, b.heights) and a.obstacles == b.obstacles
        assert oracle_feasible(a)


def test_astar_avoids_hard_cells_and_reports_no_path():
    cost = np.ones((60, 60)); hard = np.zeros((60, 60), bool)
    hard[5:55, 30] = True                      # wall between start (j=10) and goal (j=50), open at the ends
    r = astar(cost, hard, (-20.0, -20.0), (-20.0, 20.0))
    assert r["found"] and all(not hard[c] for c in r["cells"][1:-1])
    assert r["length"] > 40                    # had to go around the wall
    hard[:, 30] = True                         # full wall
    assert not astar(cost, hard, (-20.0, -20.0), (-20.0, 20.0))["found"]


def test_battery_energy_accounting_and_drain_fault():
    b = Battery(BatteryConfig(capacity_wh=10, initial_soc=1.0))
    for _ in range(3600):
        b.step(np.zeros(6), np.zeros(6), 1.0)
    assert abs(b.energy_used_wh - b.cfg.electronics_w) < 1e-6          # 1 h of electronics only
    b2 = Battery(BatteryConfig(capacity_wh=10, initial_soc=1.0)); b2.drain_factor = 3.0; b2.parasitic_w = 60
    b2.step(np.zeros(6), np.zeros(6), 1.0)
    assert abs(b2.power - (3 * b2.cfg.electronics_w + 60)) < 1e-9


def ev(**kw):
    e = Evidence(t=10.0)
    for k, v in kw.items():
        setattr(e, k, v)
    return e


@pytest.mark.parametrize("kw,label", [
    ({"lidar_stale": 3.0, "camera_stale": 3.0}, "sensor_dropout"),
    ({"perception_inconsistency": 0.4, "perception_checked": 80}, "terrain_misclassification"),
    ({"battery_ratio": 2.5}, "power_drain"),
    ({"wheel_residual": np.array([0.5, 0, 0, 0, 0, 0]), "wheel_capability": np.array([0.3, 1, 1, 1, 1, 1])}, "actuator_degradation"),
])
def test_classifier_identifies_each_fault_from_evidence(kw, label):
    det = AnomalyDetector(DetectorConfig())
    e = ev(**kw)
    for _ in range(6):
        a = det.update(e)
    c = FaultClassifier().classify(e, a)
    assert a["anomaly"] and label in c["labels"] and not c["uncertain"]


def test_ambiguous_evidence_is_classified_uncertain():
    e = ev(visloc_nis=60.0)                    # model mismatch without a fault-specific signature
    det = AnomalyDetector(DetectorConfig())
    for _ in range(6):
        a = det.update(e)
    assert FaultClassifier().classify(e, a)["uncertain"]


def test_debouncer_requires_persistence():
    d = ClassificationDebouncer(engage_s=1.0, release_s=3.0)
    assert d.update(0.0, {"x"}) == frozenset()
    assert d.update(1.1, {"x"}) == frozenset({"x"})
    assert d.update(1.2, set()) == frozenset({"x"})      # release needs 3 s
    assert d.update(4.5, set()) == frozenset()


def test_safety_supervisor_hard_constraints():
    s = RoverSafetySupervisor(SafetyConfig())
    assert s.check({"soc": 0.1})["action"] == "safe_halt"
    assert s.check({"soc": 0.9, "front_range": 0.3})["speed_cap"] == 0.0
    assert s.check({"soc": 0.9, "position": (29.5, 0.0)})["action"] == "replan"
    assert s.check({"soc": 0.9, "lidar_stale": 5.0})["speed_cap"] <= SafetyConfig().blind_speed_factor


def test_fsm_fixed_rules():
    f = FSMBaseline()
    assert f.decide(0, {"anomaly": True, "flags": {"x": 0}}, ev(), 0.9)["speed_factor"] == 0.5
    assert f.decide(1, {"anomaly": False, "flags": {}}, ev(lidar_stale=3.0), 0.9)["speed_factor"] == 0.0
    assert f.decide(2, {"anomaly": False, "flags": {}}, ev(), 0.1)["halt"]


@pytest.mark.slow
def test_rover_physics_drives_by_wheel_actuation():
    from simulation.rover.world import RoverWorld, WorldConfig
    t = generate(1)
    w = RoverWorld(t, WorldConfig(physics_hz=120.0), start_heading=np.arctan2(t.target[1] - t.start[1], t.target[0] - t.start[0]))
    p0 = w.base_state()[0]
    assert abs(w.wheel_contact_normals().sum() - w.geom.total_mass * 3.72076) / (w.geom.total_mass * 3.72076) < 0.15
    for _ in range(120 * 10):
        w.set_wheels(np.full(6, 2.0), np.full(6, 8.0)); w.step()
    d = np.linalg.norm(w.base_state()[0][:2] - p0[:2])
    assert 0.8 * 3.2 < d <= 3.3                       # v = w r = 0.32 m/s for 10 s, minus slip
    ja = w.joint_angles()
    assert abs(ja["rocker_L_joint"] + ja["rocker_R_joint"]) < 0.02   # differential couples rockers
    w.close()


@pytest.mark.slow
def test_fault_injectors_change_simulated_world_identically_across_controllers():
    from simulation.rover.mission import RoverConfig, RoverMission
    corr = []
    for ctrl in ("astra", "fsm"):
        m = RoverMission(RoverConfig(terrain=1, controller=ctrl, seed=3, duration=40,
                                     faults=[{"fault_type": "terrain_misclassification", "start": 5.0},
                                             {"fault_type": "actuator_degradation", "start": 5.0},
                                             {"fault_type": "power_drain", "start": 5.0}]))
        m.run(max_time=12)
        assert m.actuator_factor[0] == 0.3 and m.battery.drain_factor == 3.0 and m.sensors.misclass_fraction == 0.15
        from simulation.rover.sensors import stable_unit
        corr.append([stable_unit(3, "misclass", i, j) < 0.15 for i in range(60) for j in range(60)])
        m.close()
    assert corr[0] == corr[1]


@pytest.mark.slow
def test_rover_reproducible_and_nominal_controllers_identical():
    from simulation.rover.mission import RoverConfig, RoverMission
    res = []
    for ctrl in ("astra", "astra", "fsm"):
        m = RoverMission(RoverConfig(terrain=1, controller=ctrl, seed=9, duration=60))
        m.run(); res.append(m.world.base_state()[0]); m.close()
    assert np.allclose(res[0], res[1], atol=1e-9)        # same seed -> same result
    assert np.allclose(res[0], res[2], atol=1e-6)        # no faults -> ASTRA == FSM
