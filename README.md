# ASTRA — AI-Driven System for Touchdown & Rover Autonomy

A physics-based research platform for autonomous planetary landing and rover autonomy under faults.

- **ASTRA TOUCHDOWN** — 6-DOF Mars powered descent (RK4), sensor suite, 12-state EKF, cascade PID, constrained MPC,
  PPO infrastructure, lidar hazard mapping, landing-site assessment and physically feasible autonomous diversion.
- **ASTRA ROVER** — PyBullet rocker-bogie rover, five deterministic terrains (3 development, 2 held-out), sensors,
  EKF, perceived traversability, A*, Pure Pursuit, battery model, four injectable faults, detection → classification →
  adaptive response → recovery verification, a fair FSM baseline and an independent safety supervisor.
- **ASTRA MOON** — independent lunar landing: LM-class lander, Apollo-style P64/P66 guidance, landing radar,
  regolith dust, lunar terrain (separate physics from the Mars modules).
- **Research tooling** — matched-seed experiments, held-out guard, Wilson CIs, McNemar/Wilcoxon paired tests,
  PostgreSQL records, telemetry archives, CSV/JSON/PDF exports, decision audit logs.
- **Interface** — cinematic WebGL landing page (GPU-baked Mars globe) and a light, modern application
  (React, Three.js/R3F, Recharts, Zustand) with detailed 3D vehicle models and camera modes.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head && uvicorn backend.api.main:app --port 8000
cd frontend && npm install && npm run dev        # http://localhost:5173
```
or `docker compose up --build`. Full instructions: [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Status (honest)
| Area | State |
|---|---|
| Touchdown physics, EKF, PID, MPC, hazard assessment, diversion, supervisor, debrief | working, tested |
| PPO | environment, trainer, checkpoints, inference, UI working; **no converged policy** — see [docs/PPO_TRAINING_GUIDE.md](docs/PPO_TRAINING_GUIDE.md) |
| Rover simulation, autonomy, faults, FSM baseline, safety | working, tested |
| Experiments | engine working; held-out batch results stored in the database (see Experiment Lab for N completed) |
| Moon landing module | working, tested |
| Tests | 60 automated tests passing |

Limitations: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).
