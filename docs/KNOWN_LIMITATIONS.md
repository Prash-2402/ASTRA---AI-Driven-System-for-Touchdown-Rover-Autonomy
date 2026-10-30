# Known Limitations (honest list)

## Touchdown
- No hypersonic entry/parachute phase: "ENTRY" is an unpowered coast from ~2.9 km before powered descent.
- Flat-planet local frame; exponential atmosphere; inertia scales with mass (no propellant slosh/CoM shift).
- No post-contact (leg/ground) dynamics: touchdown is evaluated at first footpad contact.
- MPC uses a point-mass model and SLSQP (local NLP solver), ~25 ms/solve in Python; no real-time guarantees.
- Lander EKF is somewhat over-confident: in live runs the horizontal position error frequently lies outside the
  filter's ±2σ band (visible on the Touchdown page). Process-noise tuning / bias states need review.
- **PPO: no converged policy** (see PPO_TRAINING_GUIDE.md).

## Rover
- Skid steering (no steerable corner wheels); rocker/bogie links have no collision geometry.
- Terrain–wheel interaction is rigid-body contact + per-class friction & rolling resistance; no terramechanics
  (no sinkage, no Bekker model).
- Camera/perception is an abstraction (class labels with confusion), not image processing.
- Perceived slope error on steep terrain is large (p95 ≈ 9–11° on terrain 3); nominal traverses of terrain 3 fail
  to find the narrow corridor. Nominal terrain 2 touches rocks in some seeds.
- Collision = chassis contact or contact with a rock > 0.25 m; climbing smaller rocks is permitted.
- Physics at 120 Hz (checked against 240 Hz for outcome class, not trajectory-level equivalence).
- Experiment wall time ≈ 40–100 s per trial on one core → the N = 20 target (560 runs) needs several CPU-hours;
  see the experiment record for N actually completed.
- Fault severities were calibrated on development terrains (documented in EXPERIMENTAL_METHODOLOGY.md).

## Platform
- Single live session per module; no authentication (local research tool).
- Telemetry archives grow on disk (~1 MB per interactive run); no retention policy yet.
