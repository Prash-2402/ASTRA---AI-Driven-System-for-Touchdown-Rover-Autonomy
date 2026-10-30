# ASTRA Installation & Deployment Guide
## Local Development, Python Virtual Environments, and Docker Deployment

### 1. Prerequisites
- **Operating System:** Windows 10/11, macOS, or Ubuntu 20.04/22.04 LTS.
- **Python:** Version 3.10 to 3.13 (Global Python 3.13 supported).
- **Node.js:** Version 18+ and `npm` 9+.
- **Docker & Docker Compose (Optional):** For containerized multi-service deployment.

---

### 2. Local Setup (Frontend & Backend)

#### Clone and Backend Environment Setup
```bash
# Navigate to workspace
cd ASTRA

# Install backend dependencies
pip install fastapi uvicorn pydantic numpy scipy torch torchvision gymnasium stable-baselines3 sqlalchemy pytest httpx

# Verify backend database setup
python -c "from backend.database.session import init_db; init_db()"
```

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Run development server
npm run dev
# The landing page and research app will be available at http://localhost:5173
```

#### Launching the Backend Server
```bash
# From workspace root
uvicorn backend.core.main:app --host 0.0.0.0 --port 8000 --reload
# REST APIs and Swagger UI available at http://localhost:8000/docs
# WebSocket endpoint at ws://localhost:8000/ws
```

---

### 3. Docker Deployment
```bash
# Build and run with docker compose
docker-compose up --build -d

# Check service health
docker-compose ps
```
Services exposed:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- PostgreSQL Database: `localhost:5432`
