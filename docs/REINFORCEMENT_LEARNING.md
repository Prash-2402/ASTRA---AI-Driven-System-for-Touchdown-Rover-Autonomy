# ASTRA Reinforcement Learning
## Proximal Policy Optimization (PPO) for Planetary Touchdown Guidance

### 1. Motivation and Problem Formulation
While classical cascade PID and MPC handle predictable environments effectively, atmospheric perturbations (wind shear, dust gusts), actuator delays, and landing site diversions introduce complex multi-objective trade-offs.

ASTRA formulates terminal EDL as a continuous Markov Decision Process (MDP):

$$\mathcal{M} = \langle \mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma \rangle$$

- **Observation Space $\mathcal{S} \subset \mathbb{R}^{13}$:**
  Normalized states relative to target landing site:
  $$\mathbf{s} = \left[ \frac{\mathbf{p} - \mathbf{p}_{\text{target}}}{\mathbf{s}_p}, \frac{\mathbf{v}}{\mathbf{s}_v}, \boldsymbol{\theta}_{\text{euler}}, \frac{\boldsymbol{\omega}}{\mathbf{s}_\omega}, \frac{m_{\text{fuel}}}{m_{\text{fuel,init}}} \right]^T$$
- **Action Space $\mathcal{A} \subset \mathbb{R}^4$:**
  Continuous bounded control actions:
  $$\mathbf{a} = [u_{\text{throttle}}, \tau_{x,\text{norm}}, \tau_{y,\text{norm}}, \tau_{z,\text{norm}}]^T \in [0, 1] \times [-1, 1]^3$$
  Mapped to physical thrusters:
  $$T = u_{\text{throttle}} \cdot T_{\max}, \quad \boldsymbol{\tau}_{\text{rcs}} = \mathbf{a}_{1:3} \cdot \tau_{\text{rcs,max}}$$

---

### 2. Reward Function Architecture
The composite reward function prevents reward hacking and balances soft touchdown against fuel conservation:

$$\mathcal{R}(s, a) = r_{\text{progress}} + r_{\text{upright}} + r_{\text{fuel}} + r_{\text{terminal}}$$

1. **Progress Penalty:**
   $$r_{\text{progress}} = -0.05 \|\mathbf{p}_{\text{xy}} - \mathbf{p}_{\text{target,xy}}\| - 0.02 |v_z - v_{z,\text{target}}|$$
2. **Attitude Stability Penalty:**
   $$r_{\text{upright}} = -0.8 \|\boldsymbol{\theta}_{\text{tilt}}\|^2 - 0.1 \|\boldsymbol{\omega}\|^2$$
3. **Propellant Conservation Penalty:**
   $$r_{\text{fuel}} = -0.01 u_{\text{throttle}} - 0.005 \|\mathbf{a}_{1:3}\|_1$$
4. **Terminal Touchdown Reward / Penalty:**
   - If landed softly ($v_{\text{touch}} \le 2.0\,\text{m/s}$ and tilt $\le 5^\circ$):
     $$r_{\text{terminal}} = +100.0 - 10.0 \|\mathbf{p}_{\text{xy}} - \mathbf{p}_{\text{target,xy}}\|$$
   - If hard impact ($v_{\text{touch}} > 5.0\,\text{m/s}$):
     $$r_{\text{terminal}} = -80.0$$
   - If vehicle inverted or rollovers (tilt $> 30^\circ$):
     $$r_{\text{terminal}} = -100.0$$

---

### 3. PyTorch Policy Network Architecture
- **Actor (Policy):** Fully connected MLP with LayerNorm and Tanh activations:
  $$\mathbf{s} \in \mathbb{R}^{13} \longrightarrow [128] \longrightarrow [128] \longrightarrow \boldsymbol{\mu}(\mathbf{s}) \in \mathbb{R}^4, \quad \log \boldsymbol{\sigma} \in \mathbb{R}^4$$
- **Critic (Value Function):**
  $$\mathbf{s} \in \mathbb{R}^{13} \longrightarrow [128] \longrightarrow [128] \longrightarrow V(\mathbf{s}) \in \mathbb{R}$$
- **Clipping & Advantage:**
  $$L^{\text{CLIP}}(\theta) = \hat{\mathbb{E}}_t \left[ \min\left(r_t(\theta) \hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) \hat{A}_t\right) \right]$$
  with Generalized Advantage Estimation (GAE, $\lambda = 0.95, \gamma = 0.99$).
- **Live Training:** Exposed via `/api/touchdown/training/train_step` and visualizable in the RL Lab dashboard with real episode rewards, policy loss, and value loss.
