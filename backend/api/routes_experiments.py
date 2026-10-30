from __future__ import annotations

import subprocess
import sys
import threading
import time

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from backend.core.config import ROOT
from backend.database import models as M
from backend.database.session import session_scope
from backend.events.bus import bus
from backend.reporting.pdf import experiment_report_pdf
from experiments.analysis.statistics import summarize, summarize_touchdown
from experiments.runners.batch import create_experiment
from experiments.scenarios.rover_conditions import CONDITIONS, PAIRED, SINGLE, TOUCHDOWN_CONDITIONS
from shared.schemas.api import ExperimentCreate

router = APIRouter(prefix="/api", tags=["experiments"])
_procs: dict[int, subprocess.Popen] = {}


def _exp_dict(e: M.Experiment, trials: bool = False) -> dict:
    d = {"id": e.id, "name": e.name, "module": e.module, "status": e.status, "held_out": e.held_out, "config": e.config,
         "progress": e.progress, "summary": e.summary, "software_versions": e.software_versions,
         "created_at": e.created_at.isoformat() if e.created_at else None,
         "finished_at": e.finished_at.isoformat() if e.finished_at else None,
         "running": bool(_procs.get(e.id) and _procs[e.id].poll() is None)}
    if trials:
        d["trials"] = [{"id": t.id, "terrain": t.terrain, "condition": t.condition, "controller": t.controller,
                        "seed": t.seed, "trial_index": t.trial_index, "status": t.status, "run_uid": t.run_uid,
                        "metrics": t.metrics} for t in sorted(e.trials, key=lambda t: t.id)]
    return d


@router.get("/experiments/conditions")
def conditions():
    return {"rover": {"single": SINGLE, "paired": PAIRED, "all": list(CONDITIONS)},
            "touchdown": list(TOUCHDOWN_CONDITIONS)}


@router.get("/experiments")
def list_experiments():
    with session_scope() as s:
        return [_exp_dict(e) for e in s.scalars(select(M.Experiment).order_by(M.Experiment.id.desc()))]


