# System Architecture

Modular monolith: one Python backend process (FastAPI) hosts simulation sessions on worker threads;
batch experiments and RL training run as subprocesses; a React SPA is the operator interface.

```
frontend (React/TS, Vite)  ── REST /api/* ─┐
   landing page (Three.js)                 ├── backend/api (FastAPI, Pydantic schemas)
   application (R3F, Recharts, Zustand) ◄── WS /ws/{telemetry|events|faults|controller|experiments}
                                           │
backend/orchestration  SimulationSession (thread, fixed dt) ── simulation/touchdown | simulation/rover
backend/events         EventBus (thread-safe → asyncio queues)
backend/database       SQLAlchemy models, Alembic migrations (PostgreSQL)
backend/telemetry      gzip JSONL archives (full rate) + 1 Hz relational rows
backend/reporting      PDF debriefs / experiment reports (ReportLab)
experiments/           conditions, batch runner (process pool), statistics
machine_learning/      Gymnasium env, PPO trainer, checkpoint registry
autonomy/              estimation · prediction · planning · decision · control · fault_detection · safety
shared/                enums, API schemas
```

## Source of truth
The backend simulation is authoritative. The frontend never integrates physics; it renders snapshots and
interpolates visually between them. WebSocket publication (10 Hz wall clock) samples snapshots under a lock
and cannot change the integration step.

## Unified mission-intelligence framework (`autonomy/framework.py`)
| Interface | Touchdown implementation | Rover implementation |
|---|---|---|
| StateObservationManager | sensor health + EKF snapshot | same class |
| PredictionEngine | `TouchdownPredictor` (point mass + guidance + rocket eq.) | `RouteEnergyModel` |
| DecisionEngine | `DiversionDecisionEngine` | `AstraResponseSelector` / `FSMBaseline` |
| SafetySupervisorBase | touchdown limits in supervisor FSM | `RoverSafetySupervisor` (independent of planner) |
| DecisionAudit | diversion / abort events | classification, response, FSM transitions |

The modules share interfaces, not physics and not controllers.

## Rates
| Loop | Touchdown | Rover |
|---|---|---|
| Physics | 100 Hz RK4 | 120 Hz PyBullet (checked against 240 Hz) |
| Sensors | 1–100 Hz per channel | IMU 50, odometry 20, lidar 5, camera 2, visloc 1, battery 2 Hz |
| Control | 20 Hz (MPC re-solve 4 Hz) | 10 Hz |
| Planning / perception | lidar 1 Hz below 450 m; prediction 1 Hz | on demand (blocked route, fault, supervisor) |
| Telemetry record | 10 Hz | 5 Hz |
