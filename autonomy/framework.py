"""Unified mission-intelligence framework.

Sense -> Estimate -> Predict -> Decide -> Act -> Verify -> Adapt.

This module defines the *interfaces* shared by ASTRA TOUCHDOWN and ASTRA ROVER.
It deliberately contains no physics and no controller: each module supplies
its own model-specific implementation. What is shared is the contract for
state bookkeeping, prediction, decision, independent safety and auditing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class TimestampedEstimate:
    t: float
    mean: np.ndarray
    covariance: np.ndarray
    labels: list[str]

    def sigma(self) -> np.ndarray:
        return np.sqrt(np.clip(np.diag(self.covariance), 0.0, None))

    def to_dict(self) -> dict:
        return {"t": self.t, "labels": self.labels, "mean": self.mean.tolist(), "sigma": self.sigma().tolist()}


class StateObservationManager:
    """Keeps the latest estimate, sensor health and mission context with timestamps."""

    def __init__(self):
        self.estimate: TimestampedEstimate | None = None
        self.sensor_health: dict[str, dict[str, Any]] = {}
        self.context: dict[str, Any] = {}

    def update_estimate(self, est: TimestampedEstimate) -> None:
        self.estimate = est

    def update_sensor(self, channel: str, t: float, valid: bool) -> None:
        h = self.sensor_health.setdefault(channel, {"last_valid_t": None, "valid_count": 0, "invalid_count": 0})
        if valid:
            h["last_valid_t"] = t
            h["valid_count"] += 1
        else:
            h["invalid_count"] += 1

    def staleness(self, channel: str, t: float) -> float:
        h = self.sensor_health.get(channel)
        if not h or h["last_valid_t"] is None:
            return float("inf")
        return t - h["last_valid_t"]

    def snapshot(self, t: float) -> dict:
        return {
            "estimate": self.estimate.to_dict() if self.estimate else None,
            "sensor_staleness": {k: (None if v["last_valid_t"] is None else round(t - v["last_valid_t"], 3))
                                 for k, v in self.sensor_health.items()},
            "context": self.context,
        }


class PredictionEngine(ABC):
    """Rolls a module's own physical model forward from an estimated state."""

    @abstractmethod
    def predict(self, state: np.ndarray, horizon_s: float, **kwargs) -> dict: ...


@dataclass
class CandidateAction:
    name: str
    params: dict = field(default_factory=dict)
    predicted: dict = field(default_factory=dict)
    feasible: bool = True
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


class DecisionEngine(ABC):
    """Scores feasible actions against objective, safety, resources, uncertainty and health."""

    @abstractmethod
    def evaluate(self, candidates: list[CandidateAction], context: dict) -> CandidateAction | None: ...


class SafetySupervisorBase(ABC):
    """Independent hard-constraint monitor. Must not import or call the planner."""

    @abstractmethod
    def check(self, observation: dict) -> dict: ...
