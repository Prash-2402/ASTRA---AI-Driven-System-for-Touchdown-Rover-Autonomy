from pydantic import BaseModel
from typing import Any, Dict, Optional
from shared.enums.simulation import ModuleType

class WebSocketMessage(BaseModel):
    channel: str # e.g. "touchdown_telemetry", "rover_telemetry", "experiment_progress", "decision_audit"
    module: ModuleType
    event_type: str # e.g. "FRAME", "DECISION", "FAULT_INJECTED", "HAZARD_DIVERSION", "MISSION_END"
    timestamp: float
    payload: Dict[str, Any]

class DecisionAuditEvent(BaseModel):
    event_id: str
    timestamp: float
    module: ModuleType
    trigger: str
    sensor_evidence: Dict[str, Any]
    estimated_state: Dict[str, Any]
    uncertainty: Dict[str, Any]
    classified_fault: Optional[str] = None
    confidence: Optional[float] = None
    selected_decision: str
    rationale: str
    safety_verification: str
    expected_outcome: str
    actual_outcome: Optional[str] = None
