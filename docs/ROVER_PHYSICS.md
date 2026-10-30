# Rover Physics

PyBullet (DIRECT), Mars gravity 3.72076 m/s², heightfield terrain (0.25 m), rocks as static sphere bodies.

| Quantity | Model |
|---|---|
| Wheel actuation | per-wheel VELOCITY_CONTROL with force limit = torque limit × true actuator factor |
| Wheel–ground friction | per-wheel lateral friction set every control tick from the TRUE surface class under the wheel (0.95 bedrock, 0.75 regolith, 0.45 sand) |
| Rolling resistance | τ = −sign(ω)·C_rr·N·r applied to each wheel every physics step; C_rr 0.03 / 0.06 / 0.16; N from contact normals |
| Slip | emerges from contact physics; estimated from odometry vs EKF velocity |
| Suspension | passive rocker & bogie revolute joints with damping; differential via JOINT_GEAR |
| Slopes | from terrain geometry + gravity (no special-casing) |
| Energy | see power model below |

## Power (`simulation/rover/power.py`)
P = Σ max(τ_i ω_i, 0)/η + k_cu Σ τ_i² + P_elec (η = 0.72, k_cu = 0.004 W/(N m)², P_elec = 22 W).
V = V_oc(SoC) − I R (V_oc 23–28 V, R = 0.08 Ω); I solves P = (V_oc − IR)I; dSoC/dt = −P/(3600 C). C = 20 Wh traverse
allocation, initial SoC 0.8, hard reserve 0.15.

## Validation
- Straight drive at ω = 2 rad/s for 10 s: 3.16 m vs 3.20 m no-slip (test `test_rover_physics_drives_by_wheel_actuation`).
- Static contact normals sum to m·g within 15 %; rockers move equal-and-opposite.
- Physics rate: 120 Hz chosen after a 240 Hz comparison gave the same outcome class on dev terrains 1–2.

Rover nominal parameters: 64 kg, wheel radius 0.16 m, torque limit 8 N m/wheel (~2–3× the demand of 15° slopes
in sand), max speed 0.4 m/s, skid steering (no steerable wheels — a simplification).
