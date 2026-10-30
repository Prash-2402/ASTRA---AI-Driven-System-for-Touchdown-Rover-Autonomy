"""Anomaly detection, fault classification, response selection and recovery verification.

These are four separate components:
  AnomalyDetector   - "is something wrong?" (per-evidence thresholds with persistence)
  FaultClassifier   - "which of the four classes, with what confidence?" (multi-label)
  AstraResponseSelector - fault-specific adaptive response (ASTRA only)
  RecoveryVerifier  - "did the response restore progress / evidence?"
An EKF residual is treated as evidence of model mismatch, never as proof of a specific fault.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from autonomy.fault_detection.evidence import Evidence
from shared.enums import FaultType as FT


@dataclass
class DetectorConfig:
    """Configurable thresholds for raw evidence anomaly flagging.
    
    Attributes:
        stale_s: Maximum allowable age of sensor packets before flagging staleness.
        lidar_corruption: Fraction of ground-ring returns inconsistent with ground plane geometry.
        visloc_nis: EKF Normalized Innovation Squared threshold for visual localisation divergence.
        wheel_residual: Isolated wheel speed tracking residual (speed error vs median of peers).
        battery_ratio: Ratio of measured electrical power to mechanical model prediction.
        inconsistency: Semantic perception inconsistency threshold (camera vs lidar traversability).
        inconsistency_min_checked: Minimum number of mapped cells before evaluating consistency.
        persistence: Number of consecutive control ticks a test must pass to engage active flag.
    """
    stale_s: float = 1.2
    lidar_corruption: float = 0.45
    visloc_nis: float = 25.0
    wheel_residual: float = 0.18
    battery_ratio: float = 1.45
    inconsistency: float = 0.18
    inconsistency_min_checked: int = 25
    persistence: int = 5                   # consecutive control ticks


class AnomalyDetector:
    def __init__(self, cfg: DetectorConfig):
        self.cfg = cfg
        self.counts: dict[str, int] = {}
        self.active: dict[str, float] = {}     # feature -> first flagged time

    def update(self, ev: Evidence) -> dict:
        c = self.cfg
        tests = {
            "lidar_stale": ev.lidar_stale > c.stale_s,
            "camera_stale": ev.camera_stale > c.stale_s,
            "lidar_corruption": ev.lidar_corruption > c.lidar_corruption,
            "visloc_nis": ev.visloc_nis > c.visloc_nis,
            "wheel_residual": float(np.max(ev.wheel_residual)) > c.wheel_residual,
            "battery_ratio": ev.battery_ratio > c.battery_ratio,
            "perception_inconsistency": ev.perception_checked >= c.inconsistency_min_checked
                                        and ev.perception_inconsistency > c.inconsistency,
        }
        for k, v in tests.items():
            self.counts[k] = self.counts.get(k, 0) + 1 if v else 0
            if self.counts[k] >= c.persistence and k not in self.active:
                self.active[k] = ev.t
            if self.counts[k] == 0 and k in self.active:
                del self.active[k]
        return {"anomaly": bool(self.active), "flags": dict(self.active)}


class FaultClassifier:
    """Evidence-pattern scoring -> per-class score in [0,1] -> confidence; multi-label for paired faults."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def classify(self, ev: Evidence, anomaly: dict) -> dict:
        flags = anomaly["flags"]
        s = {
            FT.SENSOR_DROPOUT.value: max(min(max(ev.lidar_stale, ev.camera_stale) / 2.0, 1.0),
                                         float(np.clip((ev.lidar_corruption - 0.3) / 0.3, 0, 1))),
            FT.TERRAIN_MISCLASSIFICATION.value: 0.0 if ev.perception_checked < 25 else
                float(np.clip((ev.perception_inconsistency - 0.08) / 0.15, 0, 1)),
            FT.POWER_DRAIN.value: float(np.clip((ev.battery_ratio - 1.15) / 0.6, 0, 1)),
            FT.ACTUATOR_DEGRADATION.value: float(np.clip(np.max(ev.wheel_residual) / 0.35, 0, 1)
                                                 * np.clip((1 - np.min(ev.wheel_capability)) / 0.4 + 0.3, 0, 1)),
        }
        # dropout explains perception inconsistency (no fresh data) -> do not double count
        if s[FT.SENSOR_DROPOUT.value] > 0.5:
            s[FT.TERRAIN_MISCLASSIFICATION.value] *= 0.3
        total = sum(s.values()) + 0.25
        conf = {k: v / total for k, v in s.items()}
        labels = [k for k, v in s.items() if v >= self.threshold]
        uncertain = anomaly["anomaly"] and (not labels or max(conf.values()) < 0.45)
        wheel = int(np.argmax(ev.wheel_residual)) if FT.ACTUATOR_DEGRADATION.value in labels else None
        return {"labels": labels, "scores": {k: round(v, 3) for k, v in s.items()},
                "confidence": {k: round(v, 3) for k, v in conf.items()}, "uncertain": bool(uncertain),
                "degraded_wheel": wheel}


