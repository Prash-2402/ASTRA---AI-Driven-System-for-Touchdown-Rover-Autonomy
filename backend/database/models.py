"""PostgreSQL schema (SQLAlchemy 2.0). Migrations live in database/migrations (Alembic).

High-frequency telemetry is NOT stored row-per-sample: full-rate frames go to
compressed archives (backend/telemetry/archive.py) referenced from
``telemetry_archives``; the relational tables below hold 1 Hz decimated
samples for querying plus all metadata needed for reproducibility.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[int] = mapped_column(primary_key=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulationConfig(Base):
    __tablename__ = "simulation_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    config: Mapped[dict] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TerrainVariant(Base):
    __tablename__ = "terrain_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    module: Mapped[str] = mapped_column(String(20))
    variant: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    split: Mapped[str] = mapped_column(String(20))           # development | held_out
    parameters: Mapped[dict] = mapped_column(JSON)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(20), index=True)
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("missions.id"), nullable=True)
    config_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_configs.id"), nullable=True)
    trial_id: Mapped[int | None] = mapped_column(ForeignKey("trials.id"), nullable=True, index=True)
    controller: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sim_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    wall_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    software_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decisions = relationship("DecisionEventRow", cascade="all, delete-orphan", back_populates="run")


class TelemetryArchive(Base):
    __tablename__ = "telemetry_archives"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(500))
    frames: Mapped[int] = mapped_column(Integer)
    rate_hz: Mapped[float] = mapped_column(Float)
    bytes: Mapped[int] = mapped_column(Integer)


class SensorMeasurement(Base):
    __tablename__ = "sensor_measurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    t: Mapped[float] = mapped_column(Float)
    channel: Mapped[str] = mapped_column(String(40))
    valid: Mapped[bool] = mapped_column(Boolean)
    value: Mapped[list | None] = mapped_column(JSON, nullable=True)


class EstimatedState(Base):
    __tablename__ = "estimated_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    t: Mapped[float] = mapped_column(Float)
    estimate: Mapped[dict] = mapped_column(JSON)
    truth: Mapped[dict] = mapped_column(JSON)
    error: Mapped[dict] = mapped_column(JSON)


class ControllerAction(Base):
    __tablename__ = "controller_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    t: Mapped[float] = mapped_column(Float)
    action: Mapped[dict] = mapped_column(JSON)


class FaultEvent(Base):
    __tablename__ = "fault_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    t: Mapped[float] = mapped_column(Float)
    fault_type: Mapped[str] = mapped_column(String(40))
    phase: Mapped[str] = mapped_column(String(20))           # injected | detected | classified | recovered | cleared
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class DecisionEventRow(Base):
    __tablename__ = "decision_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    event_uid: Mapped[str] = mapped_column(String(40))
    t: Mapped[float] = mapped_column(Float)
    trigger: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON)
    run = relationship("SimulationRun", back_populates="decisions")


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="created")   # created | running | completed | failed | cancelled
    held_out: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSON)
    software_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trials = relationship("Trial", cascade="all, delete-orphan", back_populates="experiment")


class Trial(Base):
    __tablename__ = "trials"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    condition: Mapped[str] = mapped_column(String(80))
    terrain: Mapped[int | None] = mapped_column(Integer, nullable=True)
    controller: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(Integer)
    trial_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experiment = relationship("Experiment", back_populates="trials")


class TrainingRun(Base):
    __tablename__ = "training_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_uid: Mapped[str] = mapped_column(String(120), unique=True)
    algorithm: Mapped[str] = mapped_column(String(20), default="PPO")
    status: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    final_evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelCheckpoint(Base):
    __tablename__ = "model_checkpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    training_run_id: Mapped[int] = mapped_column(ForeignKey("training_runs.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(500))
    timesteps: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(40))
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MissionReport(Base):
    __tablename__ = "mission_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=True)
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))       # debrief | experiment
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
