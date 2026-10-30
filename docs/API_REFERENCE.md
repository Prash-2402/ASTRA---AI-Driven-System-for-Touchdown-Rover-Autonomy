# ASTRA REST & WebSocket API Reference
## Complete Specifications of Backend Endpoints and Data Contracts

### 1. Platform Gateway
- `GET /api/platform/status`: Returns platform name, version, operational status, and active modules (`touchdown`, `rover`).

---

### 2. Touchdown Module Endpoints
- `GET /api/touchdown/config`: Fetches active lander mass, Mars atmospheric parameters, and controller type.
- `POST /api/touchdown/start`: Starts real-time 6-DoF descent integration.
- `POST /api/touchdown/pause`: Pauses integration loop.
- `POST /api/touchdown/resume`: Resumes simulation.
- `POST /api/touchdown/reset`: Resets lander to initial entry conditions ($z = 2200\,\text{m}$).
- `GET /api/touchdown/telemetry`: Retrieves latest authoritative telemetry frame (`TouchdownTelemetryFrame`).
- `POST /api/touchdown/training/train_step`: Runs PPO reinforcement learning training episodes on Gymnasium EDL environment.
- `GET /api/touchdown/training/history`: Returns training loss curves, episode lengths, and success rates.

---

### 3. Rover Module Endpoints
- `GET /api/rover/config`: Fetches physical rover mass, battery capacity ($600\,\text{Wh}$), and controller mode.
- `POST /api/rover/start`: Starts rover multi-body simulation towards science target.
- `POST /api/rover/pause`: Pauses navigation.
- `POST /api/rover/resume`: Resumes rover traversal.
- `POST /api/rover/reset`: Resets rover to start waypoint and resets battery SoC to $100\%$.
- `GET /api/rover/telemetry`: Retrieves latest authoritative rover frame (`RoverTelemetryFrame`).
- `GET /api/rover/terrain?variant={1-5}`: Fetches 2D elevation grid and obstacle list for specified terrain.
- `POST /api/rover/faults/inject`: Schedules an authoritative fault injection (`RoverFaultSchedule`).

---

### 4. Experiments & Scientific Benchmarks
- `POST /api/experiments/run`: Launches asynchronous matched trial batch across development and held-out terrains.
- `GET /api/experiments/status`: Reports batch run progress and active trial count.
- `GET /api/experiments/report`: Returns complete statistical report (`ExperimentReport`) with Wilson 95% CIs and $p$-values.

---

### 5. Decision Explainability Audit Logs
- `GET /api/audit/decisions`: Fetches chronological decision audit events (`DecisionAuditEvent`) with state evidence, uncertainty, classification, and verified physical outcome.

---

### 6. Real-Time WebSocket Telemetry
- `WS /ws?client_id={id}`: Subscribes to real-time non-blocking telemetry channel ($15-20\,\text{Hz}$). Broadcasts frames tagged by module (`touchdown`, `rover`, `experiment`).
