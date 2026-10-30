from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.core.config import ROOT
from backend.orchestration.session import manager
from machine_learning.training.checkpoints import CheckpointManager
from shared.schemas.api import (DisturbanceInjection, HazardInjection, SensorFaultInjection, SpeedRequest,
                                StartRequest, TouchdownConfigRequest, TrainingRequest)
from simulation.touchdown.mission import TouchdownConfig, TouchdownMission

router = APIRouter(prefix="/api/touchdown", tags=["touchdown"])
_training_procs: dict[str, subprocess.Popen] = {}


def controller_availability() -> dict:
    ppo = CheckpointManager().latest_model_path("touchdown_ppo")
    return {"pid": True, "mpc": True, "ppo": ppo is not None, "ppo_checkpoint": str(ppo.parent.name) if ppo else None}


def _session():
    s = manager.get("touchdown")
    if s is None:
        s = _configure(TouchdownConfigRequest())
    return s


def _configure(req: TouchdownConfigRequest):
    d = req.model_dump()
    cfg = TouchdownConfig.from_dict(d)
    if cfg.controller == "ppo" and not controller_availability()["ppo"] and not cfg.ppo_checkpoint:
        raise HTTPException(409, "No trained PPO policy exists yet. Train one in the Reinforcement Learning Lab.")
    TouchdownMission(cfg)  # validate eagerly so config errors surface as 4xx
    return manager.configure("touchdown", lambda: TouchdownMission(TouchdownConfig.from_dict(d)), d)


@router.get("/config")
def get_config():
    s = manager.get("touchdown")
    return {"active": s.config if s else None, "defaults": TouchdownConfigRequest().model_dump(),
            "full_defaults": TouchdownConfig().to_dict()}


@router.post("/config")
def set_config(req: TouchdownConfigRequest):
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
        snap = s.mission.snapshot()
    return {**s.info(), **snap}


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
            raise HTTPException(409, "Mission has not finished; no debrief yet.")
        return {"run_uid": s.run_uid, **s.mission.debrief()}


@router.get("/decisions")
def decisions():
    s = _session()
    with s.lock:
        return s.mission.audit.to_list()


@router.post("/inject/hazard")
def inject_hazard(req: HazardInjection):
    s = _session()
    with s.lock:
        return s.mission.inject_hazard(req.x, req.y, req.radius)


@router.post("/inject/disturbance")
def inject_disturbance(req: DisturbanceInjection):
    s = _session()
    with s.lock:
        return s.mission.inject_disturbance(req.force, req.duration, req.wind)


@router.post("/inject/sensor")
def inject_sensor(req: SensorFaultInjection):
    s = _session()
    with s.lock:
        if req.channel not in s.mission.sensors.channels:
            raise HTTPException(404, f"unknown sensor channel {req.channel}")
        if req.dropout is not None:
            s.mission.sensors.set_dropout(req.channel, req.dropout)
        if req.degradation is not None:
            s.mission.sensors.set_degradation(req.channel, req.degradation)
        s.mission._event("injection", f"Sensor {req.channel}: dropout={req.dropout} degradation={req.degradation}")
        return {"channel": req.channel, "dropout": req.dropout, "degradation": req.degradation}


@router.get("/controllers")
def controllers():
    return controller_availability()


# ---------------- reinforcement learning ----------------
def _training_runs() -> list[dict]:
    mgr = CheckpointManager()
    runs = mgr.list_runs("touchdown_ppo")
    for r in runs:
        p = _training_procs.get(r["run_id"])
        r["process_alive"] = bool(p and p.poll() is None)
        if r.get("status") == "running" and p is not None and p.poll() is not None and not r.get("has_model"):
            r["status"] = "failed"
    return runs


@router.get("/training")
def training_runs():
    return {"runs": _training_runs(), "availability": controller_availability()}


@router.get("/training/{run_id}")
def training_run(run_id: str):
    mgr = CheckpointManager()
    meta = mgr.read_meta(run_id)
    if meta is None:
        raise HTTPException(404, "training run not found")
    f = mgr.root / run_id / "metrics.jsonl"
    metrics = [json.loads(line) for line in f.read_text().splitlines()] if f.exists() else []
    return {"run_id": run_id, "metadata": meta, "metrics": metrics}


@router.post("/training")
def start_training(req: TrainingRequest):
    if any(p.poll() is None for p in _training_procs.values()):
        raise HTTPException(409, "A training run is already in progress.")
    run_id = f"touchdown_ppo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log = open(Path(CheckpointManager().run_dir(run_id)) / "train.log", "w")
    p = subprocess.Popen([sys.executable, "-m", "machine_learning.training.train_touchdown_ppo", "--timesteps",
                          str(req.timesteps), "--envs", str(req.envs), "--seed", str(req.seed), "--run-id", run_id,
                          "--eval-every", str(max(req.timesteps // 4, 2048))], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    _training_procs[run_id] = p
    return {"run_id": run_id, "pid": p.pid, "status": "running"}
