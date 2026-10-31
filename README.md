# ASTRA — AI-Driven System for Touchdown & Rover Autonomy

ASTRA is a research-grade autonomy platform for planetary landing and surface mobility, designed to study how intelligent decision-making can remain safe, interpretable, and statistically defensible under uncertainty and injected faults. The repository combines high-fidelity simulation, state estimation, planning, control, fault detection, and experimental evaluation into a single framework for autonomous planetary systems.

The system is organized around two independent physics domains and one shared mission-intelligence layer:

- ASTRA TOUCHDOWN: autonomous Mars landing with 6-DOF descent dynamics, hazard-aware landing-site selection, and fault-tolerant guidance.
- ASTRA ROVER: planetary rover autonomy under sensor drift, terrain misclassification, power loss, and actuator degradation.
- ASTRA MOON: a separate lunar landing stack using Apollo-inspired guidance and lunar-specific terrain and dust effects.

This repository is not a toy demonstration. It is built as a research platform for comparative autonomy studies, reproducible experiments, and decision-auditability.

## Why ASTRA matters

Autonomous planetary missions are constrained by three difficult realities:

1. Sensors are imperfect and can drift, fail, or disagree with one another.
2. Terrain and environment models are uncertain and can change unexpectedly.
3. Safety must be preserved even when the controller is operating near the edge of feasible behavior.

ASTRA addresses these challenges by combining:

- model-based state estimation (EKF)
- terrain-aware traversability modeling
- fault-specific response logic
- independent safety supervision
- matched-seed experimentation and statistical evaluation
- audit trails for autonomous decisions and recoveries

The result is a platform for evaluating whether adaptive, uncertainty-aware autonomy improves mission robustness compared with a fixed baseline under realistic failure conditions.

## Core technical contributions

### 1) Unified autonomy framework

The project defines a unified mission-intelligence interface shared across both mission types, implemented in the `autonomy` stack. This abstraction separates:

- state observation and sensor health monitoring
- prediction and world modeling
- decision-making and response selection
- safety supervision and constraint enforcement
- audit logging and experimental traceability

This matters because planetary autonomy is not a single planner or single controller. It is a coordinated stack of perception, estimation, planning, control, safety, and diagnostics.

### 2) Fault-aware rover autonomy

The rover subsystem is designed around a realistic fault taxonomy and uncertainty-aware response logic. Instead of assuming all faults are equally probable or equally harmful, the system explicitly detects and classifies failure modes, then changes behavior accordingly.

It specifically models four injected fault classes:

- sensor dropout
- terrain misclassification
- power drain
- actuator degradation

Each fault is introduced in simulation without directly informing the autonomy stack, preserving realism and preventing shortcutting.

### 3) Adaptive replanning with safety-aware decision loops

ASTRA does not rely on a single fixed route or static policy. It re-evaluates the plan under changing conditions, especially when:

- route feasibility changes due to new obstacles
- sensor confidence drops
- faults are detected or classified
- energy feasibility is compromised
- safety margins are violated

The rover planning layer uses traversability-aware cost maps, A* route generation, path smoothing, and energy constraints to produce routes that balance progress and safety. This is paired with a separate safety supervisor that can override the planner when the mission enters an unsafe condition.

### 4) Independent safety supervision

ASTRA implements an independent safety layer rather than making safety a subroutine of the planner. This is an important research and systems-design principle: the planner tries to achieve mission goals, but the supervisor ensures the system remains within physical and operational constraints.

This includes checks for:

- obstacle proximity and geofence violations
- slope and tilt constraints
- battery reserve limits
- route feasibility under degraded conditions
- halt or replan when a requested action is unsafe

The architecture intentionally separates performance logic from safety logic, which is critical in autonomy research and realistic mission design.

### 5) Research-grade experimental methodology

ASTRA is built for statistically meaningful evaluation. Experimental protocol includes:

