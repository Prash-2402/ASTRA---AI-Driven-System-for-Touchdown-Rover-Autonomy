from __future__ import annotations

import csv
import io
import subprocess
import sys
import threading
import time

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core.config import ROOT
from backend.database import models as M
from backend.database.session import session_scope
from backend.events.bus import bus
from backend.reporting.pdf import experiment_report_pdf
from experiments.analysis.statistics import describe, summarize, summarize_touchdown, wilson_interval
from experiments.runners.batch import create_experiment
from experiments.scenarios.rover_conditions import CONDITIONS, PAIRED, SINGLE, TOUCHDOWN_CONDITIONS
from shared.schemas.api import ExperimentCreate

router = APIRouter(prefix="/api", tags=["experiments"])
_procs: dict[int, subprocess.Popen] = {}
_procs_lock = threading.Lock()
_progress_wake = threading.Event()
_thread_started = False


def _is_running(eid: int) -> bool:
    with _procs_lock:
        p = _procs.get(eid)
        return bool(p and p.poll() is None)


def _exp_dict(e: M.Experiment, trials: bool = False, running: bool | None = None) -> dict:
    is_run = _is_running(e.id) if running is None else running
    d = {
        "id": e.id,
        "name": e.name,
        "module": e.module,
        "status": e.status,
        "held_out": e.held_out,
        "config": e.config,
        "progress": e.progress,
        "summary": e.summary,
        "software_versions": e.software_versions,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        "running": is_run,
    }
    if trials and e.trials:
        d["trials"] = [
            {
                "id": t.id,
                "terrain": t.terrain,
                "condition": t.condition,
                "controller": t.controller,
                "seed": t.seed,
                "trial_index": t.trial_index,
                "status": t.status,
                "run_uid": t.run_uid,
                "metrics": t.metrics,
            }
            for t in sorted(e.trials, key=lambda t: t.id)
        ]
    elif trials:
        d["trials"] = []
    return d


@router.get("/experiments/conditions")
def conditions():
    return {
        "rover": {"single": SINGLE, "paired": PAIRED, "all": list(CONDITIONS)},
        "touchdown": list(TOUCHDOWN_CONDITIONS),
    }


