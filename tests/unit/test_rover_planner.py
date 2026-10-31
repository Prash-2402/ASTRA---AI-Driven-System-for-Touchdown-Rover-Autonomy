"""Surface-operations planner: route stability and costmap sensitivity."""
import numpy as np

from autonomy.planning.astar import astar, path_cost
from autonomy.planning.rover_perception import M, RoverPerceivedMap, center_of
from autonomy.planning.traversability import HARD_PENALTY, CostWeights, build_costmap, inflation_cells

OPS = CostWeights(inflation_m=1.6, sigma_inflation=0.5, inflation_rounding="round", size_aware=True, camera_soft=True,
                  max_slope_deg=26.0, clearance_m=1.0, w_clearance=0.6)


def flat_map() -> RoverPerceivedMap:
    return RoverPerceivedMap(np.zeros((M, M)))


def test_astar_is_deterministic():
    pm = flat_map()
    pm.obstacle[28:32, 25:35] = True
    cost, hard, _ = build_costmap(pm, OPS, 0.2)
    a = astar(cost, hard, (-20.0, 0.0), (20.0, 0.0), stable=True)
    b = astar(cost, hard, (-20.0, 0.0), (20.0, 0.0), stable=True)
    assert a["found"] and a["cells"] == b["cells"]


def test_inertia_keeps_the_current_route_between_equal_alternatives():
    pm = flat_map()
    pm.obstacle[29:31, 26:34] = True          # a wall straddling the straight line: north and south detours cost the same
    cost, hard, _ = build_costmap(pm, OPS, 0.2)
    free = astar(cost, hard, (-12.0, 0.0), (12.0, 0.0), stable=True)
    side = np.sign(np.mean([center_of(*c)[1] for c in free["cells"]]))
    mirror = [(i, M - 1 - j) for i, j in free["cells"]]          # the same route reflected to the other side
    kept = astar(cost, hard, (-12.0, 0.0), (12.0, 0.0), prefer_cells=mirror, inertia=0.85, stable=True)
    assert np.sign(np.mean([center_of(*c)[1] for c in kept["cells"]])) == -side
    # the reported cost is the true (undiscounted) one
    assert abs(kept["cost"] - path_cost(kept["cells"], cost)) < 1e-6


def test_round_inflation_does_not_flicker_with_position_sigma():
    radii = {inflation_cells(OPS, s) for s in np.linspace(0.05, 0.75, 30)}
    assert radii == {2}
    legacy = {inflation_cells(CostWeights(inflation_m=0.55), s) for s in np.linspace(0.05, 0.75, 30)}
    assert len(legacy) > 1                     # the old rule switched radius as sigma breathed (route flip-flop)


def test_camera_label_alone_does_not_block_in_soft_mode():
    pm = flat_map()
    pm.cam_trav[10:50, 10:50] = 0              # camera calls a large area untraversable, lidar sees nothing
    _, hard_soft, _ = build_costmap(pm, OPS, 0.2)
    _, hard_cam, _ = build_costmap(pm, CostWeights(), 0.2)
    assert not hard_soft[20:40, 20:40].any() and hard_cam[20:40, 20:40].all()


def test_gap_between_rocks_stays_open():
    pm = flat_map()
    pm.obstacle[30, 20] = pm.obstacle[30, 26] = True        # two rocks 6 m apart
    cost, hard, _ = build_costmap(pm, OPS, 0.3)
    assert not hard[30, 23]                    # the middle of the gap is drivable


def test_stuck_penalty_blocks_at_hard_level():
    pm = flat_map()
    extra = np.zeros((M, M)); extra[30, 30] = HARD_PENALTY; extra[31, 31] = 6.0
    cost, hard, _ = build_costmap(pm, OPS, 0.2, extra=extra)
    base, _, _ = build_costmap(pm, OPS, 0.2)
    assert hard[30, 30] and not hard[31, 31] and cost[31, 31] == base[31, 31] + 6.0


def test_route_takes_a_clear_gap_instead_of_detouring():
    pm = flat_map()
    pm.obstacle[30, 15:27] = True              # a wall of rocks across the way ...
    pm.obstacle[30, 33:45] = True              # ... with a 6-cell gap in the middle
    cost, hard, _ = build_costmap(pm, OPS, 0.2)
    r = astar(cost, hard, (-10.0, 0.5), (10.0, 0.5), stable=True)
    assert r["found"] and r["length"] < 22.0   # straight through the gap (~20 m), no detour around the wall ends


def scanned_flat() -> RoverPerceivedMap:
    pm = flat_map()
    pm.lidar_cnt[:, :] = 5; pm.lidar_sum[:, :] = 0.0; pm.lidar_min[:, :] = 0.0; pm.lidar_max[:, :] = 0.0
    return pm


def test_small_rock_gets_a_small_margin_big_rock_the_full_one():
    pm = scanned_flat()
    pm.obstacle[20, 20] = True; pm.lidar_max[20, 20] = 0.3          # a small, low rock
    pm.obstacle[40:43, 40:43] = True; pm.lidar_max[40:43, 40:43] = 0.9   # a boulder
    _, hard, _ = build_costmap(pm, OPS, 0.2)
    assert hard[20, 20] and hard[21, 20] and not hard[21, 21] and not hard[22, 20]   # 1-cell margin
    assert hard[44, 41] and hard[38, 41]                                              # 2-cell margin around the boulder


def test_narrow_tier_uses_any_gap_the_rover_fits():
    pm = scanned_flat()
    pm.lidar_max[30, :] = 0.3
    pm.obstacle[30, 10:28] = True              # two rock walls with a 3-cell gap (rock centres 4 m apart)
    pm.obstacle[30, 31:50] = True
    tight = OPS.with_(inflation_m=0.45)
    cost, hard, _ = build_costmap(pm, tight, 0.2)
    assert hard[30, 28] and not hard[30, 29] and hard[30, 30]   # centre of the gap open, sides keep the 1 m margin
    r = astar(cost, hard, (-10.0, -0.5), (10.0, -0.5), stable=True)
    assert r["found"] and r["length"] < 25.0    # goes through the gap, no detour round the walls
