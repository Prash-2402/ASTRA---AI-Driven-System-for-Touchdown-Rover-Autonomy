import numpy as np
import pytest

from autonomy.planning.landing_perception import LidarConfig, PerceivedHazardMap
from autonomy.planning.landing_site import DiversionConfig, DiversionPlanner, LandingSiteAssessor
from autonomy.prediction.touchdown_predictor import TouchdownPredictor
from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
from simulation.touchdown.terrain import Terrain, TerrainConfig


class FlatDEM:
    def height(self, x, y): return 0.0
    def gradient(self, x, y): return (0.0, 0.0)


def flat_terrain(**kw):
    t = Terrain(TerrainConfig(n_craters=0, rock_density_per_km2=0, roughness_m=0.0, regional_slope_deg=0.0, **kw), np.random.default_rng(0))
    t.heights[:] = 0.0
    t._update_slope()
    return t


def scanned(t, center=(0, 0), agl=150.0):
    hm = PerceivedHazardMap(LidarConfig())
    for _ in range(2):
        hm.scan(t, np.array([center[0], center[1], agl]), np.array([center[0], center[1], agl]), agl, np.array(center), np.random.default_rng(1))
    return hm


def test_assessor_accepts_flat_site_and_rejects_boulder():
    t = flat_terrain()
    a = LandingSiteAssessor().assess(0, 0, scanned(t), 0.5)
    assert a.covered and a.safe
    t.add_hazard_field(0, 0, 10, np.random.default_rng(2))
    a2 = LandingSiteAssessor().assess(0, 0, scanned(t), 0.5)
    assert not a2.safe and any("rock" in r for r in a2.reasons)


def test_relief_metric_is_not_fooled_by_sensor_noise():
    t = flat_terrain()
    a = LandingSiteAssessor().assess(0, 0, scanned(t, agl=450.0), 0.5)
    assert a.relief_m < 0.15   # noise variance is subtracted


def test_diversion_selects_feasible_safe_site_and_respects_fuel():
    t = flat_terrain()
    t.add_hazard_field(0, 0, 15, np.random.default_rng(2))
    hm = scanned(t, agl=200)
    pred = TouchdownPredictor(FlatDEM(), 10000, 225, 1100)
    planner = DiversionPlanner(DiversionConfig(), LandingSiteAssessor(), pred, {"dry_mass": 1100, "isp": 225, "max_thrust": 10000})
    est = {"p": np.array([0.0, 0.0, 200.0]), "v": np.array([0.0, 0.0, -10.0]), "agl": 198.8, "fuel": 200.0}
    plan = planner.plan(est, np.array([0.0, 0.0, 0.0]), hm, 0.5, 3.72)
    sel = plan["selected"]
    assert sel is not None and np.hypot(sel["x"], sel["y"]) > 10
    assert sel["predicted"]["fuel_margin"] >= 0
    est_low = {**est, "fuel": 5.0}
    assert planner.plan(est_low, np.array([0.0, 0.0, 0.0]), hm, 0.5, 3.72)["selected"] is None


@pytest.mark.parametrize("ctrl", ["pid", "mpc"])
def test_full_landing_mission_nominal(ctrl):
    m = TouchdownMission(TouchdownConfig(controller=ctrl, seed=42))
    r = m.run()
    assert r["outcome"] == "landed" and r["success"]
    assert abs(r["touchdown"]["vertical_speed"]) < 2.5
    assert r["phase_history"][-1]["to"] == "MISSION COMPLETE"


def test_hidden_hazard_triggers_physical_diversion_and_audited_outcome():
    m = TouchdownMission(TouchdownConfig.from_dict({"controller": "pid", "seed": 42, "terrain": {"hazard_at_target": True}}))
    r = m.run()
    assert r["diversions"] >= 1 and r["success"]
    assert r["distance_from_original_target_m"] > 10
    ev = m.audit.events[0]
    assert ev.details["alternatives"] and ev.actual_outcome["landed_safely"] is True
    # never teleported: max step between consecutive 10 Hz frames bounded by velocity
    pos = np.array([f["truth"]["position"] for f in m.telemetry])
    assert np.max(np.linalg.norm(np.diff(pos, axis=0), axis=1)) < 15.0


def test_supervisor_rejects_illegal_transition():
    from autonomy.decision.touchdown_supervisor import SupervisorConfig, TouchdownSupervisor
    from shared.enums import TouchdownPhase as Ph
    s = TouchdownSupervisor(SupervisorConfig())
    with pytest.raises(RuntimeError):
        s.transition(Ph.TOUCHDOWN, 0.0, "skip")


def test_touchdown_reproducible_with_same_seed():
    a = TouchdownMission(TouchdownConfig(seed=11)).run(max_time=30)
    m1, m2 = TouchdownMission(TouchdownConfig(seed=11)), TouchdownMission(TouchdownConfig(seed=11))
    m1.run(max_time=30); m2.run(max_time=30)
    assert np.allclose(m1.lander.x, m2.lander.x, atol=1e-9)
