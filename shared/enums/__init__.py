"""Enumerations shared across ASTRA modules and the API contract."""
from enum import Enum


class Module(str, Enum):
    TOUCHDOWN = "touchdown"
    ROVER = "rover"


class SimStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class TouchdownPhase(str, Enum):
    PRE_LAUNCH = "PRE-LAUNCH"
    ENTRY = "ENTRY"
    DESCENT = "DESCENT"
    LANDING_APPROACH = "LANDING APPROACH"
    SITE_ASSESSMENT = "SITE ASSESSMENT"
    DIVERSION = "DIVERSION"
    TOUCHDOWN = "TOUCHDOWN"
    MISSION_COMPLETE = "MISSION COMPLETE"
    ABORT = "ABORT"
    FAILED = "FAILED"


class TouchdownController(str, Enum):
    PID = "pid"
    MPC = "mpc"
    PPO = "ppo"


class RoverController(str, Enum):
    ASTRA = "astra"     # fault-specific adaptive replanning
    FSM = "fsm"         # fixed rule-based baseline


class FaultType(str, Enum):
    """The four primary rover fault classes. This taxonomy is closed by design."""
    SENSOR_DROPOUT = "sensor_dropout"
    TERRAIN_MISCLASSIFICATION = "terrain_misclassification"
    POWER_DRAIN = "power_drain"
    ACTUATOR_DEGRADATION = "actuator_degradation"


class SafetyAction(str, Enum):
    CONTINUE = "continue"
    SLOW_DOWN = "slow_down"
    REPLAN = "replan"
    CONSERVE_ENERGY = "conserve_energy"
    SAFE_HALT = "safe_halt"
