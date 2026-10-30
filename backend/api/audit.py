from fastapi import APIRouter
from typing import List, Dict, Any
from backend.orchestration.sim_manager import sim_manager

router = APIRouter(prefix="/api/audit", tags=["Decision Audit"])

@router.get("/decisions")
def get_decision_events(limit: int = 50):
    events = []
    if sim_manager.touchdown_sim:
        events.extend([e.model_dump() for e in sim_manager.touchdown_sim.decision_events])
    if sim_manager.rover_sim:
        events.extend([e.model_dump() for e in sim_manager.rover_sim.decision_events])

    events.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return events[:limit]
