# ASTRA Platform Overview
## AI-Driven System for Touchdown & Rover Autonomy

### 1. Executive Summary
**ASTRA** (*AI-Driven System for Touchdown & Rover Autonomy*) is a unified planetary simulation, intelligence, digital twin, and scientific experimentation platform built for planetary exploration engineering.

ASTRA addresses the foundational challenges of autonomous space exploration:
- **Atmospheric Entry, Descent, and Landing (EDL):** High-uncertainty terminal descent, 6-DoF rigid-body lander dynamics under Mars atmospheric density profiles, real-time Extended Kalman Filtering, multi-controller guidance (Cascade PID, receding-horizon MPC, and Proximal Policy Optimization reinforcement learning), terrain hazard assessment, and autonomous site diversion.
- **Surface Rover Autonomy:** Multi-body kinematics of a 6-wheel rocker-bogie exploration rover, non-linear Pacejka-Coulomb wheel-soil tractive interactions, deterministic terrain generations across development and held-out testbeds, dynamic A* replanning, Pure Pursuit trajectory tracking, an independent safety supervisor, and rigorous matched-pair benchmarking against an industry-standard rule-based Finite State Machine (FSM) under four standardized fault classes.

---

### 2. Primary Engineering Principle
> **Every displayed simulation result must originate from an actual physical computation, and every autonomous decision must be traceable to the state and evidence that produced it.**

ASTRA rejects superficial 3D animations and mocked telemetry dashboards. All telemetry streams (position, velocity, quaternions, wheel slip, battery State of Charge, covariance ellipses) reflect numerical integrations executed at deterministic timesteps ($dt = 0.01\,\text{s}$ for Touchdown, $dt = 0.02\,\text{s}$ for Rover).

---

### 3. Unified Autonomy Workflow
Both autonomous agents share a unified engineering paradigm:

$$\text{Sense} \longrightarrow \text{Estimate} \longrightarrow \text{Predict} \longrightarrow \text{Decide} \longrightarrow \text{Act} \longrightarrow \text{Verify} \longrightarrow \text{Adapt}$$

1. **Sense:** Raw sensor measurements with physical bias, Gaussian white noise, quantization, sampling limits, and dropouts.
2. **Estimate:** Joseph-stabilized Extended Kalman Filter (EKF) propagating state estimations and covariance matrices $\mathbf{P}_k$.
3. **Predict:** Receding-horizon vehicle dynamic forward-projection over terrain and obstacle fields.
4. **Decide:** Optimal action selection balancing mission objectives, energy efficiency, and safety clearance.
5. **Act:** Translation into actuator commands (throttle, RCS torques, wheel drive torques, steering angles).
6. **Verify:** Discrepancy tracking between predicted and actual states via innovation analysis.
7. **Adapt:** Dynamic site diversion or path rerouting when hazards or subsystem faults exceed tolerance thresholds.

---

### 4. Dual Design Architecture
- **Experience A (Public WebGL Experience):** A cinematic Three.js landing page featuring a procedural 3D planetary globe with atmospheric Rayleigh scattering, cloud rotation, starfield, scroll-driven camera transformations, and technical module showcases.
- **Experience B (Internal Research Laboratory):** A sage-green and cream design system (`--background: #F5F4E9`, `--primary: #779477`, `--surface: #FFFEF7`) providing low eye strain for extended engineering analysis, real-time 3D viewports, telemetry time-series, batch experiment runners with 95% Wilson confidence intervals, and decision explainability audit logs.
