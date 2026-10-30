# ASTRA Landing Hazard Assessment
## Real-Time Optical and Radar Terrain Safety Evaluation

### 1. Hazard Detection Scope
During terminal descent, the designated primary landing site may be compromised by:
- Steep surface slopes exceeding lander leg tip-over limits ($\theta_{\text{slope}} > 8.0^\circ$).
- Impact craters with elevated rims and steep central depressions.
- Boulder fields producing excessive local surface roughness ($R_a > 0.15\,\text{m}$).

ASTRA implements an autonomous surface hazard evaluation pipeline operating at $10\,\text{Hz}$ between $500\,\text{m}$ and $50\,\text{m}$ altitude.

---

### 2. Terrain Slope & Surface Normal Computation
Given local terrain elevation $z = f(x, y)$, surface gradients are evaluated via finite differences:

$$g_x = \frac{\partial z}{\partial x} \approx \frac{f(x + \Delta x, y) - f(x - \Delta x, y)}{2 \Delta x}$$
$$g_y = \frac{\partial z}{\partial y} \approx \frac{f(x, y + \Delta y) - f(x, y - \Delta y)}{2 \Delta y}$$

The unnormalized surface normal vector:
$$\mathbf{n} = \begin{bmatrix} -g_x \\ -g_y \\ 1 \end{bmatrix}, \quad \hat{\mathbf{n}} = \frac{\mathbf{n}}{\|\mathbf{n}\|}$$

The terrain slope angle relative to the local horizontal plane:
$$\theta_{\text{slope}} = \arccos(\hat{n}_z) = \arctan\left(\sqrt{g_x^2 + g_y^2}\right)$$

---

### 3. Hazard Cost Function
Each candidate site is assigned a composite hazard cost:

$$J_{\text{hazard}} = w_{\text{slope}} \max(0, \theta_{\text{slope}} - \theta_{\text{allow}}) + w_{\text{rough}} R_a + \sum_{i=1}^{N_{\text{craters}}} C_i \exp\left(-\frac{\|\mathbf{p}_{\text{site}} - \mathbf{p}_{\text{crater},i}\|^2}{2 r_{\text{crater},i}^2}\right)$$

A candidate is marked impassable/unreachable if:
$$\theta_{\text{slope}} > 8.0^\circ \quad \text{or} \quad J_{\text{hazard}} > 0.70$$
