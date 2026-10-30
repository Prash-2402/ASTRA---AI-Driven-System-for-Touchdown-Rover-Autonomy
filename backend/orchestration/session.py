"""Live simulation sessions.

A session owns one mission object and advances it on a worker thread with
the mission's fixed physics timestep. ``speed`` scales simulated time per
wall-clock second (0 = as fast as possible). Telemetry publication happens
at a fixed wall rate from snapshots and never changes the integration step.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Callable

from backend.events.bus import bus
from shared.enums import SimStatus

PUBLISH_HZ = 10.0


class SimulationSession:
    def __init__(self, module: str, factory: Callable[[], object], config: dict, persist: bool = True):
        self.module = module
        self.factory = factory
        self.config = config
        self.persist = persist
        self.lock = threading.RLock()
        self.status = SimStatus.IDLE
        self.speed = 1.0
        self.error: str | None = None
        self.persist_error: str | None = None
        self.db_run_id: int | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._new_mission()

    def _new_mission(self):
        self.run_uid = f"{self.module}-{uuid.uuid4().hex[:10]}"
        self.mission = self.factory()
        self._events_sent = 0
        self._wall = 0.0

    # -- lifecycle -----------------------------------------------------
    def start(self, speed: float | None = None):
        with self.lock:
            if speed is not None:
                self.speed = speed
            if self.status in (SimStatus.COMPLETED, SimStatus.STOPPED, SimStatus.ERROR):
                self._new_mission()
            if self.status == SimStatus.RUNNING:
                return
            self.status = SimStatus.RUNNING
            self._stop.clear()
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True, name=f"sim-{self.run_uid}")
                self._thread.start()
        self._publish_status()

    def pause(self):
        with self.lock:
            if self.status == SimStatus.RUNNING:
                self.status = SimStatus.PAUSED
        self._publish_status()

    def resume(self):
        with self.lock:
            if self.status == SimStatus.PAUSED:
                self.status = SimStatus.RUNNING
        self._publish_status()

    def stop(self):
        with self.lock:
            if self.status in (SimStatus.RUNNING, SimStatus.PAUSED):
                self.status = SimStatus.STOPPED
                self._stop.set()
        self._publish_status()

    def reset(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self.lock:
            self._new_mission()
            self.status = SimStatus.IDLE
            self.error = None
            self.persist_error = None
            self.db_run_id = None
        self._publish_status()

    def set_speed(self, speed: float):
        with self.lock:
            self.speed = max(0.0, float(speed))

    # -- worker --------------------------------------------------------
    def _loop(self):
        last_pub = 0.0
        last = time.perf_counter()
        sim_budget = 0.0
        try:
            while not self._stop.is_set():
                now = time.perf_counter()
                elapsed, last = now - last, now
                with self.lock:
                    st = self.status
                if st == SimStatus.RUNNING:
                    t0 = time.perf_counter()
                    with self.lock:
                        m = self.mission
                        if self.speed <= 0:
                            while time.perf_counter() - t0 < 0.05 and not self._terminal(m):
                                m.step()
                        else:
                            sim_budget = min(sim_budget + elapsed * self.speed, 2.0)
                            t_start = m.t
                            while m.t - t_start < sim_budget and not self._terminal(m) and time.perf_counter() - t0 < 0.08:
                                m.step()
                            sim_budget -= m.t - t_start
                        self._wall += time.perf_counter() - t0
                        if self._terminal(m):
                            self.status = SimStatus.COMPLETED
                    if self.status == SimStatus.COMPLETED:
                        self._publish(force=True)
                        self._finalize()
                        self._publish_status()
                        return
                else:
                    sim_budget = 0.0
                if now - last_pub >= 1.0 / PUBLISH_HZ:
                    last_pub = now
                    self._publish()
                time.sleep(0.002 if st == SimStatus.RUNNING else 0.02)
            if self.status == SimStatus.STOPPED:
                self._finalize()
        except Exception as e:  # noqa: BLE001 - surfaced to the UI, never hidden
            with self.lock:
                self.status = SimStatus.ERROR
                self.error = f"{e!r}\n{traceback.format_exc(limit=4)}"
            self._publish_status()

    @staticmethod
    def _terminal(m) -> bool:
        if hasattr(m, "terminal"):                      # rover / moon missions expose `terminal` directly
            return bool(m.terminal)
        return bool(m.supervisor.terminal)              # touchdown: mission-supervisor FSM

    def _finalize(self):
        if not self.persist:
            return
        from backend.orchestration.persistence import persist_run
        try:
            with self.lock:
                self.db_run_id = persist_run(self.module, self.run_uid, self.mission, self.status.value, self._wall)
        except Exception as e:  # noqa: BLE001
            self.persist_error = repr(e)

    # -- publication ---------------------------------------------------
    def _publish(self, force: bool = False):
        with self.lock:
            snap = self.mission.snapshot(include_paths=True)
            events = self.mission.events[self._events_sent:]
            self._events_sent = len(self.mission.events)
        snap.update({"run_uid": self.run_uid, "status": self.status.value, "speed": self.speed})
        bus.publish("telemetry", snap)
        frame = snap.get("frame") or {}
        bus.publish("controller", {"module": self.module, "t": snap["t"], "command": frame.get("command"),
                                   "controller": frame.get("controller")})
        for ev in events:
            ev = {"module": self.module, "run_uid": self.run_uid, **ev}
            bus.publish("events", ev)
            if ev.get("kind") in ("fault", "injection", "detection", "classification", "recovery"):
                bus.publish("faults", ev)

    def _publish_status(self):
        bus.publish("events", {"module": self.module, "kind": "status", "run_uid": self.run_uid,
                               "status": self.status.value, "error": self.error})

    def info(self) -> dict:
        with self.lock:
            m = self.mission
            return {"module": self.module, "run_uid": self.run_uid, "status": self.status.value, "speed": self.speed,
                    "t": round(m.t, 3), "error": self.error, "persist_error": self.persist_error,
                    "db_run_id": self.db_run_id, "config": self.config, "wall_time_s": round(self._wall, 2)}


class SessionManager:
    """One live session per module (the interactive Mission Control session)."""

    def __init__(self):
        self.sessions: dict[str, SimulationSession] = {}

    def get(self, module: str) -> SimulationSession | None:
        return self.sessions.get(module)

    def configure(self, module: str, factory, config: dict) -> SimulationSession:
        old = self.sessions.get(module)
        if old:
            old.reset() if old.status != SimStatus.IDLE else None
            old._stop.set()
        s = SimulationSession(module, factory, config)
        self.sessions[module] = s
        return s


manager = SessionManager()
