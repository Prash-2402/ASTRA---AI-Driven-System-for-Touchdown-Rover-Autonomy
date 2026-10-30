"""ASTRA FastAPI application. Run: uvicorn backend.api.main:app --reload"""
from __future__ import annotations

import json

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import routes_platform, routes_runs, routes_touchdown, websocket
from backend.core.config import VERSION, settings


class NumpyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(content, default=_np_default, allow_nan=False, separators=(",", ":")).encode()


def _np_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    return str(o)


TAGS_METADATA = [
    {"name": "platform", "description": "Platform status, system diagnostics, and hardware telemetry."},
    {"name": "touchdown", "description": "Mars powered-descent 6-DOF simulation, EKF estimation, and guidance."},
    {"name": "rover", "description": "Mars rover surface navigation, terrain perception, and adaptive fault response."},
    {"name": "moon", "description": "Lunar module landing simulation with Apollo-style P64/P66 guidance."},
    {"name": "experiments", "description": "Matched-seed batch experiment execution and statistical hypothesis tests."},
]


def create_app() -> FastAPI:
    app = FastAPI(title="ASTRA API", version=VERSION, default_response_class=NumpyJSONResponse,
                  description="AI-Driven System for Touchdown & Rover Autonomy",
                  openapi_tags=TAGS_METADATA)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins + ["*"], allow_methods=["*"], allow_headers=["*"])
    for r in (routes_platform.router, routes_touchdown.router, routes_runs.router, websocket.router):
        app.include_router(r)
    try:
        from backend.api import routes_rover
        app.include_router(routes_rover.router)
    except ImportError:
        pass
    from backend.api import routes_moon
    app.include_router(routes_moon.router)
    try:
        from backend.api import routes_experiments
        app.include_router(routes_experiments.router)
    except ImportError:
        pass
    @app.on_event("startup")
    def _mark_orphaned_batches():
        """A batch marked 'running' cannot be alive when the API process (its parent) has just started:
        mark it 'interrupted' so the UI shows it truthfully; completed trials are kept and it can be resumed."""
        try:
            from backend.database import models as M
            from backend.database.session import session_scope
            with session_scope() as s:
                for e in s.query(M.Experiment).filter(M.Experiment.status == "running"):
                    e.status = "interrupted"
        except Exception:  # noqa: BLE001 - DB may be unavailable; status endpoint reports that
            pass

    return app


app = create_app()