- matched-seed trials to ensure identical terrain, initial conditions, and injected fault placement across controllers
- development and held-out terrain splits
- controlled fault injection times
- reproducible configuration and logging
- paired comparative analysis against an FSM baseline

This design reduces bias and enables fair comparison between adaptive autonomy and rule-based response strategies.

### 6) Novelty: uncertainty-aware autonomy under sensor deception

A key novelty in this project is the treatment of the sensor itself as a possible source of mission degradation. The repo explicitly addresses the challenge of a sensor that appears valid but produces systematically misleading information.

This is captured in the project’s “Hurdle: The Sensor That Lies” theme, which includes:

- two-sided CUSUM innovation monitoring for creeping sensor bias detection
- EKF-based sensor isolation when a measurement stream becomes inconsistent
- out-of-distribution (OOD) policy guarding for learned control policies
- fallback to conservative or classification-driven recovery behavior when the sensor stack becomes untrustworthy

This is a critical advancement over systems that assume sensor health is binary or that all failures are abrupt. In real missions, the most dangerous faults are often gradual, subtle, and statistically deceptive.

## System architecture

The repository uses a modular monolith architecture with a Python backend serving the simulation engine and a React front end for interaction and visualization.

```text
frontend (React / TypeScript / Vite)
    ├─ landing page (Three.js)
    ├─ mission UI (R3F, Recharts, Zustand)
    └─ REST / WebSocket interface
            │
            ▼
backend (FastAPI + SQLAlchemy + Alembic)
    ├─ API layer and schemas
    ├─ orchestration and simulation sessions
    ├─ telemetry and event bus
    ├─ database persistence
    └─ reporting and debrief generation
            │
            ▼
simulation/
    ├─ touchdown physics
    └─ rover physics
            │
            ▼
autonomy/
    ├─ estimation
    ├─ planning
    ├─ control
    ├─ fault detection
    ├─ decision logic
    ├─ safety supervision
    └─ decision auditing
            │
            ▼
machine_learning/
    ├─ Gymnasium environment
    ├─ PPO trainer
    └─ policy checkpoint registry
```

The backend is authoritative for simulation; the frontend renders snapshots and telemetry rather than integrating the physical dynamics itself. This preserves correctness and keeps the simulator as the source of truth.

## Core modules and techniques

### Touchdown autonomy

ASTRA TOUCHDOWN models a powered descent problem for a Mars lander using a custom 6-degree-of-freedom rigid-body simulator. The system combines:

- nonlinear dynamics and numerical propagation (RK4)
- sensor suite modeling
- filter-based state estimation
- landing hazard assessment
- local landing target selection
- constrained guidance and control
- autonomous diversion around unsafe terrain

The landing pipeline considers not just trajectory tracking, but also landing-site feasibility and hazard avoidance. That allows the system to evaluate whether the final touchdown point is reachable and safe, rather than merely following a nominal descent profile.

### Rover perception and estimation

The rover uses a layered state-estimation and perception stack to interpret the world under noise and uncertainty. This includes:

- IMU and odometry inputs
- lidar and camera perception
- visual localization / visloc signals
- traversability classification from terrain cells
- covariance-aware state estimation via EKF
- uncertainty propagation tied to route planning

This design recognizes that navigation performance depends not only on perception quality, but on how uncertainty enters the planner and controller.

### Traversability and planning

The rover planning system evaluates a grid-based map where cells are categorized by traversability and cost. Hard constraints represent impassable or unsafe terrain, while soft costs model the marginal discomfort or risk associated with each path segment.

Key planning details include:

- 8-connected route planning using A*
- cost map with obstacles, slope limits, terrain class penalties, uncertainty penalties, and energy penalties
- path smoothing via collision-aware shortcutting
- replan triggers based on new hazards, safety events, or fault-driven changes
- energy-aware route selection under battery constraints

This ensures route selection is not only shortest-path but also safe, stochastically aware, and mission-feasible.

### Motion control

ASTRA uses a motion controller that blends trajectory tracking with dynamics-aware wheel behavior. In the rover stack, this includes:

