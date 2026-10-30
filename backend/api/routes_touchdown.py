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
from shared.schemas.api import (DisturbanceInjection, DriftInjection, HazardInjection, LanderEnvironment, SensorFaultInjection,
                                SpeedRequest, StartRequest, TouchdownConfigRequest, TrainingRequest)
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


def _landing_stats(rows: list[dict]) -> dict:
    import numpy as np
    done = [r for r in rows if r["outcome"] in ("landed", "crash")]
    ok = [r for r in done if r["success"]]
    err = [r["landing_error_m"] for r in ok if r.get("landing_error_m") is not None]
    vz = [abs(r["touchdown_vz"]) for r in ok if r.get("touchdown_vz") is not None]
    return {"runs": len(rows), "completed": len(done), "landed_safely": len(ok),
            "success_rate": (len(ok) / len(done)) if done else None,
            "accuracy_m": float(np.mean(err)) if err else None,          # mean miss distance from the (final) pad
            "precision_m": float(np.std(err)) if len(err) > 1 else None,  # spread of the miss distance (repeatability)
            "touchdown_speed": float(np.mean(vz)) if vz else None,
            "within_2m": (sum(e <= 2.0 for e in err) / len(err)) if err else None}


@router.get("/history")
def history(limit: int = 100, controller: str | None = None, environment: str | None = None):
    """Past landings (database) with per-run results and aggregate success / accuracy / precision."""
    from sqlalchemy import select

    from backend.database import models as M
    from backend.database.session import session_scope
    rows = []
    try:
        with session_scope() as s:
            q = (select(M.SimulationRun, M.SimulationConfig).join(M.SimulationConfig, M.SimulationConfig.id == M.SimulationRun.config_id, isouter=True)
                 .where(M.SimulationRun.module == "touchdown", M.SimulationRun.trial_id.is_(None))
                 .order_by(M.SimulationRun.id.desc()).limit(min(limit, 500)))
            for run, cfg in s.execute(q):
                res, c = run.result or {}, (cfg.config if cfg else {}) or {}
                td = res.get("touchdown") or {}
                rows.append({"run_uid": run.run_uid, "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                             "controller": run.controller, "environment": c.get("environment", "mars"), "seed": run.seed,
                             "outcome": run.outcome, "success": run.success, "landing_error_m": res.get("landing_error_m"),
                             "distance_from_original_m": res.get("distance_from_original_target_m"), "diversions": res.get("diversions"),
                             "touchdown_vz": td.get("vertical_speed"), "fuel_used_kg": res.get("fuel_used_kg"), "mission_time_s": res.get("mission_time_s"),
                             "sensor_faults": list((res.get("sensor_faults") or {}).keys()), "hover_scans": len(res.get("hover_scans") or []),
                             "guard": bool(res.get("ppo_guard"))})
    except Exception as e:  # noqa: BLE001 - history needs the database; say so instead of failing silently
        raise HTTPException(503, f"run history needs the database: {str(e).splitlines()[0]}")
    if controller:
        rows = [r for r in rows if r["controller"] == controller]
    if environment:
        rows = [r for r in rows if r["environment"] == environment]
    by_ctrl = {c: _landing_stats([r for r in rows if r["controller"] == c]) for c in sorted({r["controller"] for r in rows})}
    return {"stats": _landing_stats(rows), "by_controller": by_ctrl, "runs": rows}


@router.get("/replay/{uid}")
def replay(uid: str, every: int = 2):
    """Archived telemetry of a finished landing, slimmed for 3D playback, plus that run's terrain."""
    from sqlalchemy import select

    from backend.database import models as M
    from backend.database.session import session_scope
    from backend.telemetry.archive import read_archive
    with session_scope() as s:
        run = s.scalar(select(M.SimulationRun).where(M.SimulationRun.run_uid == uid))
        if run is None:
            raise HTTPException(404, "run not found")
        cfg = s.get(M.SimulationConfig, run.config_id).config if run.config_id else {}
        result = run.result or {}
        arch = s.scalar(select(M.TelemetryArchive).where(M.TelemetryArchive.run_id == run.id))
        apath = arch.path if arch else None
    frames = read_archive(uid, every=max(1, every), path=apath)
    if not frames:
        raise HTTPException(404, "the telemetry archive for this run is missing on this machine")
    m = TouchdownMission(TouchdownConfig.from_dict({k: v for k, v in (cfg or {}).items() if k not in ("pid", "mpc")}))
    for o in result.get("obstacles") or []:                   # same seeded stream + same order = same rocks
        m.inject_hazard(o["x"], o["y"], o["radius"])
    slim = [{"t": f["t"], "phase": f["phase"], "truth": {k: f["truth"][k] for k in ("position", "velocity", "euler", "agl", "fuel", "tilt_deg")},
             "estimate": {"position": f["estimate"]["position"], "velocity": f["estimate"]["velocity"], "agl": f["estimate"]["agl"],
                          "sigma": f["estimate"]["sigma"][:6], "euler": f["estimate"]["euler"]},
             "error": {"position": f["error"]["position"]}, "actuators": f["actuators"], "command": f["command"], "controller": {},
             "target": f["target"], "predicted_touchdown": None, "innovations": {}} for f in frames]
    return {"run_uid": uid, "result": result, "environment": (cfg or {}).get("environment", "mars"), "frames": slim, "scene": m.scene()}


EVIDENCE_FIGS = {"fig_1_readings_vs_truth.png": "sensor_drift_dataset", "fig_2_innovation_lean.png": "sensor_drift_dataset",
                 "fig_3_cusum_detection.png": "sensor_drift_dataset", "fig_4_innovation_histogram.png": "sensor_drift_dataset",
                 "fig_5_outcomes_on_vs_off.png": "sensor_drift_dataset", "fig_domain_shift.png": "domain_shift"}


@router.get("/evidence")
def evidence():
    """Results of the lying-sensor dataset and the domain-shift study (generated by experiments/runners)."""
    from backend.core.config import settings
    out = {}
    for key, folder in (("sensor_drift", "sensor_drift_dataset"), ("domain_shift", "domain_shift")):
        f = settings.data_dir / folder / "summary.json"
        if f.exists():
            d = json.loads(f.read_text())
            d.pop("runs_detail", None)
            if isinstance(d.get("runs"), list):
                d.pop("runs")
            out[key] = d
    out["figures"] = [n for n, folder in EVIDENCE_FIGS.items() if (settings.data_dir / folder / n).exists()]
    return out


@router.get("/evidence/figure/{name}")
def evidence_figure(name: str):
    from fastapi.responses import FileResponse

    from backend.core.config import settings
    if name not in EVIDENCE_FIGS:
        raise HTTPException(404, "unknown figure")
    p = settings.data_dir / EVIDENCE_FIGS[name] / name
    if not p.exists():
        raise HTTPException(404, "figure not generated yet")
    return FileResponse(p, media_type="image/png")


@router.post("/inject/drift")
def inject_drift(req: DriftInjection):
    s = _session()
    with s.lock:
        return s.mission.inject_drift(req.channel, req.rate, req.axis)


@router.post("/environment")
def set_environment(req: LanderEnvironment):
    s = _session()
    with s.lock:
        merged = {**(s.config.get("_environment") or {}), **{k: v for k, v in req.model_dump().items() if v is not None}}
        s.config["_environment"] = merged
        s.overrides["environment"] = lambda m: m.set_environment(**merged)
        return s.mission.set_environment(**merged)


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
