"""Typed API request/response contracts (mirrored in frontend/src/services/types.ts)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    speed: float = Field(1.0, ge=0.0, le=200.0, description="sim-seconds per wall-second; 0 = max")


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0.0, le=200.0)


class TouchdownConfigRequest(BaseModel):
    seed: int = 42
    controller: Literal["pid", "mpc", "ppo"] = "pid"
    environment: Literal["mars", "moon"] = "mars"
    initial_position: list[float] = Field(default=[-650.0, 320.0, 2900.0], min_length=3, max_length=3)
    initial_velocity: list[float] = Field(default=[32.0, -14.0, -62.0], min_length=3, max_length=3)
    target: list[float] = Field(default=[0.0, 0.0], min_length=2, max_length=2)
    planet: dict[str, Any] = Field(default_factory=dict)
    terrain: dict[str, Any] = Field(default_factory=dict)
    lander: dict[str, Any] = Field(default_factory=dict)
    sensors: dict[str, Any] = Field(default_factory=dict)
    supervisor: dict[str, Any] = Field(default_factory=dict)
    enable_diversion: bool = True
    ppo_checkpoint: str | None = None


class HazardInjection(BaseModel):
    x: float | None = None
    y: float | None = None
    radius: float = Field(25.0, gt=0, le=150)


class LanderEnvironment(BaseModel):
    wind_speed: float | None = Field(None, ge=0, le=40)
    wind_dir_deg: float | None = Field(None, ge=-360, le=360)
    gust_std: float | None = Field(None, ge=0, le=10)
    dust: float | None = Field(None, ge=0, le=1)


class RoverEnvironment(BaseModel):
    sandstorm: float | None = Field(None, ge=0, le=1, description="dust optical-depth proxy, 0 clear .. 1 severe")
    wind_speed: float | None = Field(None, ge=0, le=40)
    comms: bool | None = None


class RoverObstacle(BaseModel):
    x: float = Field(..., ge=-29, le=29)
    y: float = Field(..., ge=-29, le=29)
    radius: float = Field(0.6, ge=0.2, le=1.5)


class DisturbanceInjection(BaseModel):
    force: list[float] = Field(default=[1500.0, 0.0, 0.0], min_length=3, max_length=3)
    duration: float = Field(3.0, gt=0, le=30)
    wind: list[float] | None = None


class SensorFaultInjection(BaseModel):
    channel: str
    dropout: bool | None = None
    degradation: float | None = Field(None, ge=1.0, le=50.0)


class TrainingRequest(BaseModel):
    timesteps: int = Field(100_000, ge=2_048, le=5_000_000)
    envs: int = Field(2, ge=1, le=8)
    seed: int = 0


class RoverConfigRequest(BaseModel):
    seed: int = 7
    terrain: int = Field(1, ge=1, le=5)
    controller: Literal["astra", "fsm"] = "astra"
    start: list[float] | None = None
    target: list[float] | None = None
    rover_mass: float | None = Field(None, gt=50, le=2000)
    initial_battery: float | None = Field(None, gt=0.05, le=1.0)
    wheel_torque: float | None = Field(None, gt=1, le=500)
    max_speed: float | None = Field(None, gt=0.05, le=2.0)
    duration: float | None = Field(None, gt=10, le=3600)
    faults: list[dict[str, Any]] = Field(default_factory=list)
    ground_ops: bool = False
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    task_kinds: list[Literal["collect_sand", "collect_sample", "capture_image"]] = Field(default_factory=list)


class FaultInjectRequest(BaseModel):
    fault_type: Literal["sensor_dropout", "terrain_misclassification", "power_drain", "actuator_degradation"]
    duration: float | None = Field(None, gt=0, le=3600)
    params: dict[str, Any] = Field(default_factory=dict)


class ExperimentCreate(BaseModel):
    name: str = "Rover fault-response evaluation"
    module: Literal["rover", "touchdown"] = "rover"
    held_out: bool = False
    terrains: list[int] = Field(default=[1])
    conditions: list[str] = Field(default=["nominal"])
    controllers: list[str] = Field(default=["astra", "fsm"])
    trials: int = Field(5, ge=1, le=100)
    base_seed: int = 1000
    max_duration: float | None = None