- pure pursuit guidance
- curvature-limited path following
- skid-steer kinematics
- traction control under slip conditions
- gentle-turn responses when controller confidence or terrain quality degrades

This is useful because terrain and fault conditions can make aggressive path following unsafe or inefficient. The control behavior adapts to the mission context instead of assuming fixed vehicle responses.

### Fault detection and classification

The system separates detection from decision-making. A detector identifies abnormalities in sensor and actuator behavior; a classifier scores the likelihood of specific failure modes; and a debouncer prevents noisy switching.

This allows the pipeline to distinguish among:

- stray sensor noise
- persistent measurement degradation
- environment-induced misclassification
- power system issues
- physical actuator degradation

This is a major strength of the project: the stack does not behave as if every anomaly is the same thing. Policy adaptation is tied to the underlying cause, not just a generic “something is wrong” state.

### Decision selection and recovery verification

Once a fault is classified, the system selects a response policy based on the class and the active context. Responses can include reduced speed, conservative replanning, route geometry changes, reallocation of torque, or temporarily preserving current route under uncertainty.

Recovery is then verified using explicit criteria, such as progress achieved over a time horizon without halt or unsafe motion. This prevents a controller from simply declaring success after a short reaction while leaving the vehicle in a degraded state.

## Research methodology

The project is designed around a clear research question:

Can fault-specific, uncertainty-aware adaptive replanning improve rover mission performance compared with a fixed rule-based response controller while maintaining safety?

### Experimental conditions

The rover experiments cover:

- nominal conditions
- single-fault injection cases
- paired-fault conditions reported separately
- development terrains used for calibration
- held-out terrains used for evaluation only

Faults are injected in a controlled and reproducible manner, and all trials are matched using shared seeds so that both controllers operate on the same environment, noise streams, and initial conditions.

### Evaluation metrics

The evaluation is not only about mission completion. ASTRA measures:

- completion rate
- time-to-completion
- energy efficiency and remaining SoC
- route length and path quality
- collision and safety violations
- detection delay
- classification accuracy
- recovery success
- planning latency
- estimation error and filter uncertainty

This broader metric set is essential for comparing autonomy strategies that may trade short-term speed for robustness and safety.

### Statistical evaluation

The repository includes a strong experimental evaluation framework using matched-seed comparisons and robust statistical tests. The methodology is explicitly designed to avoid overclaiming performance based on one favorable scenario. This includes:

- paired experimental structure
- held-out guard conditions
- calibration performed only on development terrains
- pre-registered-like evaluation discipline
- use of comparative tests such as McNemar and Wilcoxon analyses

This is important because a controller that appears effective on a few favorable scenes may fail badly under realistic operational variation.

## Novel research framing

ASTRA’s novelty is not only in the robotics stack; it is in the way the entire system is framed as a scientific autonomy platform.

The project emphasizes several principles:

- truth is not the same as measurement or estimate
- every decision is auditable
- physics and autonomy are intentionally separated
- perception quality is treated as a first-class system variable
- safety is enforced independently of mission performance
- experiments are designed to support real scientific comparison

The most distinctive novelty lies in the combination of:

- fault-aware autonomy
- uncertainty-sensitive planning
- safety-supervised adaptive recovery
- drift detection and perception validation
- matched-seed research evaluation

This positions ASTRA as more than a simulator: it is a decision-making research platform for autonomy under degraded sensing and uncertain environments.

## Technology stack

- Python 3.11+
- FastAPI for API and orchestration
- SQLAlchemy + Alembic for persistence
- PostgreSQL-ready relational storage
- PyBullet for rover physics and terrain interaction
- NumPy, SciPy, and stable-baselines3 for scientific and RL components
- Gymnasium for RL environment interfaces
- PyTorch for learning and policy components
- React + TypeScript + Vite for the web interface
- Three.js / R3F for 3D visualization
- Recharts and Zustand for telemetry and UI state management
- ReportLab for reporting and PDF debriefing

