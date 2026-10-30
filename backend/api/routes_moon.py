from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.orchestration.session import manager
from shared.schemas.api import SpeedRequest, StartRequest
from simulation.moon.mission import MoonConfig, MoonLandingMission

router = APIRouter(prefix="/api/moon", tags=["moon"])


class MoonConfigRequest(BaseModel):
    seed: int = 11
    high_gate_altitude: float = Field(2000.0, ge=300, le=6000)
    high_gate_downrange: float = Field(4200.0, ge=500, le=5800)
    crossrange_offset: float = Field(60.0, ge=-500, le=500)
    terminal_descent_rate: float = Field(1.0, ge=0.3, le=3.0)
    propellant: float | None = Field(None, ge=200, le=8000)


def _configure(req: MoonConfigRequest):
    d = req.model_dump()
    prop = d.pop("propellant")
    if prop:
        d["lander"] = {"propellant": prop}
    return manager.configure("moon", lambda: MoonLandingMission(MoonConfig.from_dict(d)), d)


def _session():
    return manager.get("moon") or _configure(MoonConfigRequest())


@router.get("/config")
def get_config():
    s = manager.get("moon")
    return {"active": s.config if s else None, "defaults": MoonConfigRequest().model_dump()}


@router.post("/config")
def set_config(req: MoonConfigRequest):
    return _configure(req).info()


@router.post("/start")
def start(req: StartRequest = StartRequest()):
    s = _session(); s.start(req.speed); return s.info()


@router.post("/pause")
def pause():
    s = _session(); s.pause(); return s.info()


@router.post("/resume")
def resume():
    s = _session(); s.resume(); return s.info()


@router.post("/stop")
def stop():
    s = _session(); s.stop(); return s.info()


@router.post("/reset")
def reset():
    s = _session(); s.reset(); return s.info()


@router.post("/speed")
def speed(req: SpeedRequest):
    s = _session(); s.set_speed(req.speed); return s.info()


@router.get("/telemetry")
def telemetry():
    s = _session()
    with s.lock:
        return {**s.info(), **s.mission.snapshot()}


@router.get("/scene")
def scene():
    s = _session()
    with s.lock:
        return s.mission.scene()


@router.get("/debrief")
def debrief():
    s = _session()
    with s.lock:
        if not s.mission.result:
            raise HTTPException(409, "Landing has not finished; no debrief yet.")
        return {"run_uid": s.run_uid, **s.mission.debrief()}


@router.get("/decisions")
def decisions():
    s = _session()
    with s.lock:
        return s.mission.audit.to_list()
