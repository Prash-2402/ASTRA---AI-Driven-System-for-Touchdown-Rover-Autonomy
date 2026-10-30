# ASTRA — AI-Driven System for Touchdown & Rover Autonomy

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React + Three.js](https://img.shields.io/badge/frontend-React%20%7C%20Three.js-61DAFB.svg)](https://threejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

ASTRA is an advanced aerospace and planetary robotics autonomy platform designed for high-uncertainty planetary exploration missions. It unites high-fidelity physical simulation kernels, numerical state estimation, receding-horizon optimal control, reinforcement learning terminal descent guidance, and surface rover traversal autonomy.

---

## Key Modules & Capabilities

### 1. Touchdown & Atmospheric Entry, Descent, and Landing (EDL)
- **6-DoF Rigid-Body Simulation:** Mars atmospheric exponential density profile, aerodynamic drag/lift, variable mass depletion, and 4th-Order Runge-Kutta (RK4) integration ( = 0.01\,\text{s}$).
- **State Estimation:** Extended Kalman Filter (EKF) with Joseph-form covariance updates fusing IMU, radar altimeter, Doppler Velocity LIDAR (DVL), and star tracker measurements.
- **Guidance & Control:** Receding-Horizon Model Predictive Control (MPC) with terminal velocity cones, Cascade PID attitude controllers, and Proximal Policy Optimization (PPO) reinforcement learning agents.
- **Hazard Assessment & Autonomous Diversion:** Real-time slope, crater, and rock hazard evaluation with autonomous divert trajectory generation.

### 2. Surface Rover Autonomy & Rocker-Bogie Mechanics
- **6-Wheel Rocker-Bogie Kinematics:** Full kinematic linkage modeling with passive differential pivot and pitch-averaging suspension over rugged terrains.
- **Terramechanics:** Non-linear Pacejka-Coulomb wheel-soil tractive slip curves, drawbar pull, and wheel sinkage models.
- **Traversability & Path Planning:** Dynamic traversability costmap synthesis and Dynamic A* path search with slope and obstacle penalties.
- **Trajectory Tracking & Control:** Lookahead Pure Pursuit path follower and velocity governor.
- **Fault Detection & Safety:** Real-time anomaly detection, Bayesian fault classifier, and hard-constraint safety supervisors.
- **Scientific Evaluation:** Rigorous matched-pair batch benchmarking against rule-based Finite State Machine (FSM) baselines with 95% Wilson score confidence intervals and Welch\'s t-tests.

---

## System Architecture

`
Sense -> Estimate -> Predict -> Decide -> Act -> Verify -> Adapt
`

`
ASTRA/
├── autonomy/            # Perception, EKF estimation, planning, and control
│   ├── control/         # Cascade PID, MPC touchdown, Pure Pursuit rover
│   ├── decision/        # FSM baseline benchmark
│   ├── estimation/      # Joseph-stabilized Extended Kalman Filter
│   ├── fault_detection/ # Real-time anomaly detection & Bayesian classifier
│   ├── planning/        # Traversability costmap & Dynamic A* search
│   └── safety/          # Hard-constraint safety supervisors
├── simulation/          # Deterministic physical simulation engines
│   ├── common/          # Mars atmosphere, coordinates, noise models
│   ├── touchdown/       # 6-DoF Mars lander, propulsion, landing sensors
│   └── rover/           # Rocker-bogie kinematics, Pacejka slip, terrain
├── machine_learning/    # Reinforcement learning pipelines
│   ├── environments/    # Gymnasium LanderEDLEnv wrapper
│   └── training/        # PyTorch Actor-Critic PPO policy & manager
├── backend/             # FastAPI REST endpoints & WebSocket broadcaster
├── frontend/            # React, Three.js 3D viewport, and telemetry UI
├── experiments/         # Matched-pair trial runners & statistical analysis
└── docs/                # Comprehensive technical documentation
`

---

## Quick Start

### Installation

`ash
# Clone the repository
git clone https://github.com/Prash-2402/ASTRA---AI-Driven-System-for-Touchdown-Rover-Autonomy.git
cd ASTRA---AI-Driven-System-for-Touchdown-Rover-Autonomy

# Install Python dependencies
pip install -e .

# Run Unit Tests
pytest tests/ -v
`

### Running Backend API & Telemetry Broadcaster

`ash
uvicorn backend.core.main:app --host 0.0.0.0 --port 8000 --reload
`

### Running Frontend Interface

`ash
cd frontend
npm install
npm run dev
`

---

## Documentation

Full architectural specifications and mathematical derivations are available in the [docs/](docs/) directory:
- [ASTRA Overview](docs/ASTRA_OVERVIEW.md)
- [System Architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Technical Design Document](docs/TECHNICAL_DESIGN.md)
- [Touchdown Physics & RK4](docs/TOUCHDOWN_PHYSICS.md)
- [Touchdown Control & MPC](docs/TOUCHDOWN_CONTROL.md)
- [EKF State Estimation](docs/EKF_MODEL.md)
- [Rover Physics & Terramechanics](docs/ROVER_PHYSICS.md)
- [Reinforcement Learning & PPO](docs/REINFORCEMENT_LEARNING.md)
- [Experimental Methodology](docs/EXPERIMENTAL_METHODOLOGY.md)

---

## License

This project is licensed under the MIT License — see the [LICENSE](pyproject.toml) details.
