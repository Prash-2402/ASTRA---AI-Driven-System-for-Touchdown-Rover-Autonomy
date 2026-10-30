# ASTRA Touchdown Control Architecture
## Cascade PID, Receding-Horizon MPC, and Terminal Guidance

### 1. Control Hierarchy
ASTRA Touchdown provides three swappable, physics-grounded guidance and control architectures:
1. **Cascade PID Controller:** Classical dual-loop feedback with anti-windup.
2. **Model Predictive Control (MPC):** Constrained receding-horizon optimization.
3. **Proximal Policy Optimization (PPO):** Continuous reinforcement learning policy trained on stochastic wind disturbances and mass variations.

---

### 2. Cascade PID Controller
The cascade controller decouples vehicle control into three physical loops:

#### Vertical Descent Loop
$$\Delta z = p_z - p_{z,\text{target}}$$
$$v_{z,\text{des}} = f(\Delta z) = \begin{cases} -25.0\,\text{m/s} & \Delta z > 500\,\text{m} \\ -12.0\,\text{m/s} & 100 < \Delta z \le 500\,\text{m} \\ -4.0\,\text{m/s} & 20 < \Delta z \le 100\,\text{m} \\ -1.5\,\text{m/s} & 2 < \Delta z \le 20\,\text{m} \\ -0.6\,\text{m/s} & \Delta z \le 2\,\text{m} \end{cases}$$

$$e_{vz} = v_{z,\text{des}} - v_z$$
$$F_{\text{demand}} = m g_{\text{mars}} + m \left( K_{p,vz} e_{vz} + K_{i,vz} \int e_{vz} dt + K_{d,vz} \dot{e}_{vz} \right)$$
$$u_{\text{throttle}} = \text{clip}\left(\frac{F_{\text{demand}} / \cos(\theta_{\text{tilt}})}{T_{\max}}, 0.15, 1.0\right)$$

#### Horizontal Translation Loop
$$e_x = x_{\text{target}} - x, \quad e_y = y_{\text{target}} - y$$
$$v_{x,\text{des}} = K_{p,xy} e_x, \quad v_{y,\text{des}} = K_{p,xy} e_y$$
$$\theta_{\text{pitch,des}} = -\frac{K_{p,vxy} (v_{x,\text{des}} - v_x)}{g_{\text{mars}}}, \quad \theta_{\text{roll,des}} = \frac{K_{p,vxy} (v_{y,\text{des}} - v_y)}{g_{\text{mars}}}$$

#### Attitude Loop
$$\boldsymbol{\tau}_{\text{rcs}} = -K_{p,\text{att}} (\boldsymbol{\theta} - \boldsymbol{\theta}_{\text{des}}) - K_{d,\text{att}} \boldsymbol{\omega}$$

---

### 3. Model Predictive Control (MPC)
The MPC controller solves a constrained finite-horizon optimal control problem at $10\,\text{Hz}$:

$$\min_{\mathbf{u}_0, \dots, \mathbf{u}_{N-1}} \sum_{k=0}^{N-1} \left( \|\mathbf{p}_k - \mathbf{p}_{\text{target}}\|_{\mathbf{Q}_p}^2 + \|\mathbf{v}_k - \mathbf{v}_{\text{ref},k}\|_{\mathbf{Q}_v}^2 + R_u (u_k - u_{\text{hover}})^2 \right) + \|\mathbf{p}_N - \mathbf{p}_{\text{target}}\|_{\mathbf{Q}_{fp}}^2 + \|\mathbf{v}_N - \mathbf{v}_{\text{target}}\|_{\mathbf{Q}_{fv}}^2$$

Subject to:
$$0.15 \le u_k \le 1.0 \quad (\text{Throttling limits})$$
$$|\theta_{\text{pitch},k}| \le 20^\circ, \quad |\theta_{\text{roll},k}| \le 20^\circ \quad (\text{Attitude tilt limits})$$
$$v_{z,N} \ge -2.0\,\text{m/s} \quad (\text{Touchdown velocity envelope})$$

Solved using Sequential Least Squares Quadratic Programming (SLSQP) with warm-starting across prediction steps.
