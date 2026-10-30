# ASTRA Build Report

Local git history (not pushed, per owner instruction): 9 commits, one per section.

## Phase status
| Phase | Acceptance criterion | Status |
|---|---|---|
| 1 Foundation & design system | ASTRA launches; both module entry points accessible | ✅ verified in headless Chromium (15 routes, 0 console errors) |
| 2 Touchdown physics | lander responds to actual control inputs | ✅ analytic tests (free fall, hover, ṁ, τ/I, drag) |
| 3 Touchdown intelligence | complete landing mission + debrief | ✅ PID & MPC land; hidden-hazard diversion verified live in the UI; PDF debrief. ⚠ PPO not converged (handed off) |
| 4 Rover physics | rover physically traverses terrain | ✅ wheel-actuated PyBullet rocker-bogie, differential verified |
| 5 Rover estimation & navigation | reaches target under nominal conditions | ✅ dev terrain 1 (both controllers); ⚠ terrain 2 touches rocks in some seeds; ❌ terrain 3 corridor not found |
| 6 Rover fault autonomy | faults injected, rover responds via control/planning | ✅ four injectors, detection, classification, responses, FSM, safety supervisor |
| 7 Experiment engine | reproducible ASTRA vs FSM comparison | ✅ engine, held-out guard, statistics, exports; held-out batch running (incomplete) |
| 8 UI integration | every control operates against the backend | ✅ all controls wired to API/WebSocket |
| 9 Validation & release | runnable, tested, documented | ✅ 53/53 tests pass; 23 docs + PPO guide; Docker/CI files written (⚠ Docker images not built in this environment; CI not run on GitHub) |

## Bugs found and fixed through verification (selection)
Relief metric measured lidar noise (false diversions) · lidar self-returns created phantom obstacles · grazing-angle
obstacle false positives · rover drove off the map edge (no geofence) · EKF over-confidence rejected all position
fixes during slip · held-out terrains were infeasible for any controller · actuator fault was physically invisible
· FSM lacked the hysteresis ASTRA had (unfair baseline) · PPO v1 reward exploitation · frontend chunk-split crash ·
scenario-builder config merge crash.

## Held-out experiment (#4) — INTERIM, 56/140 trials
| Terrain | Condition | ASTRA | FSM |
|---|---|---|---|
| T4 | nominal | 0/5 | 2/5 |
| T4 | sensor dropout | 0/5 | 0/5 |
| T5 | nominal | 0/2 | 0/3 |
| T5 | sensor dropout | 0/5 | 0/5 |
| T5 | misclassification | 0/5 | 0/5 |
| T5 | power drain | 0/4 | 0/3 |

**Interpretation:** (1) Floor effect — nominal navigation largely fails on the unseen terrains, so the fault-response
comparison is not yet informative. (2) On nominal T4 ASTRA underperforms the FSM: false alarms on unseen terrain
trigger the "uncertain → conservative" response. Both point to generalisation gaps in perception/navigation and in
the uncertain-classification policy — not to be fixed by tuning on held-out results. Dev-terrain single trials
(n = 1, T1) showed ASTRA faster under sensor dropout (316 s vs 357 s) and misclassification (346 s vs 464 s).

The batch is resumable (Experiment Lab → *Run / resume*, or `python scripts/run_heldout_experiment.py --resume 4`).

## Recommended next steps
1. Improve nominal navigation on development terrains (perceived-slope accuracy, corridor finding) until dev nominal
   success is high; then create a **new** held-out experiment (do not reuse #4 for tuning decisions).
2. Revisit the "uncertain" response (higher evidence threshold or no slow-down on model-mismatch alone).
3. Complete PPO per `docs/PPO_TRAINING_GUIDE.md`.
4. Re-tune lander EKF process noise (error exceeds ±2σ).
5. Grant GitHub access and push when you decide to.
