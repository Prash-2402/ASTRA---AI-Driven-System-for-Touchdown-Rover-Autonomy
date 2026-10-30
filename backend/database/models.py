import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class MissionRecord(Base):
    __tablename__ = "missions"

    id = Column(String, primary_key=True)
    module = Column(String, nullable=False, index=True) # "touchdown" or "rover"
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="IDLE")
    config_json = Column(Text, nullable=False)
    summary_json = Column(Text, nullable=True)

    runs = relationship("SimulationRunRecord", back_populates="mission", cascade="all, delete-orphan")
    decision_events = relationship("DecisionEventRecord", back_populates="mission", cascade="all, delete-orphan")

class SimulationRunRecord(Base):
    __tablename__ = "simulation_runs"

    id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("missions.id"), nullable=False, index=True)
    seed = Column(Integer, nullable=False)
    controller_type = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    success = Column(Boolean, nullable=True)
    failure_reason = Column(String, nullable=True)
    metrics_json = Column(Text, nullable=True)

    mission = relationship("MissionRecord", back_populates="runs")
    telemetry_samples = relationship("TelemetrySampleRecord", back_populates="run", cascade="all, delete-orphan")

class TelemetrySampleRecord(Base):
    __tablename__ = "telemetry_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("simulation_runs.id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    step = Column(Integer, nullable=False)
    state_json = Column(Text, nullable=False)
    ekf_json = Column(Text, nullable=False)

    run = relationship("SimulationRunRecord", back_populates="telemetry_samples")

    __table_args__ = (
        Index("idx_run_timestamp", "run_id", "timestamp"),
    )

class DecisionEventRecord(Base):
    __tablename__ = "decision_events"

    id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("missions.id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    module = Column(String, nullable=False)
    trigger = Column(String, nullable=False)
    classified_fault = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    selected_decision = Column(String, nullable=False)
    evidence_json = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    actual_outcome = Column(String, nullable=True)

    mission = relationship("MissionRecord", back_populates="decision_events")

class ExperimentRecord(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    config_json = Column(Text, nullable=False)
    status = Column(String, default="PENDING")
    trials_total = Column(Integer, default=0)
    trials_completed = Column(Integer, default=0)
    report_json = Column(Text, nullable=True)

    trials = relationship("ExperimentTrialRecord", back_populates="experiment", cascade="all, delete-orphan")

class ExperimentTrialRecord(Base):
    __tablename__ = "experiment_trials"

    id = Column(String, primary_key=True)
    experiment_id = Column(String, ForeignKey("experiments.id"), nullable=False, index=True)
    seed = Column(Integer, nullable=False)
    terrain_variant = Column(Integer, nullable=False)
    is_held_out = Column(Boolean, default=False)
    controller = Column(String, nullable=False)
    fault_type = Column(String, nullable=False)
    success = Column(Boolean, nullable=False)
    time_to_completion = Column(Float, nullable=False)
    energy_consumed = Column(Float, nullable=False)
    safety_violations = Column(Integer, default=0)
    details_json = Column(Text, nullable=False)

    experiment = relationship("ExperimentRecord", back_populates="trials")
