"""Batch experiment runner (matched trials, multiprocessing).

Matched design: trial i uses seed = base_seed + i for EVERY controller and condition, so
initial conditions, sensor-noise streams, terrain and fault schedules are identical across
the compared controllers. Every trial and its configuration are persisted.
Usage: python -m experiments.runners.batch <experiment_id> [--workers N]
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select

from experiments.scenarios.rover_conditions import CONDITIONS, TOUCHDOWN_CONDITIONS


def run_rover_trial(terrain: int, condition: str, controller: str, seed: int, max_duration: float | None) -> dict:
    from simulation.rover.mission import RoverConfig, RoverMission
    cfg = RoverConfig(seed=seed, terrain=terrain, controller=controller, faults=[dict(f) for f in CONDITIONS[condition]])
    if max_duration:
        cfg.duration = max_duration
    t0 = time.perf_counter()
    m = RoverMission(cfg)
    try:
        r = m.run()
        return {"result": r, "wall": time.perf_counter() - t0, "decisions": m.audit.to_list(), "fault_log": m.fault_log,
                "config": cfg.to_dict(), "telemetry": m.telemetry[::5], "debrief_series": m.debrief()["series"]}
    finally:
        m.close()


def run_touchdown_trial(condition: str, controller: str, seed: int) -> dict:
    from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
    spec = TOUCHDOWN_CONDITIONS[condition]
    cfg = TouchdownConfig.from_dict({"seed": seed, "controller": controller, **{k: v for k, v in spec.items() if k != "disturbance"}})
    t0 = time.perf_counter()
    m = TouchdownMission(cfg)
    dist = spec.get("disturbance")
    if dist:
        m.run(max_time=dist["t"])
        m.inject_disturbance(dist["force"], dist["duration"])
    r = m.run()
    return {"result": r, "wall": time.perf_counter() - t0, "decisions": m.audit.to_list(), "fault_log": [],
            "config": cfg.to_dict(), "telemetry": m.telemetry[::10], "debrief_series": m.debrief()["series"]}


def _worker(spec: dict) -> dict:
    try:
        if spec["module"] == "rover":
            out = run_rover_trial(spec["terrain"], spec["condition"], spec["controller"], spec["seed"], spec.get("max_duration"))
        else:
            out = run_touchdown_trial(spec["condition"], spec["controller"], spec["seed"])
        return {"trial_id": spec["trial_id"], "ok": True, **out}
    except Exception as e:  # noqa: BLE001 - recorded on the trial, never hidden
        return {"trial_id": spec["trial_id"], "ok": False, "error": f"{e!r}\n{traceback.format_exc(limit=5)}"}


class _RunShim:
    """Adapter so persist_run can store a finished trial like an interactive run."""

    def __init__(self, out: dict, module: str):
        class C:  # noqa: D401
            pass
        self.cfg = C()
        self.cfg.controller = out["config"]["controller"]
        self.cfg.seed = out["config"]["seed"]
        self.cfg.to_dict = lambda: out["config"]
        self.result = out["result"]
        self.t = out["result"].get("mission_time_s", 0.0)
        self.telemetry = out["telemetry"]
        self.fault_log = out["fault_log"]
        from autonomy.decision.audit import DecisionAudit
        self.audit = DecisionAudit(module)
        self._decisions = out["decisions"]
        self.audit.to_list = lambda: self._decisions
        self._series = out["debrief_series"]

    def debrief(self):
        return {"result": self.result, "decisions": self._decisions, "series": self._series}


def run_experiment(exp_id: int, workers: int = 2) -> None:
    from backend.core.config import software_versions
    from backend.database import models as M
    from backend.database.session import session_scope
    from backend.orchestration.persistence import persist_run
    from experiments.analysis.statistics import summarize, summarize_touchdown

    with session_scope() as s:
        exp = s.get(M.Experiment, exp_id)
        module = exp.module
        exp.status = "running"
        exp.software_versions = software_versions()
        pending = [{"trial_id": t.id, "module": module, "terrain": t.terrain, "condition": t.condition,
                    "controller": t.controller, "seed": t.seed, "max_duration": exp.config.get("max_duration")}
                   for t in exp.trials if t.status in ("pending", "running", "failed")]
        total = len(exp.trials)
    done = total - len(pending)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_worker, sp) for sp in pending]
        for f in as_completed(futs):
            out = f.result()
            with session_scope() as s:
                tr = s.get(M.Trial, out["trial_id"])
                exp = s.get(M.Experiment, exp_id)
                if exp.status == "cancelled":
                    pool.shutdown(cancel_futures=True)
                    return
                if out["ok"]:
                    uid = f"trial-{exp_id}-{tr.id}-{uuid.uuid4().hex[:6]}"
                    tr.metrics = json.loads(json.dumps(out["result"], default=str))
                    tr.status = "completed"
                    tr.run_uid = uid
                else:
                    tr.status = "failed"
                    tr.metrics = {"error": out["error"]}
                done += 1
                exp.progress = {"done": done, "total": total, "updated": datetime.now(timezone.utc).isoformat()}
            if out["ok"]:
                try:
                    persist_run(module, uid, _RunShim(out, module), "completed", out["wall"], trial_id=out["trial_id"])
                except Exception as e:  # noqa: BLE001
                    print("persist failed", e)
    with session_scope() as s:
        exp = s.get(M.Experiment, exp_id)
        trials = [{"terrain": t.terrain, "condition": t.condition, "controller": t.controller, "seed": t.seed,
                   "status": t.status, "metrics": t.metrics} for t in exp.trials]
        exp.summary = json.loads(json.dumps(summarize(trials) if module == "rover" else summarize_touchdown(trials), default=str))
        failed = sum(1 for t in exp.trials if t.status == "failed")
        exp.status = "completed" if failed == 0 else "completed_with_errors"
        exp.finished_at = datetime.now(timezone.utc)


def create_experiment(req: dict) -> int:
    from backend.database import models as M
    from backend.database.session import session_scope
    from simulation.rover.terrain import DEVELOPMENT, HELD_OUT
    module = req.get("module", "rover")
    if module == "rover":
        terrains = list(req["terrains"])
        allowed = HELD_OUT if req.get("held_out") else DEVELOPMENT
        bad = [t for t in terrains if t not in allowed]
        if bad:
            raise ValueError(f"terrains {bad} not allowed in {'held-out' if req.get('held_out') else 'development'} mode "
                             f"(allowed: {list(allowed)})")
        for c in req["conditions"]:
            if c not in CONDITIONS:
                raise ValueError(f"unknown condition {c}")
        ctrls = [c for c in req["controllers"] if c in ("astra", "fsm")]
    else:
        terrains = [None]
        for c in req["conditions"]:
            if c not in TOUCHDOWN_CONDITIONS:
                raise ValueError(f"unknown touchdown condition {c}")
        ctrls = [c for c in req["controllers"] if c in ("pid", "mpc", "ppo")]
    if not ctrls:
        raise ValueError("no valid controllers")
    with session_scope() as s:
        exp = M.Experiment(name=req["name"], module=module, held_out=bool(req.get("held_out")), config=req,
                           status="created", progress={"done": 0, "total": 0})
        s.add(exp); s.flush()
        n = 0
        for terr in terrains:
            for cond in req["conditions"]:
                for i in range(req["trials"]):
                    for ctrl in ctrls:
                        s.add(M.Trial(experiment_id=exp.id, condition=cond, terrain=terr, controller=ctrl,
                                      seed=req["base_seed"] + i, trial_index=i))
                        n += 1
        exp.progress = {"done": 0, "total": n}
        return exp.id


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("experiment_id", type=int)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    run_experiment(a.experiment_id, a.workers)
