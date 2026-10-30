# ASTRA Extended Kalman Filter (EKF) Model
## 9-State Touchdown & 7-State Rover Non-Linear State Estimation

### 1. Mathematical Foundations
Both the Touchdown lander and Rover systems use Extended Kalman Filtering (EKF) to estimate full pose and velocities from noisy, biased, and delayed sensors.

To prevent numerical covariance divergence caused by finite-precision floating-point arithmetic, ASTRA implements the **Joseph Stabilized Covariance Update Formulation**:

$$\mathbf{P}_k = (\mathbf{I} - \mathbf{K}_k \mathbf{H}_k) \mathbf{P}_k^- (\mathbf{I} - \mathbf{K}_k \mathbf{H}_k)^T + \mathbf{K}_k \mathbf{R}_k \mathbf{K}_k^T$$

This guarantees that $\mathbf{P}_k$ remains strictly symmetric and positive semi-definite for all $k \ge 0$.

---

### 2. Module 1: Touchdown EKF (9 States)
#### State Vector
$$\mathbf{x}_{\text{edl}} = [p_x, p_y, p_z, v_x, v_y, v_z, \phi, \theta, \psi]^T \in \mathbb{R}^9$$
where $[\phi, \theta, \psi]$ are Roll, Pitch, and Yaw Euler angles.

#### Non-Linear Transition Model $\mathbf{f}(\mathbf{x}, \mathbf{u})$
$$\dot{\mathbf{p}} = \mathbf{v}$$
$$\dot{\mathbf{v}} = \mathbf{R}(\boldsymbol{\theta}) \mathbf{a}_{\text{imu}} + \begin{bmatrix} 0 \\ 0 \\ -g_{\text{mars}} \end{bmatrix}$$
$$\dot{\boldsymbol{\theta}} = \mathbf{T}(\boldsymbol{\theta}) \boldsymbol{\omega}_{\text{imu}}$$

where $\mathbf{R}(\boldsymbol{\theta})$ is the direction cosine rotation matrix and $\mathbf{T}(\boldsymbol{\theta})$ is the kinematic matrix relating body rates to Euler angle rates:

$$\mathbf{T}(\phi, \theta) = \begin{bmatrix} 1 & \sin\phi \tan\theta & \cos\phi \tan\theta \\ 0 & \cos\phi & -\sin\phi \\ 0 & \sin\phi \sec\theta & \cos\phi \sec\theta \end{bmatrix}$$

#### Measurement Vector $\mathbf{z}_{\text{edl}} \in \mathbb{R}^6$
$$\mathbf{z} = [z_{\text{altimeter}}, v_{x,\text{radar}}, v_{y,\text{radar}}, v_{z,\text{radar}}, p_{x,\text{radar}}, p_{y,\text{radar}}]^T$$

Innovation vector:
$$\tilde{\mathbf{y}}_k = \mathbf{z}_k - \mathbf{h}(\mathbf{x}_k^-)$$

---

### 3. Module 2: Rover EKF (7 States)
#### State Vector
$$\mathbf{x}_{\text{rov}} = [p_x, p_y, p_z, v_x, v_y, \psi_{\text{heading}}, \omega_z]^T \in \mathbb{R}^7$$

#### Kinematic Transition Model
$$\begin{aligned}
p_{x,k+1} &= p_{x,k} + (v_{x,k} \cos\psi_k - v_{y,k} \sin\psi_k) \Delta t \\
p_{y,k+1} &= p_{y,k} + (v_{x,k} \sin\psi_k + v_{y,k} \cos\psi_k) \Delta t \\
p_{z,k+1} &= f_{\text{terrain}}(p_{x,k}, p_{y,k}) \\
v_{x,k+1} &= v_{x,k} + a_{x,\text{imu}} \Delta t \\
v_{y,k+1} &= v_{y,k} + a_{y,\text{imu}} \Delta t \\
\psi_{k+1} &= \psi_k + \omega_{z,\text{imu}} \Delta t \\
\omega_{z,k+1} &= \omega_{z,\text{imu}}
\end{aligned}$$

#### Measurements
- Wheel Odometry speed $v_{\text{odo}} = \frac{R}{6} \sum_{i=1}^6 \omega_i$
- Gyroscope yaw rate $\omega_{\text{gyro}}$
- Optical / Beacon position fixes $[p_{x,\text{opt}}, p_{y,\text{opt}}]$

---

### 4. Innovation Tracking & Fault Residuals
Innovations $\tilde{\mathbf{y}}_k$ are tracked in a circular buffer. The normalized innovation squared (NIS):

$$\epsilon_k = \tilde{\mathbf{y}}_k^T \mathbf{S}_k^{-1} \tilde{\mathbf{y}}_k$$

where $\mathbf{S}_k = \mathbf{H}_k \mathbf{P}_k^- \mathbf{H}_k^T + \mathbf{R}_k$ is the innovation covariance.

When $\epsilon_k > \chi^2_{m, 1-\alpha}$, an anomaly event is raised.
**Crucially, in ASTRA an EKF residual is evidence of model mismatch, not automatic proof of a specific fault.** The Bayesian classifier cross-references EKF residuals with battery telemetry, wheel slip, and sensor validity before asserting a fault type.
