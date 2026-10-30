"""Decision audit log.

Each significant autonomous decision is recorded *at the moment it is made*
with the evidence available then. The actual outcome is attached later by
``resolve`` when it is observed; explanations are never generated
retrospectively from the outcome.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

_counter = itertools.count(1)


def _jsonable(x: Any) -> Any:
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x


@dataclass
class DecisionEvent:
    module: str
    t: float
    trigger: str
    decision: str
    evidence: dict = field(default_factory=dict)
    estimated_state: dict = field(default_factory=dict)
    uncertainty: dict = field(default_factory=dict)
    fault_classification: dict | None = None
    expected_outcome: dict = field(default_factory=dict)
    actual_outcome: dict | None = None
    safety_status: str = "nominal"
    details: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt-{next(_counter):06d}")

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


class DecisionAudit:
    def __init__(self, module: str):
        self.module = module
        self.events: list[DecisionEvent] = []

    def record(self, **kwargs) -> DecisionEvent:
        ev = DecisionEvent(module=self.module, **kwargs)
        self.events.append(ev)
        return ev

    def resolve(self, event_id: str, actual_outcome: dict) -> None:
        for ev in self.events:
            if ev.event_id == event_id:
                ev.actual_outcome = _jsonable(actual_outcome)
                return

    def open_events(self) -> list[DecisionEvent]:
        return [e for e in self.events if e.actual_outcome is None]

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self.events]

    def dumps(self) -> str:
        return json.dumps(self.to_list())
