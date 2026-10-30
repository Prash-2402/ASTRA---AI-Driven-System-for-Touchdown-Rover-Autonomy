# ASTRA Rover Physics Engine
## Multi-Body Dynamics, Rocker-Bogie Kinematics, Pacejka Slip, and Battery Model

### 1. Rocker-Bogie Mechanical Architecture
The ASTRA planetary rover features a 6-wheel articulated rocker-bogie passive suspension modeled on flight-proven Mars exploration rovers (Curiosity, Perseverance).

```
          [ Differential Pivot ]
               /            \
       [ Left Rocker ]   [ Right Rocker ]
         /         \       /          \
  (Rear Wheel)   [Bogie] (Rear Wheel) [Bogie]
                 /     \              /     \
             (Front)  (Mid)       (Front)  (Mid)
```

The differential pivot mechanism links the left and right rockers such that:

$$\theta_{\text{rocker,L}} + \theta_{\text{rocker,R}} = 2 \theta_{\text{chassis,pitch}}$$

The differential transmits pitch rotations between rockers while isolating the main chassis from extreme terrain tilt, equalizing normal ground loads across all six wheels.

---

### 2. Multi-Body Wheel Load Distribution
Under Mars gravity ($g_{\text{mars}} = 3.71\,\text{m/s}^2$) and total rover mass $m = 185.0\,\text{kg}$, the nominal static normal force per wheel on level ground is:

$$F_{N,0} = \frac{m g_{\text{mars}}}{6} \approx 114.4\,\text{N}$$

On 3D sloped terrain with chassis pitch $\theta$ and roll $\phi$:
- Gravitational load shift along pitch axis adjusts front-to-rear distribution.
- Gravitational load shift along roll axis adjusts port-to-starboard distribution.
- Rocker-bogie articulation angles dynamically shift wheel ground contact points $[x_i, y_i, z_i]$.

---

### 3. Non-Linear Pacejka-Coulomb Tractive Contact Mechanics
Regolith tractive forces are modeled using the non-linear Pacejka Magic Formula:

#### Longitudinal Wheel Slip Ratio
$$s_i = \frac{\omega_i R - v_i}{\max(|\omega_i R|, |v_i|, 10^{-4})}$$

where $\omega_i$ is wheel rotational velocity, $R = 0.25\,\text{m}$ is wheel radius, and $v_i$ is local linear velocity.

#### Tractive Force
$$F_{x,i} = \mu_0 F_{N,i} \tanh(5.5 s_i)$$

where $\mu_0 = 0.72$ is Mars regolith coefficient of friction.

#### Rolling Resistance Force
$$F_{\text{rr},i} = C_{\text{rr}} F_{N,i} \text{sgn}(v_i)$$

where $C_{\text{rr}} = 0.035$ on Martian soil.

#### Rotational Acceleration per Wheel
$$I_{\text{wheel}} \dot{\omega}_i = \tau_{\text{motor},i} - F_{x,i} R$$

---

### 4. Electrochemical Battery & Power Model
- **Nominal Capacity:** $600\,\text{Wh}$ ($28.0\,\text{V}$ nominal bus).
- **Power Consumption:**
  $$P_{\text{total}} = \left( P_{\text{avionics}} + \sum_{i=1}^6 \frac{|\tau_i \omega_i|}{\eta_{\text{motor}}} \right) \cdot \kappa_{\text{fault3}}$$
  where $P_{\text{avionics}} = 35.0\,\text{W}$, $\eta_{\text{motor}} = 0.82$, and $\kappa_{\text{fault3}} = 2.8$ during power surge.
- **Voltage Sag:**
  $$V(t) = V_{\text{nom}} (0.85 + 0.15 \text{SoC}) - I R_{\text{internal}}$$
- **State of Charge (SoC):**
  $$\text{SoC}(t) = \frac{E(t)}{E_{\max}} \in [0.0, 1.0]$$
