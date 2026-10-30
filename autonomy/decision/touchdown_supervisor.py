"""Touchdown mission supervisor: finite-state machine driven by simulated conditions."""
from __future__ import annotations

from dataclasses import dataclass

from shared.enums import TouchdownPhase as Ph

ALLOWED = {
    Ph.PRE_LAUNCH: {Ph.ENTRY, Ph.DESCENT},
    Ph.ENTRY: {Ph.DESCENT, Ph.FAILED},
    Ph.DESCENT: {Ph.LANDING_APPROACH, Ph.FAILED, Ph.TOUCHDOWN},
    Ph.LANDING_APPROACH: {Ph.SITE_ASSESSMENT, Ph.TOUCHDOWN, Ph.FAILED},
    Ph.SITE_ASSESSMENT: {Ph.LANDING_APPROACH, Ph.DIVERSION, Ph.ABORT, Ph.TOUCHDOWN, Ph.FAILED},
    Ph.DIVERSION: {Ph.SITE_ASSESSMENT, Ph.TOUCHDOWN, Ph.ABORT, Ph.FAILED},
    Ph.ABORT: {Ph.TOUCHDOWN, Ph.FAILED},
    Ph.TOUCHDOWN: {Ph.MISSION_COMPLETE, Ph.FAILED},
    Ph.MISSION_COMPLETE: set(),
    Ph.FAILED: set(),
}


@dataclass
class SupervisorConfig:
    ignition_agl: float = 2400.0
    approach_agl: float = 700.0
    assessment_agl: float = 450.0
    min_divert_agl: float = 70.0
    max_mission_time: float = 400.0


class TouchdownSupervisor:
    def __init__(self, cfg: SupervisorConfig):
        self.cfg = cfg
        self.phase = Ph.PRE_LAUNCH
        self.history: list[dict] = []
        self.phase_entered_t = 0.0

    def transition(self, new: Ph, t: float, reason: str) -> bool:
        if new == self.phase:
            return False
        if new not in ALLOWED[self.phase]:
            raise RuntimeError(f"illegal transition {self.phase.value} -> {new.value}")
        self.history.append({"t": round(t, 3), "from": self.phase.value, "to": new.value, "reason": reason})
        self.phase = new
        self.phase_entered_t = t
        return True

    @property
    def engine_enabled(self) -> bool:
        return self.phase not in (Ph.PRE_LAUNCH, Ph.ENTRY, Ph.TOUCHDOWN, Ph.MISSION_COMPLETE, Ph.FAILED)

    @property
    def terminal(self) -> bool:
        return self.phase in (Ph.MISSION_COMPLETE, Ph.FAILED)