@router.get("/experiments")
def list_experiments(limit: int | None = None, offset: int = 0):
    with _procs_lock:
        running_eids = {eid for eid, p in _procs.items() if p.poll() is None}

    with session_scope() as s:
        stmt = select(M.Experiment).order_by(M.Experiment.id.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        exps = s.scalars(stmt).all()
        return [_exp_dict(e, running=(e.id in running_eids)) for e in exps]


@router.post("/experiments")
def create(req: ExperimentCreate):
    try:
        eid = create_experiment(req.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    with session_scope() as s:
        exp = s.get(M.Experiment, eid)
        return _exp_dict(exp, running=False)


@router.get("/experiments/{eid}")
def get_experiment(eid: int):
    with session_scope() as s:
        stmt = (
            select(M.Experiment)
            .options(selectinload(M.Experiment.trials))
            .where(M.Experiment.id == eid)
        )
        e = s.scalar(stmt)
        if e is None:
            raise HTTPException(404, "experiment not found")
        return _exp_dict(e, trials=True)


@router.post("/experiments/{eid}/run")
def run(eid: int, workers: int = 2):
    with _procs_lock:
        if any(p.poll() is None for p in _procs.values()):
            raise HTTPException(409, "Another experiment batch is running.")

        with session_scope() as s:
            e = s.get(M.Experiment, eid)
            if e is None:
                raise HTTPException(404, "experiment not found")
            e.status = "running"

        log_dir = ROOT / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"experiment_{eid}.log"
        with open(log_file, "a") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "experiments.runners.batch", str(eid), "--workers", str(workers)],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        _procs[eid] = proc

    _ensure_progress_thread()
    _progress_wake.set()
    return {"id": eid, "status": "running", "pid": proc.pid}


@router.post("/experiments/{eid}/cancel")
def cancel(eid: int):
    with _procs_lock:
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

        # Fast projected query for trials: avoids loading full ORM objects
        trial_stmt = (
            select(
                M.Trial.terrain,
                M.Trial.condition,
                M.Trial.controller,
                M.Trial.seed,
                M.Trial.status,
                M.Trial.metrics,
            )
            .where(M.Trial.experiment_id == eid)
            .order_by(M.Trial.id)
        )
        trial_rows = s.execute(trial_stmt).all()
        trials = [
            {
                "terrain": r[0],
                "condition": r[1],
                "controller": r[2],
                "seed": r[3],
                "status": r[4],
                "metrics": r[5],
            }
            for r in trial_rows
        ]
        summ = summarize(trials) if e.module == "rover" else summarize_touchdown(trials)
        complete = summ["trials_completed"] == summ["trials_total"]
        return {"id": eid, "status": e.status, "complete": complete, "held_out": e.held_out, **summ}


@router.get("/experiments/{eid}/export")
def export(eid: int, format: str = "json"):
    d = get_experiment(eid)
    if format == "csv":
        buf = io.StringIO()
        cols = [
            "trial_id", "terrain", "condition", "controller", "seed", "status", "success", "outcome",
            "time_to_completion_s", "mission_time_s", "energy_used_wh", "remaining_battery_soc", "route_length_m",
            "collisions", "safety_violations", "classification_accuracy", "recovery_success_rate",
            "replanning_time_ms_mean", "position_error_mean_m", "heading_error_mean_rad", "landing_error_m",
            "fuel_used_kg", "run_uid",
        ]
        w = csv.writer(buf)
        w.writerow(cols)
        metric_cols = cols[6:-1]
        for t in d["trials"]:
            m = t["metrics"] or {}
            w.writerow([t["id"], t["terrain"], t["condition"], t["controller"], t["seed"], t["status"]] +
                       [m.get(c) for c in metric_cols] + [t["run_uid"]])
        return Response(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="experiment_{eid}.csv"'},
        )
    if format == "pdf":
        d["summary"] = results(eid)
        return Response(
            experiment_report_pdf(d),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="experiment_{eid}.pdf"'},
        )
    return d


@router.get("/results/statistics")
def statistics(module: str = "rover", held_out: bool | None = None):
    """Pooled statistics over all completed experiments of a module (optionally held-out only).

    Optimized to query trials with a direct SQL join, avoiding N+1 queries.
    """
    with session_scope() as s:
        stmt = (
            select(
                M.Trial.terrain,
                M.Trial.condition,
                M.Trial.controller,
                M.Trial.seed,
                M.Trial.status,
                M.Trial.metrics,
            )
            .join(M.Experiment, M.Trial.experiment_id == M.Experiment.id)
            .where(M.Experiment.module == module)
        )
        if held_out is not None:
            stmt = stmt.where(M.Experiment.held_out == held_out)

        trial_rows = s.execute(stmt).all()
        trials = [
            {
                "terrain": r[0],
                "condition": r[1],
                "controller": r[2],
                "seed": r[3],
                "status": r[4],
                "metrics": r[5],
            }
            for r in trial_rows
        ]
    return summarize(trials) if module == "rover" else summarize_touchdown(trials)


@router.get("/results/compare")
def compare(module: str = "touchdown"):
    """Controller comparison from stored runs (interactive + experiment trials) of one module.

    Optimized projection: selects only controller and result columns to minimize memory and payload.
    """
    with session_scope() as s:
        stmt = select(M.SimulationRun.controller, M.SimulationRun.result).where(M.SimulationRun.module == module)
        rows = s.execute(stmt).all()
        by: dict = {}
        for ctrl, res in rows:
            by.setdefault(ctrl, []).append(res or {})

    out = []
    for ctrl, rs in sorted(by.items()):
        n = len(rs)
        k = sum(1 for r in rs if r.get("success"))
        lo, hi = wilson_interval(k, n)
        row = {"controller": ctrl, "n": n, "successes": k, "completion_rate": k / n if n else None, "ci_low": lo, "ci_high": hi}
        if module == "touchdown":
            row.update(
                landing_error_m=describe([r.get("landing_error_m") for r in rs]),
                fuel_used_kg=describe([r.get("fuel_used_kg") for r in rs]),
                touchdown_speed=describe([
                    abs((r.get("touchdown") or {}).get("vertical_speed", 0)) if r.get("touchdown") else None
                    for r in rs
                ]),
            )
        else:
            row.update(
                time_to_completion_s=describe([r.get("time_to_completion_s") for r in rs]),
                energy_used_wh=describe([r.get("energy_used_wh") for r in rs]),
                collisions=describe([r.get("collisions") for r in rs]),
            )
        out.append(row)
    return {"module": module, "controllers": out}


@router.get("/reports")
def reports():
    """Retrieve recent mission reports (lightweight column projection)."""
    with session_scope() as s:
        stmt = (
            select(
                M.MissionReport.id,
                M.MissionReport.kind,
                M.MissionReport.run_id,
                M.MissionReport.experiment_id,
                M.MissionReport.created_at,
            )
            .order_by(M.MissionReport.id.desc())
            .limit(100)
        )
        rows = s.execute(stmt).all()
        return [
            {
                "id": r[0],
                "kind": r[1],
                "run_id": r[2],
                "experiment_id": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]


def _ensure_progress_thread():
    global _thread_started
    with _procs_lock:
        if _thread_started:
            return
        _thread_started = True

    def loop():
        while True:
            # Check if there are active processes; if not, wait for signal or idle check
            with _procs_lock:
                active_procs = {eid: p for eid, p in list(_procs.items()) if p.poll() is None}

            if not active_procs:
                _progress_wake.wait(timeout=10.0)
                _progress_wake.clear()
                continue

            time.sleep(2.0)
            for eid, p in list(active_procs.items()):
                try:
                    with session_scope() as s:
                        e = s.get(M.Experiment, eid)
                        if e:
                            running = p.poll() is None
                            bus.publish("experiments", {"id": eid, "status": e.status, "progress": e.progress,
                                                        "running": running})
                except Exception:  # noqa: BLE001
                    pass

    t = threading.Thread(target=loop, daemon=True, name="experiments-progress")
    t.start()