@router.post("/experiments")
def create(req: ExperimentCreate):
    try:
        eid = create_experiment(req.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    with session_scope() as s:
        return _exp_dict(s.get(M.Experiment, eid))


@router.get("/experiments/{eid}")
def get_experiment(eid: int):
    with session_scope() as s:
        e = s.get(M.Experiment, eid)
        if e is None:
            raise HTTPException(404, "experiment not found")
        return _exp_dict(e, trials=True)


@router.post("/experiments/{eid}/run")
def run(eid: int, workers: int = 2):
    if any(p.poll() is None for p in _procs.values()):
        raise HTTPException(409, "Another experiment batch is running.")
    with session_scope() as s:
        e = s.get(M.Experiment, eid)
        if e is None:
            raise HTTPException(404, "experiment not found")
        e.status = "running"
    log = open(ROOT / "data" / f"experiment_{eid}.log", "a")
    _procs[eid] = subprocess.Popen([sys.executable, "-m", "experiments.runners.batch", str(eid), "--workers", str(workers)],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    _ensure_progress_thread()
    return {"id": eid, "status": "running", "pid": _procs[eid].pid}


@router.post("/experiments/{eid}/cancel")
def cancel(eid: int):
    p = _procs.get(eid)
    if p and p.poll() is None:
        p.terminate()
    with session_scope() as s:
        e = s.get(M.Experiment, eid)
        if e:
            e.status = "cancelled"
    return {"id": eid, "status": "cancelled"}


@router.get("/experiments/{eid}/results")
def results(eid: int):
    with session_scope() as s:
        e = s.get(M.Experiment, eid)
        if e is None:
            raise HTTPException(404, "experiment not found")
        trials = [{"terrain": t.terrain, "condition": t.condition, "controller": t.controller, "seed": t.seed,
                   "status": t.status, "metrics": t.metrics} for t in e.trials]
        summ = summarize(trials) if e.module == "rover" else summarize_touchdown(trials)
        complete = summ["trials_completed"] == summ["trials_total"]
        return {"id": eid, "status": e.status, "complete": complete, "held_out": e.held_out, **summ}


@router.get("/experiments/{eid}/export")
def export(eid: int, format: str = "json"):
    d = get_experiment(eid)
    if format == "csv":
        import csv
        import io
        buf = io.StringIO()
        cols = ["trial_id", "terrain", "condition", "controller", "seed", "status", "success", "outcome",
                "time_to_completion_s", "mission_time_s", "energy_used_wh", "remaining_battery_soc", "route_length_m",
                "collisions", "safety_violations", "classification_accuracy", "recovery_success_rate",
                "replanning_time_ms_mean", "position_error_mean_m", "heading_error_mean_rad", "landing_error_m",
                "fuel_used_kg", "run_uid"]
        w = csv.writer(buf); w.writerow(cols)
        for t in d["trials"]:
            m = t["metrics"] or {}
            w.writerow([t["id"], t["terrain"], t["condition"], t["controller"], t["seed"], t["status"]] +
                       [m.get(c) for c in cols[6:-1]] + [t["run_uid"]])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="experiment_{eid}.csv"'})
    if format == "pdf":
        d["summary"] = results(eid)
        return Response(experiment_report_pdf(d), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="experiment_{eid}.pdf"'})
    return d


@router.get("/results/statistics")
def statistics(module: str = "rover", held_out: bool | None = None):
    """Pooled statistics over all completed experiments of a module (optionally held-out only)."""
    with session_scope() as s:
        q = select(M.Experiment).where(M.Experiment.module == module)
        if held_out is not None:
            q = q.where(M.Experiment.held_out == held_out)
        trials = []
        for e in s.scalars(q):
            trials += [{"terrain": t.terrain, "condition": t.condition, "controller": t.controller, "seed": t.seed,
                        "status": t.status, "metrics": t.metrics} for t in e.trials]
    return summarize(trials) if module == "rover" else summarize_touchdown(trials)


@router.get("/results/compare")
def compare(module: str = "touchdown"):
    """Controller comparison from stored runs (interactive + experiment trials) of one module."""
    with session_scope() as s:
        runs = s.scalars(select(M.SimulationRun).where(M.SimulationRun.module == module)).all()
        by: dict = {}
        for r in runs:
            by.setdefault(r.controller, []).append(r.result or {})
    from experiments.analysis.statistics import describe, wilson_interval
    out = []
    for ctrl, rs in sorted(by.items()):
        n = len(rs); k = sum(1 for r in rs if r.get("success"))
        lo, hi = wilson_interval(k, n)
        row = {"controller": ctrl, "n": n, "successes": k, "completion_rate": k / n if n else None, "ci_low": lo, "ci_high": hi}
        if module == "touchdown":
            row.update(landing_error_m=describe([r.get("landing_error_m") for r in rs]),
                       fuel_used_kg=describe([r.get("fuel_used_kg") for r in rs]),
                       touchdown_speed=describe([abs((r.get("touchdown") or {}).get("vertical_speed", 0)) if r.get("touchdown") else None for r in rs]))
        else:
            row.update(time_to_completion_s=describe([r.get("time_to_completion_s") for r in rs]),
                       energy_used_wh=describe([r.get("energy_used_wh") for r in rs]),
                       collisions=describe([r.get("collisions") for r in rs]))
        out.append(row)
    return {"module": module, "controllers": out}


@router.get("/reports")
def reports():
    with session_scope() as s:
        rows = s.scalars(select(M.MissionReport).order_by(M.MissionReport.id.desc()).limit(100)).all()
        return [{"id": r.id, "kind": r.kind, "run_id": r.run_id, "experiment_id": r.experiment_id,
                 "created_at": r.created_at.isoformat()} for r in rows]


_thread_started = False


def _ensure_progress_thread():
    global _thread_started
    if _thread_started:
        return
    _thread_started = True

    def loop():
        while True:
            time.sleep(2.0)
            for eid, p in list(_procs.items()):
                try:
                    with session_scope() as s:
                        e = s.get(M.Experiment, eid)
                        if e:
                            bus.publish("experiments", {"id": eid, "status": e.status, "progress": e.progress,
                                                        "running": p.poll() is None})
                except Exception:  # noqa: BLE001
                    pass
    threading.Thread(target=loop, daemon=True).start()
