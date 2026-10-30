import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database.models import (
    MissionRecord,
    SimulationRunRecord,
    TelemetrySampleRecord,
    DecisionEventRecord,
    ExperimentRecord,
    ExperimentTrialRecord
)

def create_mission(db: Session, mission_id: str, module: str, name: str, config: Dict[str, Any]) -> MissionRecord:
    mission = MissionRecord(
        id=mission_id,
        module=module,
        name=name,
        created_at=datetime.utcnow(),
        status="IDLE",
        config_json=json.dumps(config)
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission

def get_mission(db: Session, mission_id: str) -> Optional[MissionRecord]:
    return db.query(MissionRecord).filter(MissionRecord.id == mission_id).first()

def list_missions(db: Session, module: Optional[str] = None, limit: int = 50) -> List[MissionRecord]:
    query = db.query(MissionRecord)
    if module:
        query = query.filter(MissionRecord.module == module)
    return query.order_by(MissionRecord.created_at.desc()).limit(limit).all()

def create_simulation_run(
    db: Session,
    run_id: str,
    mission_id: str,
    seed: int,
    controller_type: str
) -> SimulationRunRecord:
    run = SimulationRunRecord(
        id=run_id,
        mission_id=mission_id,
        seed=seed,
        controller_type=controller_type,
        started_at=datetime.utcnow()
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

def complete_simulation_run(
    db: Session,
    run_id: str,
    success: bool,
    duration: float,
    metrics: Dict[str, Any],
    failure_reason: Optional[str] = None
):
    run = db.query(SimulationRunRecord).filter(SimulationRunRecord.id == run_id).first()
    if run:
        run.completed_at = datetime.utcnow()
        run.success = success
        run.duration_seconds = duration
        run.failure_reason = failure_reason
        run.metrics_json = json.dumps(metrics)
        db.commit()

def record_decision_event(
    db: Session,
    event_id: str,
    mission_id: str,
    timestamp: float,
    module: str,
    trigger: str,
    selected_decision: str,
    evidence: Dict[str, Any],
    rationale: str,
    classified_fault: Optional[str] = None,
    confidence: Optional[float] = None,
    actual_outcome: Optional[str] = None
) -> DecisionEventRecord:
    event = DecisionEventRecord(
        id=event_id,
        mission_id=mission_id,
        timestamp=timestamp,
        module=module,
        trigger=trigger,
        classified_fault=classified_fault,
        confidence=confidence,
        selected_decision=selected_decision,
        evidence_json=json.dumps(evidence),
        rationale=rationale,
        actual_outcome=actual_outcome
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def get_mission_decisions(db: Session, mission_id: str) -> List[DecisionEventRecord]:
    return db.query(DecisionEventRecord).filter(
        DecisionEventRecord.mission_id == mission_id
    ).order_by(DecisionEventRecord.timestamp.asc()).all()

def save_experiment_trial(
    db: Session,
    trial_id: str,
    experiment_id: str,
    seed: int,
    terrain_variant: int,
    is_held_out: bool,
    controller: str,
    fault_type: str,
    success: bool,
    time_to_completion: float,
    energy_consumed: float,
    safety_violations: int,
    details: Dict[str, Any]
):
    trial = ExperimentTrialRecord(
        id=trial_id,
        experiment_id=experiment_id,
        seed=seed,
        terrain_variant=terrain_variant,
        is_held_out=is_held_out,
        controller=controller,
        fault_type=fault_type,
        success=success,
        time_to_completion=time_to_completion,
        energy_consumed=energy_consumed,
        safety_violations=safety_violations,
        details_json=json.dumps(details)
    )
    db.add(trial)
    db.commit()
