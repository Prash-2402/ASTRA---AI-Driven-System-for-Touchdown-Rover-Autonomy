# Touchdown Guidance & Control

All guidance laws output a desired non-gravitational acceleration **a_cmd** (world frame). A shared
inner loop converts it to actuator commands, so controller comparisons isolate the guidance law.

## Thrust allocation & attitude control (`lander_allocation.py`)
1. T = m·a_cmd (T_z ≥ 0.05 m). Desired body-z = T/|T|, limited to tilt_max = 30°.
2. throttle = (T · z_b) / T_max (projection on the current thrust axis).
3. Lateral thrusters supply the residual T − throttle·T_max·z_b (body x/y).
4. Attitude PD: e = Rᵀ(z_b × z_des), yaw hold; τ = I(ω_n² e − 2ζω_n ω), ω_n = 2.2 rad/s, ζ = 0.9; saturated.

## Descent profile (`descent_profile.py`)
v_z,des = −max(v_td, min(√(2 a h), v_td + 0.15 h, 75)), a = 1 m/s², v_td = 0.7 m/s.
v_h,des = k_h (target − p), |v_h| ≤ min(40, 0.08 h + 1). Below 120 m with > 4 m horizontal error the
vertical rate is reduced so lateral alignment finishes first.

## Cascade PID (`lander_pid.py`)
Position/altitude → (profile) → velocity → PID → acceleration (+g) → allocation → attitude PD → torque.
Gains: horizontal kp 0.45, ki 0.04 (|a| ≤ 3 m/s²); vertical kp 0.9, ki 0.08 (−4…6 m/s²).
Anti-windup: conditional integration (integrate only when unsaturated or when the error drives out of
saturation) plus an integrator clamp.

## Model Predictive Control (`lander_mpc.py`)
Point-mass prediction with gravity, step 0.5 s, horizon N = 16 (8 s), control horizon Nc = 5 (move blocking).
```
min Σ_k Q_v‖v_k − v_ref,k‖² + Q_p‖p_k − p_ref,k‖² + R‖u_k − g ẑ‖² + R_Δ‖u_k − u_{k−1}‖² + W_gs·Σ max(0, tan γ‖p_xy − t_xy‖ − (p_z − h_t))²
s.t. ‖u_k‖² ≤ a_max²,  u_z ≥ a_min,  ‖u_xy‖ ≤ tan(tilt_max)·u_z
```
Q_v 1, Q_p 0.02, R 0.05, R_Δ 0.3, W_gs 2, γ = 15°. Reference = kinematic roll-out of the descent profile.
Solved with SLSQP (≤ 60 iterations, warm-started) every 0.25 s from the **estimated** state; the first input
is applied; the solution is projected onto the constraint set if SLSQP returns a marginally infeasible iterate.
Solve time, iterations and convergence are published in telemetry.

## Trajectory prediction (`touchdown_predictor.py`)
From the EKF state, roll out a point mass under the profile guidance law with T_max/m and tilt limits and
rocket-equation fuel use (Δt = 0.25 s) → predicted trajectory, touchdown point and fuel. Displayed as the
"predicted" path; MPC's own horizon is displayed separately.

## Mission supervisor (`touchdown_supervisor.py`)
PRE-LAUNCH → ENTRY (coast, RCS holds attitude) → DESCENT (engine lit at ignition AGL) → LANDING APPROACH
(≤ 700 m) → SITE ASSESSMENT (lidar in range, ≤ 450 m) → [DIVERSION | ABORT] → TOUCHDOWN → MISSION COMPLETE | FAILED.
Illegal transitions raise an error; every transition stores time and reason.
