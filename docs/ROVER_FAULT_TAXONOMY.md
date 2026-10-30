# Rover Fault Taxonomy (closed — four classes)

| # | Fault | Injection (changes the simulated world) | Default |
|---|---|---|---|
| 01 | `sensor_dropout` | LiDAR and/or camera return no data (`missing`) or random data (`corrupted`); visloc lost with camera | both sensors, 45 s |
| 02 | `terrain_misclassification` | invert traversability of a fraction of observed cells; cell selection = hash(seed, cell) so **identical for both controllers** | 15 % |
| 03 | `power_drain` | actual consumption × factor + parasitic load | ×3, +60 W |
| 04 | `actuator_degradation` | one wheel's true torque capability × factor | front-left, 0.3 |

Faults never inform the autonomy stack directly. The API rejects any other fault type (HTTP 422).

## Detection & classification (`autonomy/fault_detection/`)
Independent components: **AnomalyDetector** (thresholds + 5-tick persistence) → **FaultClassifier**
(per-class scores, confidence, multi-label for paired faults, `uncertain` if no class ≥ 0.5 or max confidence
< 0.45) → **ClassificationDebouncer** (engage 1 s, release 3 s) → **AstraResponseSelector** → **RecoveryVerifier**
(≥ 1.5 m progress within 25 s without halt).

| Evidence | Primarily indicates |
|---|---|
| sensor staleness; steep-ring range inconsistency (attitude-compensated) | dropout |
| isolated camera-untraversable labels on lidar-flat ground; camera-traversable cells with lidar obstacles on gentle slopes | misclassification |
| measured / predicted electrical power (EWMA) | power drain |
| isolated wheel tracking residual + torque ceiling below command | actuator degradation |
| visloc NIS | model mismatch (not a specific fault) → uncertain |

## ASTRA responses
| Class | Response |
|---|---|
| uncertain | conservative: 50 % speed, wider margins, replan |
| dropout | continue on mapped route at 35 % speed while σ_pos < 0.45 m, else hold for relocalisation; uncertainty-weighted costs |
| misclassification | geometry-dominant traversability (lidar overrides camera where it has coverage), replan |
| power drain | update fixed-load estimate, energy-weighted route, keep efficient (not reduced) speed |
| actuator | torque reallocation to same-side wheels, low-curvature tracking (no pivots), slope/sand-averse route, 75 % speed |
