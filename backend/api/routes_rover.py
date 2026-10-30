from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.orchestration.session import manager
from shared.enums import FaultType
from shared.schemas.api import (FaultInjectRequest, RoverConfigRequest, RoverEnvironment, RoverObstacle, SpeedRequest,
                                StartRequest)
from simulation.rover.faults import DEFAULT_PARAMS
from simulation.rover.mission import RoverConfig, RoverMission
from simulation.rover.terrain import VARIANTS, generate

router = APIRouter(prefix="/api/rover", tags=["rover"])


def _cfg_dict(req: RoverConfigRequest) -> dict:
    d = req.model_dump()
    out = {"seed": d["seed"], "terrain": d["terrain"], "controller": d["controller"], "start": d["start"],
           "target": d["target"], "rover_mass": d["rover_mass"], "faults": d["faults"],
           "ground_ops": d["ground_ops"], "tasks": d["tasks"], "task_kinds": d["task_kinds"]}
    for k_req, k_cfg in (("initial_battery", "initial_battery"), ("wheel_torque", "wheel_torque"),
                         ("max_speed", "max_speed"), ("duration", "duration")):
        if d[k_req] is not None:
            out[k_cfg] = d[k_req]
    return out


def _configure(req: RoverConfigRequest):
    d = _cfg_dict(req)
    for f in d["faults"]:
        try:
            FaultType(f.get("fault_type"))
        except ValueError:
            raise HTTPException(422, f"unknown fault type {f.get('fault_type')}; taxonomy is closed: {[x.value for x in FaultType]}")
    old = manager.get("rover")
    if old is not None:
        old.reset()
        with old.lock:
            old.mission.close()
    return manager.configure("rover", lambda: RoverMission(RoverConfig.from_dict(d)), d)


def _session():
    s = manager.get("rover")
    return s if s is not None else _configure(RoverConfigRequest())


@router.get("/config")
def get_config():
    s = manager.get("rover")
    return {"active": s.config if s else None, "defaults": RoverConfigRequest().model_dump(),
            "fault_defaults": DEFAULT_PARAMS}


@router.post("/config")
def set_config(req: RoverConfigRequest):
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
    s = _session()
    with s.lock:
        s.mission.close()
    s.reset()
    return s.info()


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


@router.get("/terrain")
def terrains():
    return [{"variant": k, "name": v["name"], "split": v["split"], "start": v["start"], "target": v["target"]}
            for k, v in VARIANTS.items()]


@router.get("/terrain/{variant}")
def terrain(variant: int):
    if variant not in VARIANTS:
        raise HTTPException(404, "terrain variant must be 1..5")
    t = generate(variant)
    return {**t.summary(), **t.visual(step=2)}


@router.get("/faults")
def faults():
    s = manager.get("rover")
    active = []
    log = []
    if s:
        with s.lock:
            active = [f.to_dict() for f in s.mission.injector.specs]
            log = s.mission.fault_log
    return {"taxonomy": [f.value for f in FaultType], "defaults": DEFAULT_PARAMS, "scheduled": active, "log": log}


@router.post("/faults")
def inject(req: FaultInjectRequest):
    s = _session()
    with s.lock:
        return s.mission.inject_fault(req.fault_type, req.duration, req.params)


@router.post("/environment")
def set_environment(req: RoverEnvironment):
    s = _session()
    with s.lock:
        merged = {**(s.config.get("_environment") or {}), **{k: v for k, v in req.model_dump().items() if v is not None}}
        s.config["_environment"] = merged
        s.overrides["environment"] = lambda m: m.set_environment(**merged)
        return s.mission.set_environment(**merged)


@router.post("/obstacle")
def add_obstacle(req: RoverObstacle):
    s = _session()
    with s.lock:
        try:
            return s.mission.add_obstacle(req.x, req.y, req.radius)
        except ValueError as e:
            raise HTTPException(422, str(e))


@router.get("/decisions")
def decisions():
    s = _session()
    with s.lock:
        return s.mission.audit.to_list()


@router.get("/debrief")
def debrief():
    s = _session()
    with s.lock:
        if not s.mission.result:
            raise HTTPException(409, "Mission has not finished; no debrief yet.")
        return {"run_uid": s.run_uid, **s.mission.debrief()}


@router.get("/controllers")
def controllers():
    return {"astra": {"available": True, "description": "Fault-specific, uncertainty-aware adaptive replanning"},
            "fsm": {"available": True, "description": "Fixed rule-based finite-state-machine baseline"}}


@router.get("/landing")
def landing():
    """Sky-crane landing sequence for the configured terrain/seed (computed dynamics, see simulation/rover/skycrane.py)."""
    import numpy as np

    from simulation.rover.skycrane import simulate_skycrane
    s = _session()
    with s.lock:
        t = s.mission.terrain
        seed = s.mission.cfg.seed
        mass = s.mission.geom.total_mass
    heading = float(np.arctan2(t.target[1] - t.start[1], t.target[0] - t.start[0]))
    return simulate_skycrane(t.start, t.height, heading=heading, seed=seed, rover_mass=mass)


@router.get("/costmap")
def costmap():
    """Perceived traversability cost, hard constraints and slope (the planner's own view of the terrain)."""
    import numpy as np

    from autonomy.planning.traversability import build_costmap
    s = _session()
    with s.lock:
        m = s.mission
        cost, hard, info = build_costmap(m.map, m.weights, m.ekf.pos_sigma(), float(np.min(m.actuator_health_est)))
        slope = m.map.slope()
        seen = (m.map.seen_t >= 0)
    return {"cell": 1.0, "size_m": 60.0, "cost": np.round(np.where(hard, -1, cost), 2).tolist(),
            "slope": np.round(slope, 1).tolist(), "seen": seen.astype(int).tolist(), "info": info}
