from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from shared.schemas.touchdown import TouchdownConfig, TouchdownTelemetryFrame
from backend.orchestration.sim_manager import sim_manager
from machine_learning.training.ppo_manager import ppo_touchdown_manager

router = APIRouter(prefix="/api/touchdown", tags=["Touchdown"])

@router.get("/config")
def get_config():
    if sim_manager.touchdown_sim:
        return sim_manager.touchdown_sim.config
    return TouchdownConfig()

@router.post("/start")
def start_simulation(config: Optional[TouchdownConfig] = None):
    sim_manager.start_touchdown(config)
    return {"status": "started", "simulation_status": sim_manager.touchdown_status.value}

@router.post("/pause")
def pause_simulation():
    sim_manager.pause_touchdown()
    return {"status": "paused", "simulation_status": sim_manager.touchdown_status.value}

@router.post("/resume")
def resume_simulation():
    sim_manager.resume_touchdown()
    return {"status": "resumed", "simulation_status": sim_manager.touchdown_status.value}

@router.post("/stop")
def stop_simulation():
    sim_manager.stop_touchdown()
    return {"status": "stopped", "simulation_status": sim_manager.touchdown_status.value}

@router.post("/reset")
def reset_simulation():
    sim_manager.reset_touchdown()
    return {"status": "reset", "simulation_status": sim_manager.touchdown_status.value}

@router.get("/telemetry")
def get_telemetry():
    if sim_manager.touchdown_latest_frame:
        return sim_manager.touchdown_latest_frame
    if sim_manager.touchdown_sim:
        return sim_manager.touchdown_sim.step()
    sim_manager.start_touchdown()
    return sim_manager.touchdown_sim.step()

@router.post("/training/train_step")
def trigger_ppo_train(episodes: int = 10):
    stats = ppo_touchdown_manager.run_training_step(num_episodes=episodes)
    return {
        "status": "success",
        "training_stats": stats,
        "is_trained": ppo_touchdown_manager.is_trained
    }

@router.get("/training/history")
def get_training_history():
    return {
        "history": ppo_touchdown_manager.training_history,
        "is_trained": ppo_touchdown_manager.is_trained
    }
