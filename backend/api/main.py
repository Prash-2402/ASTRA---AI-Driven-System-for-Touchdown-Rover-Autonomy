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


def create_app() -> FastAPI:
    app = FastAPI(title="ASTRA API", version=VERSION, default_response_class=NumpyJSONResponse,
                  description="AI-Driven System for Touchdown & Rover Autonomy")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins + ["*"], allow_methods=["*"], allow_headers=["*"])
    for r in (routes_platform.router, routes_touchdown.router, routes_runs.router, websocket.router):
        app.include_router(r)
    try:
        from backend.api import routes_rover
        app.include_router(routes_rover.router)
    except ImportError:
        pass
    try:
        from backend.api import routes_experiments
        app.include_router(routes_experiments.router)
    except ImportError:
        pass
    return app


app = create_app()
