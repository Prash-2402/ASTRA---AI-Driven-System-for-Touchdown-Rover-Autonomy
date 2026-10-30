# ASTRA Rover Sensor Suite
## Physics-Grounded Sensing: IMU, Encoders, LiDAR Scanner, and BMS Telemetry

### 1. Sensor Overview & Stochastic Models
Every sensor measurement in ASTRA is subject to physical noise, bias drift, quantization, and potential dropouts.

---

### 2. Inertial Measurement Unit (IMU)
- **Tri-Axial Accelerometer:**
  $$\mathbf{a}_{\text{meas}} = \mathbf{a}_{\text{true}} + \mathbf{b}_{\text{accel}} + \boldsymbol{\eta}_{\text{accel}}$$
  where $\mathbf{b}_{\text{accel}} = [0.015, -0.010, 0.020]^T\,\text{m/s}^2$ (slowly drifting bias), $\sigma_{\text{accel}} = 0.05\,\text{m/s}^2$ (white noise).
- **Tri-Axial Gyroscope:**
  $$\boldsymbol{\omega}_{\text{meas}} = \boldsymbol{\omega}_{\text{true}} + \mathbf{b}_{\text{gyro}} + \boldsymbol{\eta}_{\text{gyro}}$$
  where $\sigma_{\text{gyro}} = 0.002\,\text{rad/s}$ ($\sim 0.11^\circ/\text{s}$).

---

### 3. Rotary Wheel Encoders
Six optical encoders measure rotational velocity of each wheel:

$$\omega_{\text{enc},i} = \omega_i + \eta_{\text{enc},i}, \quad \eta_{\text{enc},i} \sim \mathcal{N}(0, \sigma_{\text{enc}}^2), \quad \sigma_{\text{enc}} = 0.02\,\text{rad/s}$$

Wheel odometry forward speed:
$$v_{\text{odo}} = \frac{R}{6} \sum_{i=1}^6 \omega_{\text{enc},i}$$

Under wheel slip ($s_i > 0$), $v_{\text{odo}}$ overestimates actual forward speed, creating an odometry-inertial residual that is tracked by the EKF and fault classifier.

---

### 4. 360-Degree Radial LiDAR Scanner
- **Resolution:** 36 radial beams spaced at $10.0^\circ$ increments ($0^\circ$ to $350^\circ$).
- **Max Range:** $25.0\,\text{m}$.
- **Ray-Casting Contact:** Evaluates distance to all terrain obstacles within line-of-sight.
- **Range Noise:** Gaussian noise $\sigma_{\text{lidar}} = 0.08\,\text{m}$.
- **Fault Dropout:** Under FAULT 01, all range beams return empty/invalid readings.

---

### 5. Battery Management System (BMS)
- Monitored channels: Terminal voltage $V(t)$, discharge current $I(t)$, and estimated State of Charge $\text{SoC}(t)$.
- Current draw: $I(t) = P_{\text{total}}(t) / V(t) + \eta_{\text{bms}}$.
- Electrical power spikes ($P > 140.0\,\text{W}$) trigger immediate anomaly events.
