import asyncio
import time
import logging
from typing import Optional, Dict, Any
from shared.enums.simulation import SimulationStatus, ModuleType
from shared.schemas.touchdown import TouchdownConfig, TouchdownTelemetryFrame
from shared.schemas.rover import RoverMissionConfig, RoverFaultSchedule, RoverTelemetryFrame
from simulation.touchdown.lander_simulation import TouchdownSimulation
from simulation.rover.rover_simulation import RoverSimulation
from backend.telemetry.broadcaster import telemetry_broadcaster

logger = logging.getLogger("astra.sim_manager")

class SimulationManager:
    """
    Manages active simulation lifecycle, asynchronous runner tasks,
    and periodic telemetry broadcasting.
    Separates physics integration from rendering/broadcasting rate.
    """
    def __init__(self):
        # Touchdown state
        self.touchdown_sim: Optional[TouchdownSimulation] = None
        self.touchdown_status: SimulationStatus = SimulationStatus.IDLE
        self.touchdown_task: Optional[asyncio.Task] = None
        self.touchdown_latest_frame: Optional[TouchdownTelemetryFrame] = None

        # Rover state
        self.rover_sim: Optional[RoverSimulation] = None
        self.rover_status: SimulationStatus = SimulationStatus.IDLE
        self.rover_task: Optional[asyncio.Task] = None
        self.rover_latest_frame: Optional[RoverTelemetryFrame] = None

    # --- Touchdown Lifecycle ---
    def start_touchdown(self, config: Optional[TouchdownConfig] = None):
        self.stop_touchdown()
        self.touchdown_sim = TouchdownSimulation(config or TouchdownConfig())
        self.touchdown_status = SimulationStatus.RUNNING
        self.touchdown_task = asyncio.create_task(self._run_touchdown_loop())
        logger.info("Touchdown simulation started")

    def pause_touchdown(self):
        if self.touchdown_status == SimulationStatus.RUNNING:
            self.touchdown_status = SimulationStatus.PAUSED

    def resume_touchdown(self):
        if self.touchdown_status == SimulationStatus.PAUSED:
            self.touchdown_status = SimulationStatus.RUNNING

    def stop_touchdown(self):
        self.touchdown_status = SimulationStatus.STOPPED
        if self.touchdown_task and not self.touchdown_task.done():
            self.touchdown_task.cancel()
        self.touchdown_task = None

    def reset_touchdown(self):
        self.stop_touchdown()
        cfg = self.touchdown_sim.config if self.touchdown_sim else TouchdownConfig()
        self.touchdown_sim = TouchdownSimulation(cfg)
        self.touchdown_status = SimulationStatus.IDLE
        self.touchdown_latest_frame = None

    async def _run_touchdown_loop(self):
        dt = self.touchdown_sim.config.dt
        try:
            while self.touchdown_status in [SimulationStatus.RUNNING, SimulationStatus.PAUSED]:
                if self.touchdown_status == SimulationStatus.PAUSED:
                    await asyncio.sleep(0.05)
                    continue

                frame = self.touchdown_sim.step()
                self.touchdown_latest_frame = frame

                # Broadcast frame
                await telemetry_broadcaster.broadcast("touchdown_telemetry", {
                    "channel": "touchdown_telemetry",
                    "module": ModuleType.TOUCHDOWN.value,
                    "event_type": "FRAME",
                    "timestamp": frame.timestamp,
                    "payload": frame.model_dump()
                })

                # Broadcast any new decision audit events
                if self.touchdown_sim.decision_events:
                    latest_decision = self.touchdown_sim.decision_events[-1]
                    await telemetry_broadcaster.broadcast("decision_audit", {
                        "channel": "decision_audit",
                        "module": ModuleType.TOUCHDOWN.value,
                        "event_type": "DECISION",
                        "timestamp": latest_decision.timestamp,
                        "payload": latest_decision.model_dump()
                    })

                if self.touchdown_sim.is_finished:
                    self.touchdown_status = SimulationStatus.COMPLETED
                    break

                await asyncio.sleep(dt)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in touchdown loop: {e}", exc_info=True)
            self.touchdown_status = SimulationStatus.FAILED

    # --- Rover Lifecycle ---
    def start_rover(self, config: Optional[RoverMissionConfig] = None):
        self.stop_rover()
        self.rover_sim = RoverSimulation(config or RoverMissionConfig())
        self.rover_status = SimulationStatus.RUNNING
        self.rover_task = asyncio.create_task(self._run_rover_loop())
        logger.info("Rover simulation started")

    def pause_rover(self):
        if self.rover_status == SimulationStatus.RUNNING:
            self.rover_status = SimulationStatus.PAUSED

    def resume_rover(self):
        if self.rover_status == SimulationStatus.PAUSED:
            self.rover_status = SimulationStatus.RUNNING

    def stop_rover(self):
        self.rover_status = SimulationStatus.STOPPED
        if self.rover_task and not self.rover_task.done():
            self.rover_task.cancel()
        self.rover_task = None

    def reset_rover(self):
        self.stop_rover()
        cfg = self.rover_sim.config if self.rover_sim else RoverMissionConfig()
        self.rover_sim = RoverSimulation(cfg)
        self.rover_status = SimulationStatus.IDLE
        self.rover_latest_frame = None

    def inject_rover_fault(self, fault: RoverFaultSchedule):
        if self.rover_sim:
            self.rover_sim.inject_fault(fault)

    async def _run_rover_loop(self):
        dt = self.rover_sim.config.dt
        try:
            while self.rover_status in [SimulationStatus.RUNNING, SimulationStatus.PAUSED]:
                if self.rover_status == SimulationStatus.PAUSED:
                    await asyncio.sleep(0.05)
                    continue

                frame = self.rover_sim.step()
                self.rover_latest_frame = frame

                # Broadcast frame
                await telemetry_broadcaster.broadcast("rover_telemetry", {
                    "channel": "rover_telemetry",
                    "module": ModuleType.ROVER.value,
                    "event_type": "FRAME",
                    "timestamp": frame.timestamp,
                    "payload": frame.model_dump()
                })

                # Broadcast any new decision audit events
                if self.rover_sim.decision_events:
                    latest_decision = self.rover_sim.decision_events[-1]
                    await telemetry_broadcaster.broadcast("decision_audit", {
                        "channel": "decision_audit",
                        "module": ModuleType.ROVER.value,
                        "event_type": "DECISION",
                        "timestamp": latest_decision.timestamp,
                        "payload": latest_decision.model_dump()
                    })

                if self.rover_sim.is_finished:
                    self.rover_status = SimulationStatus.COMPLETED
                    break

                await asyncio.sleep(dt)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in rover loop: {e}", exc_info=True)
            self.rover_status = SimulationStatus.FAILED

sim_manager = SimulationManager()
