# Touchdown Physics

## Environment (Mars only)
| Parameter | Value | Source |
|---|---|---|
| Gravity g | 3.72076 m/s² | NASA GSFC Mars Fact Sheet (equatorial) |
| Mean radius | 3 389.5 km | NASA GSFC |
| Surface density ρ₀ | 0.020 kg/m³ | NASA GSFC (typical) |
| Scale height H | 11.1 km | NASA GSFC |
| Atmosphere | ρ(h) = ρ₀ exp(−h/H) | exponential model |
| Wind | mean vector + Ornstein–Uhlenbeck gusts (σ = 1.5 m/s, τ = 3 s) | configurable |

Local flat ENU frame (x East, y North, z Up). At < 10 km altitude the curvature error is < 0.02 %.

## State and equations (`simulation/touchdown/lander.py`)
State (14): p (3), v (3), q (4, body→world, scalar first), ω (3, body), m_fuel.

```
ṗ = v
v̇ = ( R(q)·F_body + F_aero + F_dist ) / m + [0, 0, −g]
q̇ = ½ q ⊗ [0, ω]
ω̇ = I⁻¹ ( τ − ω × Iω )
ṁ_fuel = −( |T_main| + |T_x| + |T_y| ) / (Isp g₀) − Σ|τ_i| / (r_rcs Isp g₀)
F_body = [u_x T_lat, u_y T_lat, u_th T_max]
F_aero = −½ ρ C_d A |v − w| (v − w)
I(m) = I_full · m / m_wet           (propellant at CoM — simplification)
```
Integrated with classical RK4 at Δt = 0.01 s; quaternion renormalised each step.

## Propulsion & actuators
| Parameter | Value |
|---|---|
| Dry / propellant mass | 1100 / 450 kg |
| Main engine T_max, Isp | 10 kN, 225 s (min throttle 15 % when lit) |
| Lateral thrusters | ±500 N per body axis |
| RCS torque limits | 700, 700, 350 N m |
| Actuator lags | throttle τ = 0.12 s, RCS τ = 0.05 s (exact first-order discretisation) |

The *achieved* actuator state (after lag and saturation) enters the dynamics; the engine produces no force
once propellant is exhausted.

## Terrain (`simulation/touchdown/terrain.py`)
2 km × 2 km at 4 m: fractal relief (FFT 1/f^1.9 noise), regional slope, parabolic craters with rims,
Pareto-distributed rock population (kept as discrete objects), optional hidden boulder field.

## Touchdown evaluation (truth)
Success requires |v_z| ≤ 2.5 m/s, v_h ≤ 1.2 m/s, tilt ≤ 10°, footprint slope ≤ 12°, no rock > 0.4 m under the
2.2 m footprint. No post-contact dynamics are simulated.

## Sensors (`simulation/touchdown/sensors.py`)
| Channel | Rate | Noise (1σ) | Other |
|---|---|---|---|
| IMU accel / gyro | 100 Hz | 0.03 m/s², 1.5 mrad/s | bias + random walk |
| Radar altimeter | 20 Hz | 0.6 m | 1 % dropout, < 6 km |
| Doppler velocimeter | 10 Hz | 0.12 m/s | 1 % dropout, < 4 km |
| TRN position | 2 Hz | 4, 4, 6 m | 0.1 s delay, 2 % dropout |
| Star tracker | 10 Hz | 2 mrad | — |
| Fuel gauge | 1 Hz | 1.5 kg | — |
Noise, bias, delay, rate, dropout and degradation are configurable per channel and injectable live.
