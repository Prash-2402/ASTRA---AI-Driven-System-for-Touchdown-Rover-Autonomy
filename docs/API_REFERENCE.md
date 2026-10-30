# API Reference

Interactive OpenAPI docs: `http://localhost:8000/docs`. All bodies are validated with Pydantic (`shared/schemas/api.py`).

## Platform
| Method | Path | Purpose |
|---|---|---|
| GET | /api/platform/status | DB health, counts, sessions, controller availability, software versions |
| GET | /api/modules | module list |
| GET | /api/docs, /api/docs/{name} | documentation |
| GET/POST | /api/profiles | local profiles |

## Touchdown (`/api/touchdown`)
`GET/POST /config` · `POST /start {speed}` · `/pause` · `/resume` · `/stop` · `/reset` · `/speed {speed}` ·
`GET /telemetry` (session + snapshot + trajectories) · `GET /scene` · `GET /debrief` (409 until finished) ·
`GET /decisions` · `POST /inject/hazard {x,y,radius}` · `/inject/disturbance {force,duration,wind}` ·
`/inject/sensor {channel,dropout,degradation}` · `GET /controllers` · `GET/POST /training` · `GET /training/{run_id}`.
PPO config returns 409 while no completed policy exists.

## Rover (`/api/rover`)
`GET/POST /config` (faults validated against the closed taxonomy → 422) · lifecycle as above · `GET /telemetry` ·
`GET /scene` · `GET /terrain` · `GET /terrain/{variant}` · `GET /faults` · `POST /faults {fault_type,duration,params}` ·
`GET /decisions` · `GET /debrief` · `GET /controllers`.

## Moon (`/api/moon`)
`GET/POST /config` (seed, high-gate altitude/downrange, crossrange, P66 rate, propellant) · lifecycle (`/start`,
`/pause`, `/resume`, `/stop`, `/reset`, `/speed`) · `GET /telemetry` · `GET /scene` · `GET /decisions` · `GET /debrief`.

## Rover additions
`GET /api/rover/landing` (computed sky-crane sequence) · `GET /api/rover/costmap` (planner's perceived cost, hard cells, slope).

## Experiments & results
`GET /api/experiments/conditions` · `GET/POST /api/experiments` (held-out guard → 422) · `GET /api/experiments/{id}` ·
`POST /api/experiments/{id}/run?workers=n` (409 if another batch runs) · `POST /api/experiments/{id}/cancel` ·
`GET /api/experiments/{id}/results` · `GET /api/experiments/{id}/export?format=csv|json|pdf` ·
`GET /api/results/statistics?module=&held_out=` · `GET /api/results/compare?module=` · `GET /api/reports`.

## Runs
`GET /api/runs` · `GET /api/runs/{uid}` · `GET /api/runs/{uid}/telemetry?format=json|csv&every=k` · `GET /api/runs/{uid}/report.pdf`.

## WebSockets
`/ws/telemetry` (snapshots, 10 Hz) · `/ws/events` (mission events + status) · `/ws/faults` · `/ws/controller` · `/ws/experiments` (progress).