@dataclass
class Response:
    speed_factor: float = 1.0
    weights: dict = field(default_factory=dict)
    hold: bool = False
    replan: bool = False
    actuator_health: np.ndarray | None = None
    gentle_turns: bool = False
    energy_update: dict | None = None
    description: str = "nominal"


class AstraResponseSelector:
    """Fault-specific, uncertainty-aware adaptive responses."""

    def select(self, cls: dict, ev: Evidence, est: dict) -> Response:
        labels = set(cls["labels"])
        r = Response()
        desc = []
        if cls["uncertain"]:
            r.speed_factor = 0.5
            r.weights.update(w_unknown=1.0, w_slope=3.0, inflation_m=1.1)
            r.replan = True
            desc.append("uncertain classification -> conservative: half speed, wider margins, replan")
        if FT.SENSOR_DROPOUT.value in labels:
            sig = est["pos_sigma"]
            # keep moving along the mapped route while the estimate is trustworthy; hold otherwise
            r.speed_factor = min(r.speed_factor, 0.35 if sig < 0.45 else 0.0)
            r.hold = sig >= 0.45
            r.weights.update(w_uncertainty=2.0, w_unknown=2.0)
            desc.append(f"sensor dropout -> dead-reckon on mapped route at reduced speed (σ={sig:.2f} m)"
                        + ("; hold for relocalisation" if r.hold else ""))
        if FT.TERRAIN_MISCLASSIFICATION.value in labels:
            r.weights.update(camera_hard=False)
            r.replan = True
            desc.append("terrain misclassification -> geometry-dominant traversability (lidar overrides camera), replan")
        if FT.POWER_DRAIN.value in labels:
            r.energy_update = {"p_fixed": ev.p_fixed_est}
            r.weights.update(w_energy=1.5, w_class=1.5)
            r.speed_factor = min(r.speed_factor, 1.0)      # fixed loads dominate: slower costs more energy
            r.replan = True
            desc.append(f"power drain (est. fixed load {ev.p_fixed_est:.0f} W) -> energy-optimal route at efficient speed")
        if FT.ACTUATOR_DEGRADATION.value in labels:
            health = np.clip(ev.wheel_capability, 0.1, 1.0)
            r.actuator_health = health
            r.weights.update(w_actuator=3.0, max_slope_deg=16.0)
            r.speed_factor = min(r.speed_factor, 0.75)
            r.gentle_turns = True       # skid-steer turns need the most torque: avoid high curvature / pivots
            r.replan = True
            desc.append(f"actuator degradation on wheel {cls['degraded_wheel']} (capability {float(np.min(health)):.2f})"
                        " -> torque reallocation, low-curvature tracking, slope/sand-averse route, 75% speed")
        r.description = "; ".join(desc) if desc else "nominal"
        return r


class RecoveryVerifier:
    def __init__(self, window_s: float = 25.0, min_progress: float = 1.5):
        self.window_s, self.min_progress = window_s, min_progress
        self.pending: dict[str, dict] = {}

    def start(self, key: str, t: float, dist_to_goal: float, event_id: str):
        self.pending[key] = {"t0": t, "d0": dist_to_goal, "event_id": event_id}

    def check(self, t: float, dist_to_goal: float, halted: bool) -> list[tuple[str, dict]]:
        done = []
        for k, p in list(self.pending.items()):
            if t - p["t0"] >= self.window_s:
                progress = p["d0"] - dist_to_goal
                ok = progress >= self.min_progress and not halted
                done.append((p["event_id"], {"recovered": ok, "progress_m": round(progress, 2),
                                             "window_s": self.window_s, "verified_at": round(t, 2)}))
                del self.pending[k]
        return done


class ClassificationDebouncer:
    """Hysteresis on classification labels: a label set must persist `engage_s` before it is acted on,
    and a return to nominal must persist `release_s`. Prevents response flapping on transient evidence."""

    def __init__(self, engage_s: float = 1.0, release_s: float = 3.0):
        self.engage_s, self.release_s = engage_s, release_s
        self.stable: frozenset = frozenset()
        self.candidate: frozenset = frozenset()
        self.since = 0.0

    def update(self, t: float, labels: set) -> frozenset:
        lab = frozenset(labels)
        if lab != self.candidate:
            self.candidate, self.since = lab, t
        hold = self.release_s if not lab else self.engage_s
        if self.candidate != self.stable and t - self.since >= hold:
            self.stable = self.candidate
        return self.stable
