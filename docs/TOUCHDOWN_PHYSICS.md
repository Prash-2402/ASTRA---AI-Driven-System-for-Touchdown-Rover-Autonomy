# ASTRA Touchdown Physics
## 6-DoF Rigid-Body Dynamics, Mars Environment, Aerodynamics, and Propulsion

### 1. Planetary Environment Parameters
ASTRA Touchdown is configured for standard Mars atmospheric entry, descent, and landing (EDL):

| Parameter | Symbol | Nominal Value | Units | Reference |
| :--- | :--- | :--- | :--- | :--- |
| **Surface Gravity** | $g_{\text{mars}}$ | $3.71$ | $\text{m/s}^2$ | NASA Mars Fact Sheet |
| **Planetary Radius** | $R_{\text{mars}}$ | $3389.5 \times 10^3$ | $\text{m}$ | Volumetric mean radius |
| **Surface Atmospheric Density** | $\rho_0$ | $0.020$ | $\text{kg/m}^3$ | CO2-dominant atmosphere |
| **Atmospheric Scale Height** | $H$ | $11100.0$ | $\text{m}$ | Barometric scale height |
| **Surface Elevation Variance** | $\sigma_z$ | Fractal grid | $\text{m}$ | Harmonic craters & regional slopes |

The atmospheric density at altitude $z$ follows the barometric exponential profile:
$$\rho(z) = \rho_0 \exp\left(-\frac{z}{H}\right)$$

Wind velocity combines steady altitude-dependent boundary layers with stochastic turbulent gusts:
$$\mathbf{v}_{\text{wind}}(z) = \mathbf{v}_{\text{base}} \min\left(1.0, \max\left(0.1, \frac{z}{800}\right)\right) + \boldsymbol{\eta}_{\text{gust}}$$

---

### 2. 6-DoF Equations of Motion
The lander state is defined by 13 independent quantities:

$$\mathbf{x} = \left[\mathbf{p}^T, \mathbf{v}^T, \mathbf{q}^T, \boldsymbol{\omega}^T\right]^T \in \mathbb{R}^{13}$$

where:
- $\mathbf{p} = [p_x, p_y, p_z]^T$: World-frame position ($\text{m}$)
- $\mathbf{v} = [v_x, v_y, v_z]^T$: World-frame linear velocity ($\text{m/s}$)
- $\mathbf{q} = [q_w, q_x, q_y, q_z]^T$: Unit quaternion representing orientation from body to world frame
- $\boldsymbol{\omega} = [\omega_x, \omega_y, \omega_z]^T$: Body-frame angular velocity ($\text{rad/s}$)

#### Translational Dynamics
$$\dot{\mathbf{p}} = \mathbf{v}$$
$$m(t) \dot{\mathbf{v}} = \mathbf{F}_{\text{thrust}} + \mathbf{F}_{\text{aero}} + m(t) \mathbf{g}$$

where $\mathbf{g} = [0, 0, -g_{\text{mars}}]^T$.

#### Rotational Dynamics
$$\dot{\mathbf{q}} = \frac{1}{2} \boldsymbol{\Omega}(\boldsymbol{\omega}) \mathbf{q} = \frac{1}{2} \begin{bmatrix} 0 & -\omega_x & -\omega_y & -\omega_z \\ \omega_x & 0 & \omega_z & -\omega_y \\ \omega_y & -\omega_z & 0 & \omega_x \\ \omega_z & \omega_y & -\omega_x & 0 \end{bmatrix} \begin{bmatrix} q_w \\ q_x \\ q_y \\ q_z \end{bmatrix}$$

$$\mathbf{I} \dot{\boldsymbol{\omega}} + \boldsymbol{\omega} \times (\mathbf{I} \boldsymbol{\omega}) = \boldsymbol{\tau}_{\text{rcs}} + \boldsymbol{\tau}_{\text{gimbal}}$$

with vehicle inertia tensor $\mathbf{I} = \text{diag}(I_{xx}, I_{yy}, I_{zz})$.

---

### 3. Propulsion & Variable Mass Model
The variable vehicle mass $m(t) = m_{\text{dry}} + m_{\text{fuel}}(t)$ depletes continuously via propellant mass flow:

$$\dot{m}_{\text{fuel}} = -\left(\frac{T_{\text{main}}}{g_0 I_{\text{sp,main}}} + \frac{\|\mathbf{F}_{\text{rcs}}\|_1}{g_0 I_{\text{sp,rcs}}}\right)$$

- Main Thruster Throttle: $u \in [0.15, 1.0]$, max thrust $T_{\max} = 5500\,\text{N}$, $I_{\text{sp}} = 285\,\text{s}$.
- Reaction Control System (RCS): 8 bi-propellant cold/warm gas nozzles, torque authority $\pm 120\,\text{N}\cdot\text{m}$, $I_{\text{sp,rcs}} = 210\,\text{s}$.
- Numerical Integration: 4th-Order Runge-Kutta (RK4) evaluated at $100\,\text{Hz}$ ($dt = 0.01\,\text{s}$).
