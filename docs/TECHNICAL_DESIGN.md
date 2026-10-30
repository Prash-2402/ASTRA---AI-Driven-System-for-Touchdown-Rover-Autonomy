# ASTRA Technical Design Document
## Detailed Specifications, Mathematics, and Data Models

### 1. Architectural Scope and Component Layout
ASTRA is designed as an end-to-end scientific platform implementing high-fidelity planetary dynamics and verifiable autonomy.

The repository structure isolates responsibilities cleanly:
```
ASTRA/
├── backend/                  # FastAPI web services, WebSockets, DB models
│   ├── api/                  # REST endpoints: /api/platform, /api/touchdown, /api/rover, /api/experiments, /api/audit
│   ├── core/                 # Main application entry point & CORS
│   ├── database/             # SQLAlchemy ORM, engine, and CRUD helpers
│   ├── orchestration/        # Simulation lifecycle manager (SimManager)
│   └── telemetry/            # Non-blocking WebSocket broadcaster
├── simulation/               # Pure mathematical & physical simulation kernels
│   ├── touchdown/            # 6-DoF Mars lander, RK4, propulsion, sensors, hazards
│   └── rover/                # 6-wheel rocker-bogie, Pacejka slip, deterministic terrain
├── autonomy/                 # Perception, estimation, planning, and control
│   ├── estimation/           # Extended Kalman Filters (EKF) with Joseph updates
│   ├── control/              # Cascade PID, Receding-Horizon MPC, Pure Pursuit
│   ├── planning/             # Dynamic Traversability Costmap & A* search
│   ├── fault_detection/      # Anomaly detection & Bayesian fault classifier
│   ├── decision/             # Rule-based FSM baseline for matched benchmark
│   └── safety/               # Independent hard-constraint safety supervisors
├── machine_learning/         # Reinforcement learning pipelines
│   ├── environments/         # Gymnasium LanderEDLEnv wrapper
│   └── training/             # PyTorch Actor-Critic PPO policy & manager
├── experiments/              # Scientific experimentation & statistics
│   ├── analysis/             # Wilson score 95% CIs, Welch's t-test, Fisher test
│   └── runners/              # Matched paired trial batch runner
├── shared/                   # Pydantic schemas, enums, and WebSocket contracts
└── frontend/                 # Vite, React, TypeScript, Three.js, Zustand
```

---

### 2. State & Coordinate Reference Frames
All calculations in ASTRA adhere to standard aerospace and robotics coordinate conventions:
1. **World Frame (Inertial, NWU / ENU):**
   - $X$: East / Downrange
   - $Y$: North / Crossrange
   - $Z$: Up (Opposite to planetary gravity vector $\mathbf{g} = [0, 0, -g]^T$)
2. **Body Frame (Vehicle-Fixed):**
   - Origin at the vehicle Center of Mass (CoM).
   - Touchdown Lander: $+Z_B$ aligned with thrust vector (pointing out top/bottom), $+X_B, +Y_B$ in vehicle lateral plane.
   - Rover: $+X_B$ forward heading, $+Y_B$ lateral port, $+Z_B$ normal to chassis base plate.

---

### 3. Numerical Integration Engine
Both simulation cores use explicit, deterministic integrators. Touchdown uses 4th-Order Runge-Kutta (RK4):

$$\mathbf{k}_1 = f(t_n, \mathbf{y}_n)$$
$$\mathbf{k}_2 = f\left(t_n + \frac{\Delta t}{2}, \mathbf{y}_n + \frac{\Delta t}{2} \mathbf{k}_1\right)$$
$$\mathbf{k}_3 = f\left(t_n + \frac{\Delta t}{2}, \mathbf{y}_n + \frac{\Delta t}{2} \mathbf{k}_2\right)$$
$$\mathbf{k}_4 = f(t_n + \Delta t, \mathbf{y}_n + \Delta t \mathbf{k}_3)$$
$$\mathbf{y}_{n+1} = \mathbf{y}_n + \frac{\Delta t}{6} (\mathbf{k}_1 + 2\mathbf{k}_2 + 2\mathbf{k}_3 + \mathbf{k}_4)$$

RK4 eliminates numerical energy drift during rapid attitude slew maneuvers and terminal thrust throttling.
