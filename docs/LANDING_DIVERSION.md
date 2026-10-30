# ASTRA Autonomous Landing Site Diversion
## Kinetic Footprint, Tsiolkovsky Delta-V Estimation, and Trajectory Retargeting

### 1. Diversion Triggering Protocol
Autonomous diversion occurs when:
1. Lander descends into the perception altitude window ($100\,\text{m} \le z \le 350\,\text{m}$).
2. Surface sensors detect that the primary target hazard score $J_{\text{hazard}} > 0.50$ or slope exceeds $6.0^\circ$.
3. The supervisor transitions mission phase to `DIVERSION` and invokes `DiversionEngine.check_and_execute_diversion()`.

**Critical Safety Invariant:** A diversion must respect physical thrust limitations, attitude slew rates, and remaining propellant mass. Under no circumstances is the lander teleported or guided along unfeasible trajectories.

---

### 2. Reachable Kinetic Footprint & Propellant Consumption
To divert to candidate site $(x_c, y_c)$ located at horizontal distance $d = \|\mathbf{p}_{\text{cand,xy}} - \mathbf{p}_{\text{lander,xy}}\|$:

#### Available Time to Touchdown
$$t_{\text{descent}} \approx \frac{z - z_{\text{cand}}}{\max(1.0, |v_z|)}$$

#### Required Lateral Velocity and Acceleration
$$a_{\text{lateral,req}} = \frac{2 d}{t_{\text{descent}}^2}, \quad v_{\text{lateral,req}} = \frac{d}{\max(5.0, t_{\text{descent}})}$$
$$\Delta v_{\text{diversion}} = v_{\text{lateral,req}} + \Delta v_{\text{margin}} \quad (\Delta v_{\text{margin}} = 2.5\,\text{m/s})$$

#### Tsiolkovsky Propellant Requirement
$$\Delta m_{\text{fuel}} = m(t) \left( 1 - \exp\left(-\frac{\Delta v_{\text{diversion}}}{g_0 I_{\text{sp}}}\right) \right)$$

---

### 3. Candidate Ranking & Selection
Candidates within the reachable footprint are ranked via the multi-objective feasibility cost:

$$J_{\text{feasibility}} = 1.8 \theta_{\text{slope}} + 15.0 R_a + 0.08 d + 0.5 \Delta m_{\text{fuel}}$$

Subject to:
$$m_{\text{fuel,remain}} \ge \Delta m_{\text{fuel}} + m_{\text{reserve}} \quad (m_{\text{reserve}} = 20.0\,\text{kg})$$
$$\theta_{\text{slope}} \le 8.0^\circ$$
$$J_{\text{hazard}} < 0.70$$

If all candidate sites are infeasible, the lander executes a conservative vertical descent abort maneuver into the lowest slope region identified.
