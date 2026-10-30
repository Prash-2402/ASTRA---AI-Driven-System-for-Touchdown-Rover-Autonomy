# Experimental Methodology

**Research question:** Can fault-specific, uncertainty-aware adaptive replanning improve rover mission performance
compared with a fixed rule-based response controller while maintaining safety?

## Design
- Controllers: ASTRA vs FSM baseline (identical everything except response policy — see FSM_BASELINE.md).
- Conditions (`experiments/scenarios/rover_conditions.py`): nominal; four single faults injected at t = 20 s;
  paired tier (reported separately): dropout + actuator (+10 s), misclassification + power (+10 s).
- Terrains: 1–3 development (all tuning/calibration happened here); 4–5 held-out (evaluation only; enforced by API).
- Matching: trial i uses seed base_seed + i for both controllers → identical terrain, noise streams, initial
  conditions and fault cells.
- Target: N = 20 matched trials per condition per held-out terrain (560 runs). Infrastructure supports it; see
  the experiment record for the N actually completed.
- Success: rover stops within 0.6 m of the target by its estimate, is truly within 1.5 m, with zero collisions
  (chassis contact or contact with rocks > 0.25 m), no tilt > 30° and no battery < 5 %, within 600 s.

## Metrics
Primary: completion rate; time-to-completion (successful missions).
Secondary: energy, remaining SoC, route length, collisions, safety violations, detection delay, classification
accuracy (first classification after injection contains the injected class; ASTRA only), recovery success,
replanning time, position/heading estimation error, mean EKF σ.

## Development-phase calibration (disclosed)
Changes made on development terrains before held-out evaluation: lidar self-return masking; robust obstacle test;
EKF relocalisation; path smoothing; generator feasibility check; actuator torque budget 22 → 8 N m and degradation
0.25 → 0.3 (so the fault is physically consequential but survivable); battery 0.6 → 0.8 SoC; classification
debounce for both controllers; gentle-turn actuator response. No change was made after looking at held-out results.
