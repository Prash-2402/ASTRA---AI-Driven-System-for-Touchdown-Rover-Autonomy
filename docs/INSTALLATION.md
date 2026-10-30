# Installation & Running

## Requirements
Python 3.11+ (tested 3.13), Node 20+ (tested 22), PostgreSQL 14+ (tested 16). A C++ toolchain may be needed if
PyBullet has no wheel for your Python (it compiles from source in ~5 min).

## Backend
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # adjust ASTRA_DATABASE_URL
createdb astra                  # or use docker compose (below)
alembic upgrade head
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

On Windows (PowerShell):
```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn backend.api.main:app --reload --port 8000
```

## Frontend
```bash
cd frontend && npm install
npm run dev                     # http://localhost:5173  (landing at /, application at /app)
```
Or run directly from the repository root:
```bash
npm run dev:web
```
The UI talks to `http://<host>:8000` by default; change it in **Settings** or with `VITE_API_BASE`.

## Docker
```bash
docker compose up --build       # postgres, api (runs migrations), web
```

## Batch experiments & training from the CLI
```bash
python -m experiments.runners.batch <experiment_id> --workers 4
python -m machine_learning.training.train_touchdown_ppo --timesteps 2000000 --envs 7
```
