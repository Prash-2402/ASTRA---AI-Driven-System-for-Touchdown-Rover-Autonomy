# Adaptive Planning (Rover)

## Cost map (`autonomy/planning/traversability.py`) — hard vs soft
**Hard (impassable):** 2 m geofence border · lidar obstacles dilated by 0.9 m + 1.5·σ_pos · perceived slope > 22°
(16° under actuator degradation) · camera-untraversable cells (unless geometry-dominant mode and lidar sees flat ground).

**Soft (cost per metre):**
`1 + w_slope (s/s_max)² + w_class·c(class) + w_unknown·unseen + w_unc·σ_pos + w_energy·(s/s_max + sand) + w_act·(1 − health)(s/10 + 2·sand)`
Defaults: w_slope 2, w_class 1, w_unknown 0.4, w_unc 0.5, w_energy 0, w_act 0. Class cost: bedrock 0, regolith 0.25,
sand 1.4, rock 3, unknown 0.6.

## A* (`autonomy/planning/astar.py`)
8-connected 1 m grid, edge cost = length × mean cell cost, admissible heuristic c_min·euclidean, no corner cutting.
Paths are smoothed by line-of-sight shortcutting only if the corridor (line + 4-neighbours) is free of hard cells
and the worst cost is within 1.15× of the replaced segment. Planning time is logged per replan.

## Replanning triggers
Both controllers: initial plan; remaining route crosses a newly hard cell (checked at 2 Hz, ignoring the rover's
own neighbourhood); safety-supervisor REPLAN; no path (retry every 2 s, safe-halt after 30 s).
ASTRA only: fault-specific replanning when the debounced classification changes (weights from the response table).

## Motion control (`autonomy/control/pure_pursuit.py`)
Look-ahead 1.8 m (2.9 m in gentle mode), κ = 2 sin α / L_d, v = v_max·factor·max(0.25, 1 − |α|/1.2),
pivot turn if |α| > 70°. Skid-steer: ω_L,R = (v ∓ ωB_eff/2)/r, B_eff = 1.35 m. Traction control above slip 0.35.

## Energy management
Route energy predicted with `RouteEnergyModel` (P_fixed/v + m g (C_rr + ½ sin s)/η per metre). The safety supervisor
compares it with (SoC − reserve)·C every 2 s and requests a replan if infeasible; below the reserve it safe-halts.
