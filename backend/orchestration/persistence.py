"""Persist completed runs: metadata + decimated rows to PostgreSQL, full telemetry to archive."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from backend.core.config import software_versions
from backend.database import models as M
from backend.database.session import session_scope
from backend.telemetry.archive import write_archive


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()


def persist_run(module: str, run_uid: str, mission, status: str, wall_time: float, trial_id: int | None = None) -> int:
    cfg = mission.cfg.to_dict()
    result = mission.result or {}
    frames = mission.telemetry
    with session_scope() as s:
        c = M.SimulationConfig(module=module, config=json.loads(json.dumps(cfg, default=str)), config_hash=config_hash(cfg))
        s.add(c); s.flush()
        run = M.SimulationRun(run_uid=run_uid, module=module, config_id=c.id, trial_id=trial_id,
                              controller=str(mission.cfg.controller), seed=int(mission.cfg.seed), status=status,
                              outcome=result.get("outcome"), success=result.get("success"),
                              sim_time_s=float(mission.t), wall_time_s=wall_time,
                              result=json.loads(json.dumps(result, default=str)), software_versions=software_versions(),
                              finished_at=datetime.now(timezone.utc))
        s.add(run); s.flush()
        if frames:
            path, size = write_archive(run_uid, frames)
            rate = 1.0 / max(frames[1]["t"] - frames[0]["t"], 1e-3) if len(frames) > 1 else 0.0
            s.add(M.TelemetryArchive(run_id=run.id, path=str(path), frames=len(frames), rate_hz=rate, bytes=size))
            step = max(1, int(round(rate)))            # 1 Hz decimation for relational storage
            for f in frames[::step]:
                s.add(M.EstimatedState(run_id=run.id, t=f["t"], estimate=f.get("estimate", {}), truth=f.get("truth", {}),
                                       error=f.get("error", {})))
                s.add(M.ControllerAction(run_id=run.id, t=f["t"], action={"command": f.get("command"),
                                                                           "controller": f.get("controller")}))
                for ch, v in (f.get("sensors") or {}).items():
                    s.add(M.SensorMeasurement(run_id=run.id, t=f["t"], channel=ch, valid=bool(v.get("valid", True)),
                                              value=v.get("value")))
        for ev in mission.audit.to_list():
            s.add(M.DecisionEventRow(run_id=run.id, event_uid=ev["event_id"], t=ev["t"], trigger=ev["trigger"][:200],
                                     decision=ev["decision"][:200], payload=ev))
        for fe in getattr(mission, "fault_log", []):
            s.add(M.FaultEvent(run_id=run.id, t=fe["t"], fault_type=fe["fault_type"], phase=fe["phase"],
                               details=json.loads(json.dumps(fe, default=str))))
        if result:
            s.add(M.MissionReport(run_id=run.id, kind="debrief",
                                  content=json.loads(json.dumps(mission.debrief(), default=str))))
        return run.id
