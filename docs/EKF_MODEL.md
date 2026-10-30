# Extended Kalman Filters

Both filters keep **estimate** and **covariance** separate from ground truth; the UI plots actual error
against ±2σ. Covariance describes the filter's belief — it is not evidence of accuracy.

## Lander EKF (`autonomy/estimation/lander_ekf.py`)
State x (12) = [p, v, θ (roll, pitch, yaw), b_a (accelerometer bias)]. Inputs: accelerometer f_b, gyro ω_b.
```
p⁺ = p + v Δt
v⁺ = v + (R(θ)(f_b − b_a) + g) Δt
θ⁺ = θ + E(θ) ω_b Δt            (ZYX Euler kinematics, |cos pitch| floored at 1e-3)
b_a⁺ = b_a
F = ∂f/∂x : identity blocks analytic; ∂(R a)/∂θ and ∂(E ω)/∂θ by central differences (ε = 1e-6)
Q: position ½σ_a Δt², velocity σ_a²Δt, attitude σ_g²Δt, bias σ_b²Δt
```
Measurements: TRN position (H = [I 0 0 0]), Doppler velocity, star-tracker attitude (angle-wrapped
innovation), altimeter h(x) = p_z − DEM(p_x, p_y) with H = [−∂DEM/∂x, −∂DEM/∂y, 1, 0…] using the onboard
orbital DEM (not true terrain). σ_alt = 1 m + 0.2 % range.

Safeguards: χ² gating (99.9 %: 10.83 for 1 dof, 16.27 for 3 dof), Joseph-form update, symmetrisation,
eigenvalue floor 1e-10. Innovation, S and NIS are recorded per sensor.

## Rover EKF (`autonomy/estimation/rover_ekf.py`)
State (8) = [x, y, z, v, ψ, ω, roll, pitch].
```
x⁺ = x + v cosψ cosθ Δt,  y⁺ = y + v sinψ cosθ Δt,  z⁺ = z − v sinθ Δt,  ψ⁺ = ψ + ωΔt
```
Analytic Jacobian. Measurements: wheel odometry v (σ = 0.03 + (0.15 + 0.8·slip)|v| — slip-aware), gyro yaw rate,
IMU roll/pitch, visual localisation [x, y, z, ψ] at 1 Hz (gate 30).
**Relocalisation:** three consecutive gated-out fixes are treated as filter divergence (over-confident P):
position/heading variance is inflated by the squared innovation and the fix is re-applied. This was added after
observing slip-induced divergence (σ = 0.06 m with 1.08 m true error) during development.
