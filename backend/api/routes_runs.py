from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from backend.database import models as M
from backend.database.session import session_scope
from backend.reporting.pdf import run_report_pdf
from backend.telemetry.archive import frames_to_csv, read_archive

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_dict(r: M.SimulationRun, full: bool = False) -> dict:
    d = {"run_uid": r.run_uid, "module": r.module, "controller": r.controller, "seed": r.seed, "status": r.status,
         "outcome": r.outcome, "success": r.success, "sim_time_s": r.sim_time_s, "wall_time_s": r.wall_time_s,
         "trial_id": r.trial_id, "started_at": r.started_at.isoformat() if r.started_at else None,
         "finished_at": r.finished_at.isoformat() if r.finished_at else None}
    if full:
        d["result"] = r.result
        d["software_versions"] = r.software_versions
    return d


@router.get("")
def list_runs(module: str | None = None, limit: int = 50, include_trials: bool = False):
    with session_scope() as s:
        q = select(M.SimulationRun).order_by(M.SimulationRun.id.desc()).limit(min(limit, 500))
        if module:
            q = q.where(M.SimulationRun.module == module)
        if not include_trials:
            q = q.where(M.SimulationRun.trial_id.is_(None))
        return [_run_dict(r) for r in s.scalars(q)]


def _get(s, uid):
    r = s.scalar(select(M.SimulationRun).where(M.SimulationRun.run_uid == uid))
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@router.get("/{uid}")
def get_run(uid: str):
    with session_scope() as s:
        r = _get(s, uid)
        d = _run_dict(r, full=True)
        d["config"] = s.get(M.SimulationConfig, r.config_id).config if r.config_id else None
        d["decisions"] = [e.payload for e in s.scalars(select(M.DecisionEventRow).where(M.DecisionEventRow.run_id == r.id).order_by(M.DecisionEventRow.t))]
        d["faults"] = [f.details for f in s.scalars(select(M.FaultEvent).where(M.FaultEvent.run_id == r.id).order_by(M.FaultEvent.t))]
        rep = s.scalar(select(M.MissionReport).where(M.MissionReport.run_id == r.id))
        d["debrief"] = rep.content if rep else None
        return d


@router.get("/{uid}/telemetry")
def run_telemetry(uid: str, format: str = "json", every: int = 1):
    with session_scope() as s:
        r = s.scalar(select(M.SimulationRun).where(M.SimulationRun.run_uid == uid))
        arch = s.scalar(select(M.TelemetryArchive).where(M.TelemetryArchive.run_id == r.id)) if r else None
        apath = arch.path if arch else None
    frames = read_archive(uid, every=max(1, every), path=apath)
    if not frames:
        raise HTTPException(404, "no telemetry archive for this run")
    if format == "csv":
        return Response(frames_to_csv(frames), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{uid}.csv"'})
    return frames


@router.get("/{uid}/report.pdf")
def run_report(uid: str):
    d = get_run(uid)
    return Response(run_report_pdf(d), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{uid}.pdf"'})
