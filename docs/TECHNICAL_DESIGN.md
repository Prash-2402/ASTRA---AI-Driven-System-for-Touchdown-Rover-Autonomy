# Technical Design

## Session lifecycle (`backend/orchestration/session.py`)
`IDLE → RUNNING ⇄ PAUSED → (STOPPED | COMPLETED | ERROR)`. `reset` builds a fresh mission from the stored
configuration with a new `run_uid`. With `speed = s > 0` the worker advances `s` simulated seconds per wall
second (capped at 80 ms of compute per iteration); `speed = 0` runs as fast as possible. Exceptions are
captured into `status = error` with a traceback shown in the UI — never swallowed.

On completion or stop the run is persisted (`persistence.py`): configuration (+SHA-256 hash), result,
software versions (numpy/scipy/pybullet/git commit), decisions, fault events, 1 Hz decimated
estimated-state / controller-action rows, a mission report, and a full-rate telemetry archive.

## Experiments (`experiments/runners/batch.py`)
Trial *i* uses `seed = base_seed + i` for every controller and condition, so terrain, sensor-noise streams
(per-subsystem `SeedManager` streams), initial conditions and fault schedules are identical. Trials run in a
process pool; each finished trial is written immediately, so a batch can be resumed after interruption.
Held-out mode only accepts terrains 4–5; development mode only 1–3 (enforced server-side).

## Determinism
Each stochastic subsystem draws from its own SHA-256-derived stream, so adding noise to one sensor never
shifts another subsystem's sequence. Verified by tests (`test_touchdown_reproducible_with_same_seed`,
`test_rover_reproducible_and_nominal_controllers_identical`). Tolerance: bit-identical on the same machine
and software versions; across platforms, PyBullet contact solving may differ at floating-point level.

## Error handling
Validation errors → HTTP 422; conflicting state (PPO without a trained model, two batches at once) → 409;
missing records → 404. Persistence failures are reported as `persist_error` on the session.
