# Database Schema (PostgreSQL 16, Alembic revision 0001)

| Table | Purpose |
|---|---|
| profiles | local user profiles |
| missions | named missions (optional grouping) |
| simulation_configs | full configuration JSON + SHA-256 hash |
| simulation_runs | run uid, module, controller, seed, status, outcome, result JSON, software versions, trial link |
| telemetry_archives | path, frame count, rate, size of the full-rate gzip JSONL archive |
| sensor_measurements / estimated_states / controller_actions | 1 Hz decimated rows (truth, estimate, error; commands) |
| fault_events | injected / cleared fault events per run |
| decision_events | complete audit payload per decision |
| terrain_variants | catalogue of terrain variants and split |
| experiments | design, held-out flag, progress, summary, software versions |
| trials | condition, terrain, controller, seed, status, metrics, run uid |
| training_runs / model_checkpoints | RL registry (file metadata is authoritative for checkpoints) |
| mission_reports | debrief / experiment report content |

**Telemetry strategy:** high-frequency frames are never stored row-per-sample; they go to
`data/telemetry/<run_uid>.jsonl.gz` (CSV/JSON export streams from there). Migrations: `alembic upgrade head`.
