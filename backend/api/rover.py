from fastapi import APIRouter
from typing import Optional, List, Dict, Any
from shared.schemas.rover import (
    RoverMissionConfig,
    RoverFaultSchedule,
    RoverTelemetryFrame
)
from shared.enums.simulation import TerrainVariant
from simulation.rover.terrain_generator import TerrainMap
from backend.orchestration.sim_manager import sim_manager

router = APIRouter(prefix="/api/rover", tags=["Rover"])

@router.get("/config")
def get_config():
    if sim_manager.rover_sim:
        return sim_manager.rover_sim.config
    return RoverMissionConfig()

@router.post("/start")
def start_rover(config: Optional[RoverMissionConfig] = None):
    sim_manager.start_rover(config)
    return {"status": "started", "simulation_status": sim_manager.rover_status.value}

@router.post("/pause")
def pause_rover():
    sim_manager.pause_rover()
    return {"status": "paused", "simulation_status": sim_manager.rover_status.value}

@router.post("/resume")
def resume_rover():
    sim_manager.resume_rover()
    return {"status": "resumed", "simulation_status": sim_manager.rover_status.value}

@router.post("/stop")
def stop_rover():
    sim_manager.stop_rover()
    return {"status": "stopped", "simulation_status": sim_manager.rover_status.value}

@router.post("/reset")
def reset_rover():
    sim_manager.reset_rover()
    return {"status": "reset", "simulation_status": sim_manager.rover_status.value}

@router.get("/telemetry")
def get_telemetry():
    if sim_manager.rover_latest_frame:
        return sim_manager.rover_latest_frame
    if sim_manager.rover_sim:
        return sim_manager.rover_sim.step()
    sim_manager.start_rover()
    return sim_manager.rover_sim.step()

@router.post("/faults/inject")
def inject_fault(fault: RoverFaultSchedule):
    sim_manager.inject_rover_fault(fault)
    return {"status": "injected", "fault": fault.model_dump()}

@router.get("/terrain")
def get_terrain_data(variant: int = 1):
    t_variant = TerrainVariant(variant)
    t_map = TerrainMap(t_variant, width_m=100.0, height_m=100.0, resolution_m=2.0)
    # Sample elevation and obstacles
    elevation_matrix = []
    for x in t_map.grid_x:
        row = []
        for y in t_map.grid_y:
            row.append(round(t_map.get_elevation(x, y), 2))
        elevation_matrix.append(row)

    obstacles_list = [
        {"x": float(obs["pos"][0]), "y": float(obs["pos"][1]), "radius": float(obs["radius"]), "height": float(obs["height"])}
        for obs in t_map.obstacles
    ]

    return {
        "variant": variant,
        "is_held_out": (variant in [4, 5]),
        "width": t_map.width,
        "height": t_map.height,
        "elevation_grid": elevation_matrix,
        "obstacles": obstacles_list
    }
