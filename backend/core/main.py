import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.database.session import init_db
from backend.telemetry.broadcaster import telemetry_broadcaster
from backend.orchestration.sim_manager import sim_manager
from backend.api.platform import router as platform_router
from backend.api.touchdown import router as touchdown_router
from backend.api.rover import router as rover_router
from backend.api.experiments import router as experiments_router
from backend.api.audit import router as audit_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("astra")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ASTRA Database...")
    init_db()
    logger.info("ASTRA Database initialized.")
    # Initialize background simulations
    sim_manager.start_touchdown()
    sim_manager.start_rover()
    yield
    logger.info("Shutting down ASTRA simulations...")
    sim_manager.stop_touchdown()
    sim_manager.stop_rover()

app = FastAPI(
    title="ASTRA API",
    description="AI-Driven System for Touchdown & Rover Autonomy",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(platform_router)
app.include_router(touchdown_router)
app.include_router(rover_router)
app.include_router(experiments_router)
app.include_router(audit_router)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str = Query("all")):
    await telemetry_broadcaster.connect(websocket, channel)
    try:
        while True:
            # Keep socket alive and receive any client messages/commands
            data = await websocket.receive_text()
            # Client can ping or send control commands
    except WebSocketDisconnect:
        await telemetry_broadcaster.disconnect(websocket, channel)
    except Exception as e:
        logger.warning(f"WebSocket closed with exception: {e}")
        await telemetry_broadcaster.disconnect(websocket, channel)

@app.get("/")
def root():
    return {
        "message": "ASTRA Platform API operational.",
        "documentation": "/docs",
        "system": "AI-Driven System for Touchdown & Rover Autonomy"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.core.main:app", host="0.0.0.0", port=8000, reload=True)
