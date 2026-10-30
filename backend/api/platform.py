from fastapi import APIRouter
from shared.enums.simulation import ModuleType
from backend.orchestration.sim_manager import sim_manager

router = APIRouter(prefix="/api/platform", tags=["Platform"])

@router.get("/status")
def get_platform_status():
    return {
        "platform": "ASTRA",
        "full_name": "AI-Driven System for Touchdown & Rover Autonomy",
        "version": "1.0.0",
        "status": "OPERATIONAL",
        "modules": {
            "touchdown": {
                "status": sim_manager.touchdown_status.value,
                "controller": sim_manager.touchdown_sim.config.controller_type.value if sim_manager.touchdown_sim else "MPC",
                "phase": sim_manager.touchdown_sim.phase.value if sim_manager.touchdown_sim else "PRE-LAUNCH",
                "sim_time": sim_manager.touchdown_sim.sim_time if sim_manager.touchdown_sim else 0.0
            },
            "rover": {
                "status": sim_manager.rover_status.value,
                "controller": sim_manager.rover_sim.config.controller_type.value if sim_manager.rover_sim else "ASTRA_ADAPTIVE",
                "phase": sim_manager.rover_sim.phase.value if sim_manager.rover_sim else "IDLE",
                "sim_time": sim_manager.rover_sim.sim_time if sim_manager.rover_sim else 0.0
            }
        }
    }

@router.get("/modules")
def get_modules():
    return [
        {
            "id": ModuleType.TOUCHDOWN.value,
            "name": "ASTRA TOUCHDOWN",
            "subtitle": "Autonomous Planetary Entry, Descent and Landing",
            "features": ["6-DoF Rigid Body", "EKF Estimation", "Cascade PID", "MPC", "PPO RL", "Autonomous Diversion"]
        },
        {
            "id": ModuleType.ROVER.value,
            "name": "ASTRA ROVER",
            "subtitle": "Adaptive Rover Autonomy Under Injected Hazards",
            "features": ["6-Wheel Rocker-Bogie", "URDF Kinematics", "EKF", "4 Fault Injectors", "Dynamic A*", "Pure Pursuit", "FSM Baseline"]
        }
    ]
