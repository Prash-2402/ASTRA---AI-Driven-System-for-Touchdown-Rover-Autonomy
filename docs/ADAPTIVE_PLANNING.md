# ASTRA Adaptive Planning & Dynamic Replanning
## Costmap Inflation, A* Graph Search, and Uncertainty-Aware Rerouting

### 1. Dynamic Traversability Costmap
ASTRA maintains an authoritative $100 \times 100$ discrete costmap grid ($1.0\,\text{m}$ resolution) in `DynamicTraversabilityCostmap`.

The cost of traversing cell $(i, j)$ is dynamically modulated:

$$c(i, j) = c_{\text{base}} + w_{\text{slope}} \cdot g(\theta_{\text{slope}}) + w_{\text{obstacle}} \cdot \exp\left(-\frac{d_{\text{obs}}^2}{2 \sigma_{\text{safety}}^2}\right) + w_{\text{actuator}} \cdot \Delta_{\text{degraded}}$$

#### Inflation Under Estimation Uncertainty
When EKF position covariance increases (e.g. during sensor dropout):

$$\sigma_{\text{safety}} = \sigma_0 + 3.0 \sqrt{\text{Tr}(\mathbf{P}_{xy})}$$

Obstacle collision envelopes dilate automatically, forcing the planner to select wider corridors and avoid tight boulder passes.

---

### 2. A* Graph Search & Path Smoothing
Path search operates on an 8-connected grid with admissible Euclidean heuristic:

$$h(n) = \sqrt{(x_n - x_{\text{goal}})^2 + (y_n - y_{\text{goal}})^2}$$

Edge weights include diagonal motion penalties ($\sqrt{2}$) and cell traversability costs:
$$g(n) = g(\text{parent}) + \text{dist}(\text{parent}, n) \cdot \frac{c(\text{parent}) + c(n)}{2}$$

#### Path Smoothing
Collinear and line-of-sight waypoints are pruned via Bresenham ray-casting, generating smooth, dynamically feasible trajectories for the Pure Pursuit motion controller.

---

### 3. Fault-Triggered Dynamic Replanning
When the Bayesian fault classifier detects a confirmed subsystem fault:
1. **Actuator Loss (Fault 04):** Maximum allowable slope threshold is reduced from $18^\circ$ to $8^\circ$. Steep cells become impassable ($\text{cost} = \infty$).
2. **Power Surge (Fault 03):** Edge distance weights are increased relative to slope costs, prioritizing direct paths to the target to conserve remaining Watt-hours.
3. **Sensor Dropout (Fault 01):** Uncertainty dilation inflates obstacle boundaries by $+1.5\,\text{m}$.
4. A* recomputes a revised collision-free path starting from current EKF coordinates $[x_k, y_k]$.
