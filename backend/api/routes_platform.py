from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from backend.core.config import VERSION, software_versions
from backend.database import models as M
from backend.database.session import db_status, session_scope
from backend.orchestration.session import manager

router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/platform/status")
def platform_status():
    db = db_status()
    counts, recent = {}, []
    if db["connected"]:
        with session_scope() as s:
            counts = {
                "runs": s.scalar(select(func.count(M.SimulationRun.id))) or 0,
                "experiments": s.scalar(select(func.count(M.Experiment.id))) or 0,
                "experiments_completed": s.scalar(select(func.count(M.Experiment.id)).where(M.Experiment.status == "completed")) or 0,
                "decisions": s.scalar(select(func.count(M.DecisionEventRow.id))) or 0,
                "training_runs": s.scalar(select(func.count(M.TrainingRun.id))) or 0,
            }
            for r in s.scalars(select(M.SimulationRun).order_by(M.SimulationRun.id.desc()).limit(8)):
                recent.append({"run_uid": r.run_uid, "module": r.module, "controller": r.controller,
                               "outcome": r.outcome, "success": r.success, "trial": r.trial_id is not None,
                               "finished_at": r.finished_at.isoformat() if r.finished_at else None})
    from backend.api.routes_touchdown import controller_availability
    return {"name": "ASTRA", "version": VERSION, "database": db, "counts": counts, "recent_runs": recent,
            "sessions": {k: v.info() for k, v in manager.sessions.items()},
            "controllers": {"touchdown": controller_availability(), "rover": {"astra": True, "fsm": True}},
            "software": software_versions()}


@router.get("/modules")
def modules():
    return [
        {"id": "touchdown", "name": "ASTRA TOUCHDOWN", "description": "Autonomous planetary entry, descent and landing",
         "controllers": ["pid", "mpc", "ppo"]},
        {"id": "rover", "name": "ASTRA ROVER", "description": "Adaptive rover autonomy under injected hazards",
         "controllers": ["astra", "fsm"]},
    ]


# ---------------- documentation & local profiles ----------------
from pathlib import Path  # noqa: E402

from fastapi import HTTPException  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.core.config import ROOT  # noqa: E402

DOCS = ROOT / "docs"


@router.get("/docs")
def list_docs():
    order = ["ASTRA_OVERVIEW.md", "SYSTEM_ARCHITECTURE.md", "TECHNICAL_DESIGN.md"]
    names = sorted(p.name for p in DOCS.glob("*.md"))
    return [n for n in order if n in names] + [n for n in names if n not in order]


@router.get("/docs/{name}")
def get_doc(name: str):
    p = (DOCS / name).resolve()
    if p.parent != DOCS.resolve() or p.suffix != ".md" or not p.exists():
        raise HTTPException(404, "document not found")
    return {"name": name, "content": p.read_text()}


class ProfileIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


@router.get("/profiles")
def profiles():
    with session_scope() as s:
        return [{"id": p.id, "name": p.name} for p in s.scalars(select(M.Profile).order_by(M.Profile.id))]


@router.post("/profiles")
def add_profile(p: ProfileIn):
    with session_scope() as s:
        if s.scalar(select(M.Profile).where(M.Profile.name == p.name)):
            raise HTTPException(409, "profile exists")
        row = M.Profile(name=p.name, preferences={})
        s.add(row); s.flush()
        return {"id": row.id, "name": row.name}