## Repository structure

```text
.
├── autonomy/               # shared mission-intelligence stack
├── backend/                # API, database, orchestration, telemetry
├── docs/                   # methodology, architecture, evaluation notes
├── experiments/            # scenario generation, batch evaluation, stats
├── frontend/               # React + TypeScript UI
├── machine_learning/       # RL environments and PPO training
├── simulation/             # touchdown and rover physics
├── shared/                 # enums and common schemas
├── tests/                  # automated validation
├── .env.example            # environment template
├── alembic.ini             # database migration config
├── docker-compose.yml      # container orchestration
├── package.json            # root web scripts
├── pyproject.toml          # Python project configuration
├── README.md               # project overview and documentation
└── LOGO.png                # project identity
```

## Quick start

### Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Database setup

```bash
alembic upgrade head
```

### Start the backend

```bash
uvicorn backend.api.main:app --port 8000
```

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is typically served locally on the Vite dev server, while the API runs on the configured FastAPI port.

### Docker

```bash
docker compose up --build
```

## Documentation and deeper reading

The repository includes detailed design and methodology notes in the `docs/` folder:

- `docs/ASTRA_OVERVIEW.md` — mission framing and principles
- `docs/SYSTEM_ARCHITECTURE.md` — system organization and interfaces
- `docs/EXPERIMENTAL_METHODOLOGY.md` — experimental design and metrics
- `docs/ADAPTIVE_PLANNING.md` — planning logic and replanning behavior
- `docs/ROVER_FAULT_TAXONOMY.md` — fault classes and responses
- `docs/TOUCHDOWN_CONTROL.md` — guidance and landing control
- `docs/TOUCHDOWN_PHYSICS.md` — Mars landing physics
- `docs/ROVER_PHYSICS.md` — rover kinematics and terrain interactions
- `docs/PPO_TRAINING_GUIDE.md` — RL training setup and usage
- `docs/STATISTICAL_EVALUATION.md` — analysis methodology
- `docs/KNOWN_LIMITATIONS.md` — known gaps and constraints

## Status and honest assessment

The repository is operational and organized as a research platform, with working components across the autonomy stack. The current project status is best described as:

- Touchdown physics, EKF, state estimation, planning, hazard assessment, and autonomous diversion: working and tested
- Rover simulation and autonomy stack: working and tested
- Fault taxonomy and adaptive recovery logic: working and tested
- Moon landing module: working and tested
- RL/PPO infrastructure: functional, but no converged policy is claimed in the currently available repository state
- Experiment engine: active and integrated with reproducible evaluation workflows
- Test suite: automated tests are present and passing in the repository state

This honest framing is important: ASTRA is a credible research system, but it is also an active autonomy platform with areas that remain intentionally constrained or under continued development.

## Limitations

As with any research platform, ASTRA has constraints. These are documented in the project’s limitations guide and include:

- no guarantees of full real-world deployment fidelity
- assumptions in simulation fidelity and terrain models
- hardware and sensor modeling simplifications
- remaining uncertainty around learned control convergence
- no claim of universal generalization beyond the configured mission domains

These limitations are not weaknesses; they are explicit boundaries that make the platform scientifically honest and useful for experimentation.

## Final statement

ASTRA is a complete research platform for autonomous planetary mission intelligence. It brings together simulation, estimation, planning, control, learning, fault diagnosis, and experimental validation under one coherent architecture. Its core novelty is the coupling of uncertainty-aware reasoning, fault-specific recovery, and safety-supervised autonomy in a scientifically disciplined evaluation loop.

The project is most compelling when viewed as a systems and research framework rather than a single algorithm. Its value lies in the combination of autonomous decision-making, robust fault handling, and rigorous comparative evaluation in the context of planetary autonomy.

---

If you want, I can also produce a shorter, more GitHub-optimized version of this README for a cleaner landing page style while keeping the same technical depth.
