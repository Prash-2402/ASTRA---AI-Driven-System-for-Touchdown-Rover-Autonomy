# Rover Terrain Generation

Exactly five variants (`simulation/rover/terrain.py`), 60 m × 60 m, height 0.25 m, classes 1 m.

| # | Name | Split | Features |
|---|---|---|---|
| 1 | Mixed flat and uneven | development | 0.35 m relief, 2° slope, 35 rocks, 1 rock field |
| 2 | Rocky distributed obstacles | development | 120 rocks, 2 rock fields |
| 3 | Sloped narrow corridors | development | 6°/2° slope, 3 ridges with gaps |
| 4 | Irregular complex | **held-out** | 0.6 m relief, 2 fields, 1 ridge, 18 % sand |
| 5 | Complex alternate hazards | **held-out** | 3 fields, 2 ridges, different slope direction |

Generation: FFT fractal relief + regional slope + Gaussian ridges with super-Gaussian gaps; class map from
thresholded smooth noise (bedrock/regolith/sand) and circular rock fields (impassable, dense boulders);
rocks with uniform radius ranges; start/target neighbourhoods cleared.

**Determinism & feasibility:** each variant has a fixed generation seed. An oracle planner using TRUE terrain
(slope ≤ 22°, dilated rocks/fields) must find a path; otherwise the next sub-seed is used deterministically.
This is generator validation only — no controller result is used. Variant 4 required sub-seed 1. This check
was introduced after discovering that variants 4–5 were originally infeasible for any controller.

Ground truth (heights, classes, rocks) is used by physics, sensor synthesis and evaluation only. The planner
uses the perceived map (`autonomy/planning/rover_perception.py`). Held-out terrains are never used for tuning.
