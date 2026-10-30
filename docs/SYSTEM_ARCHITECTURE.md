# ASTRA System Architecture
## Comprehensive Architectural Blueprint

### 1. Architectural Philosophy
ASTRA is constructed as an authoritative modular monolith with decoupled real-time simulation engines, numerical physics evaluators, intelligent autonomy controllers, persistent database models, and dual frontends.

The core architectural invariant is:
**The frontend never owns the authoritative simulation state.**

```
+-----------------------------------------------------------------------------------+
|                                 USER INTERFACES                                   |
|  +-------------------------------------+   +------------------------------------+ |
|  | Experience A: Public Landing Page   |   | Experience B: Sage-Green & Cream   | |
|  | - Procedural 3D WebGL Globe         |   |   Internal Research Lab            | |
|  | - Cinematic Rayleigh Atmosphere     |   | - 3D Lander & Rover Viewports      | |
|  | - Scroll-driven Camera Journeys     |   | - Real-time Telemetry & Time Series| |
|  | - Product Capability Showcases      |   | - Matched-Trial Experiment Engine  | |
|  +-------------------------------------+   +------------------------------------+ |
+------------------------------------------^----------------------------------------+
                                           | HTTP REST / WebSocket JSON Frames
+------------------------------------------v----------------------------------------+
|                                BACKEND APPLICATION                                |
|  +------------------------------------------------------------------------------+ |
|  | FastAPI Gateway & WebSocket Broadcaster (/api/*, /ws)                        | |
|  +------------------------------------------------------------------------------+ |
|  | Simulation Lifecycle Orchestration (SimManager)                              | |
|  +-------------------------------------+   +------------------------------------+ |
|  | Module 1: ASTRA TOUCHDOWN           |   | Module 2: ASTRA ROVER              | |
|  | - 6-DoF Rigid-Body Lander Dynamics  |   | - 6-Wheel Rocker-Bogie Multi-Body  | |
|  | - Mars Atmosphere & Wind Model      |   | - Non-linear Pacejka-Coulomb Slip  | |
|  | - Propulsion (Thrust & RCS Torques) |   | - Deterministic Terrain Suite (1-5)| |
|  | - Sensor Suite (IMU, Doppler, Altim)|   | - Sensor Suite (IMU, LiDAR, BMS)   | |
|  | - 9-State Joseph-Stabilized EKF     |   | - 7-State Joseph-Stabilized EKF    | |
|  | - Guidance: Cascade PID / MPC / PPO |   | - 4 Benchmark Fault Injectors      | |
|  | - Hazard Detection & Diversion      |   | - Dynamic A* Costmap Replanning    | |
|  | - 10-State EDL Mission Supervisor   |   | - Pure Pursuit & Independent Safety| |
|  |                                     |   | - Rule-Based FSM Baseline          | |
|  +-------------------------------------+   +------------------------------------+ |
|  | Shared Experimentation Engine: Matched Trials, Wilson 95% CI, Welch's t-test | |
|  | Decision Explainability Logger: Traceable JSON Audit Events                 | |
|  +------------------------------------------------------------------------------+ |
|  | SQLAlchemy ORM & SQLite / PostgreSQL Persistence Data Access Layer           | |
+-----------------------------------------------------------------------------------+
```

---

### 2. Frequency Decoupling
To guarantee numerical stability while preserving interactive 60 FPS graphics, ASTRA enforces strict frequency decoupling across the execution loops:

| Domain | Frequency | Execution Context | Responsibility |
| :--- | :--- | :--- | :--- |
| **Lander Physics** | $100\,\text{Hz}$ ($dt = 0.01\,\text{s}$) | Synchronous RK4 Integrator | 6-DoF equations of motion, mass depletion, aerodynamics |
| **Rover Physics** | $50\,\text{Hz}$ ($dt = 0.02\,\text{s}$) | Euler/Symplectic Integrator | Wheel torque balance, normal load distribution, Pacejka slip |
| **Sensor Simulation** | $50\,\text{Hz}$ ($dt = 0.02\,\text{s}$) | Background Thread / Step Loop | IMU bias drift, altimeter beam tilt dropout, encoder noise |
| **EKF Estimation** | $50\,\text{Hz}$ ($dt = 0.02\,\text{s}$) | Autonomy Pipeline | Joseph-stabilized covariance propagation and Kalman updates |
| **Motion Controllers** | $10 - 25\,\text{Hz}$ | Guidance Loop | PID / Pure Pursuit / MPC receding-horizon quadratic program |
| **High-Level Planning** | $1 - 5\,\text{Hz}$ | Asynchronous Autonomy | Dynamic A* costmap updates, landing diversion feasibility |
| **WebSocket Telemetry** | $15 - 20\,\text{Hz}$ | Non-blocking Async Queue | Throttled JSON broadcast over `/ws` to prevent socket saturation |
| **Frontend Render** | $60\,\text{Hz}$ | WebGL Three.js RequestAnimationFrame | Smooth visual slerp/lerp interpolation of authoritative states |

---

### 3. State Authority & Synchronization
1. **Authoritative Ground Truth:** Maintained exclusively by `LanderSimulationOrchestrator` and `RoverSimulationOrchestrator`.
2. **Perceived State:** Autonomy modules receive only corrupted sensor measurements and EKF estimates. Ground-truth state and hidden hazards are never leaked to guidance controllers.
3. **Telemetry Streaming:** The backend broadcasts structured JSON contracts (`TouchdownTelemetryFrame` and `RoverTelemetryFrame`) containing both ground truth and estimation error vectors, enabling the UI to plot estimation error and $3\sigma$ covariance bounds side by side.
