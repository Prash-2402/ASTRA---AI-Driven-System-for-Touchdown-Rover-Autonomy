"""Sensor-health monitor: catches sensors that keep reporting but are slowly wrong ("lying sensors").

A dead sensor is easy: it goes silent. A drifting sensor keeps producing plausible readings, each of which
passes the EKF's per-sample chi-square gate. What gives it away is *persistence*: an honest sensor's
normalised innovations e = y / sqrt(S) scatter on both sides of zero; a drifting one keeps leaning the
same way. Two independent tests:

1. Two-sided CUSUM on each axis of each monitored channel's normalised innovation (Page 1954):
       g+ = max(0, g+ + e - k)      g- = max(0, g- - e - k)
   k (drift allowance) absorbs honest noise; g crosses h only when the mean shifts. h is calibrated on
   fault-free missions (see experiments/runners/sensor_drift_dataset.py) for zero false alarms.
2. Cross-sensor consistency: the radar altimeter and the terrain-relative-navigation (TRN) fix both
   measure height above terrain (via the onboard DEM). Their normalised disagreement gets its own CUSUM;
   it tells *which* of the pair is lying (the one whose own CUSUM is also high).

Status per channel: OK -> SUSPECT (own CUSUM above h) -> ISOLATED (confirmed by the cross-check, or own
CUSUM above 1.6 h). An isolated channel is excluded from the EKF; the monitor keeps watching it.
Only rover-/lander-side quantities are used. Truth is carried along solely for the chart buffer.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

MONITORED = ("altimeter", "position", "velocimeter")
DECIMATE = {"altimeter": 6, "position": 1, "velocimeter": 3}     # samples kept for charts: ~3.3, 2, 3.3 Hz


@dataclass
class HealthConfig:
    k: float = 0.5                   # CUSUM drift allowance (in innovation sigmas)
    h: dict = field(default_factory=lambda: {"altimeter": 14.0, "position": 14.0, "velocimeter": 14.0})
    h_cross: float = 14.0
    isolate_factor: float = 1.6      # own-CUSUM-only isolation threshold multiple
    buffer: int = 600                # samples kept per channel for live charts


class _Cusum:
    def __init__(self, dims: int, k: float):
        self.k = k
        self.gp = np.zeros(dims)
        self.gn = np.zeros(dims)

    def update(self, e: np.ndarray) -> float:
        self.gp = np.maximum(0.0, self.gp + e - self.k)
        self.gn = np.maximum(0.0, self.gn - e - self.k)
        return float(max(self.gp.max(), self.gn.max()))

    @property
    def value(self) -> float:
        return float(max(self.gp.max(), self.gn.max()))

    @property
    def sign(self) -> int:
        return 1 if self.gp.max() >= self.gn.max() else -1


class SensorHealthMonitor:
    def __init__(self, cfg: HealthConfig | None = None):
        self.cfg = cfg or HealthConfig()
        dims = {"altimeter": 1, "position": 3, "velocimeter": 3}
        self.cusum = {c: _Cusum(dims[c], self.cfg.k) for c in MONITORED}
        self.cross = _Cusum(1, self.cfg.k)
        self.status = {c: "OK" for c in MONITORED}
        self.first: dict[str, dict] = {}            # channel -> {"suspect": t, "isolated": t}
        self.buf = {c: deque(maxlen=self.cfg.buffer) for c in MONITORED}
        self.cross_buf = deque(maxlen=self.cfg.buffer)
        self._last_alt = None
        self._last_pos = None
        self.events: list[dict] = []
        self.innov_mean = {c: 0.0 for c in MONITORED}
        self.grace: dict[str, float] = {}
        self._n = {c: 0 for c in MONITORED}

    # ------------------------------------------------------------------
    def update(self, t: float, channel: str, innovation, s_diag, meas, truth) -> list[dict]:
        """Feed one EKF innovation. Returns newly raised status changes."""
        if channel not in self.cusum:
            return []
        y = np.atleast_1d(np.asarray(innovation, float))
        s = np.sqrt(np.maximum(np.atleast_1d(np.asarray(s_diag, float)), 1e-9))
        e = y / s
        g = self.cusum[channel].update(e)
        if t < self.grace.get(channel, -1.0):      # honest twin while the estimate re-converges after an isolation
            self.cusum[channel].gp[:] = 0; self.cusum[channel].gn[:] = 0; g = 0.0
        lead = int(np.argmax(np.abs(e))) if channel == "altimeter" else 2   # vertical axis for vector channels
        self.innov_mean[channel] = 0.97 * self.innov_mean[channel] + 0.03 * float(e[lead])
        self._n[channel] += 1
        if self._n[channel] % DECIMATE[channel] == 0:               # chart buffer covers ~3 minutes
            m = np.atleast_1d(meas); tr = np.atleast_1d(truth)
            self.buf[channel].append((round(t, 2), round(float(m[lead]), 3), round(float(tr[lead]), 3),
                                      round(float(e[lead]), 3), round(g, 2)))
        return self._evaluate(t, channel)

    def cross_check(self, t: float, alt_meas: float, alt_sigma: float, trn_height: float, trn_sigma: float) -> None:
        """Altimeter vs TRN-derived height above terrain (independent sensors, same physical quantity)."""
        r = (alt_meas - trn_height) / np.sqrt(alt_sigma ** 2 + trn_sigma ** 2)
        g = self.cross.update(np.array([r]))
        self.cross_buf.append((round(t, 2), round(float(r), 3), round(g, 2)))

    def _vertical(self, channel: str) -> tuple[float, int]:
        cu = self.cusum[channel]; i = 0 if channel == "altimeter" else 2
        return (float(cu.gp[i]), 1) if cu.gp[i] >= cu.gn[i] else (float(cu.gn[i]), -1)

    def _common_cause(self, t: float) -> dict | None:
        """Altimeter and TRN agree with EACH OTHER (low cross-check) but both disagree with the estimate in
        the same direction: neither is lying - the estimate itself was dragged by the velocity source."""
        c = self.cfg
        if self.status["velocimeter"] == "ISOLATED":
            return None
        (ga, sa), (gp, sp) = self._vertical("altimeter"), self._vertical("position")
        if ga > 0.6 * c.h["altimeter"] and gp > 0.6 * c.h["position"] and sa == sp and self.cross.value < 0.5 * c.h_cross:
            self.status["velocimeter"] = "ISOLATED"
            self.first.setdefault("velocimeter", {}).update({"suspect": t, "isolated": t})
            ev = {"t": t, "channel": "velocimeter", "status": "ISOLATED", "cusum": self.cusum["velocimeter"].value,
                  "threshold": c.h["velocimeter"], "cross_check": self.cross.value, "cross_threshold": c.h_cross,
                  "confirmed_by": f"common cause: altimeter (CUSUM {ga:.1f}) and TRN (CUSUM {gp:.1f}) agree with each "
                                  f"other (cross {self.cross.value:.1f}) but both disagree with the estimate the same way",
                  "direction": "positive" if sa > 0 else "negative"}
            for ch in ("altimeter", "position"):          # exonerate the honest pair
                self.cusum[ch].gp[:] = 0; self.cusum[ch].gn[:] = 0
                if self.status[ch] == "SUSPECT":
                    self.status[ch] = "OK"
            return ev
        return None

    def _evaluate(self, t: float, channel: str) -> list[dict]:
        c = self.cfg
        h = c.h[channel]
        out = []
        cc = self._common_cause(t)
        if cc:
            self.events.append(cc)
            return [cc]
        g = self.cusum[channel].value
        st = self.status[channel]
        if st == "OK" and g > h:
            self.status[channel] = "SUSPECT"
            self.first.setdefault(channel, {})["suspect"] = t
            out.append({"t": t, "channel": channel, "status": "SUSPECT", "cusum": g, "threshold": h,
                        "direction": "positive" if self.cusum[channel].sign > 0 else "negative"})
        if self.status[channel] == "SUSPECT":
            # altimeter / TRN need the cross-check to name them as the liar (otherwise the common-cause test
            # above gets the chance to clear them); the velocimeter has no independent twin
            cross_ok = channel in ("altimeter", "position") and self.cross.value > c.h_cross \
                and self._is_liar(channel)
            # opposite pull: the liar drags the estimate, so its honest twin leans the OTHER way
            # (a common cause would make both lean the SAME way)
            pull_ok = False
            if channel in ("altimeter", "position") and not cross_ok:
                other = "position" if channel == "altimeter" else "altimeter"
                (g_own, s_own), (g_oth, s_oth) = self._vertical(channel), self._vertical(other)
                pull_ok = g_own > 3.0 * h and s_oth == -s_own and g_oth > 0.2 * c.h[other]
            if cross_ok or pull_ok or (channel == "velocimeter" and g > c.isolate_factor * h):
                if channel in ("altimeter", "position"):      # the honest twin was only reacting to the liar
                    other = "position" if channel == "altimeter" else "altimeter"
                    self.cusum[other].gp[:] = 0; self.cusum[other].gn[:] = 0
                    if self.status[other] == "SUSPECT":
                        self.status[other] = "OK"
                    self.cross.gp[:] = 0; self.cross.gn[:] = 0
                    self.grace[other] = t + 25.0
                self.status[channel] = "ISOLATED"
                self.first.setdefault(channel, {})["isolated"] = t
                out.append({"t": t, "channel": channel, "status": "ISOLATED", "cusum": g, "threshold": h,
                            "cross_check": self.cross.value, "cross_threshold": c.h_cross,
                            "confirmed_by": ("altimeter/TRN cross-check" if cross_ok else
                                             "opposite pull on the independent twin sensor" if pull_ok else f"CUSUM > {c.isolate_factor}·h"),
                            "direction": "positive" if self.cusum[channel].sign > 0 else "negative"})
        self.events.extend(out)
        return out

    def _is_liar(self, channel: str) -> bool:
        """Of the altimeter/TRN pair, the liar is the one whose own CUSUM is higher relative to its threshold."""
        other = "position" if channel == "altimeter" else "altimeter"
        return self.cusum[channel].value / self.cfg.h[channel] >= self.cusum[other].value / self.cfg.h[other]

    def isolated(self, channel: str) -> bool:
        return self.status.get(channel) == "ISOLATED"

    def snapshot(self) -> dict:
        return {"channels": {c: {"status": self.status[c], "cusum": round(self.cusum[c].value, 2),
                                 "threshold": self.cfg.h[c], "mean_innovation": round(self.innov_mean[c], 3),
                                 "first": self.first.get(c)} for c in MONITORED},
                "cross": {"cusum": round(self.cross.value, 2), "threshold": self.cfg.h_cross},
                "k": self.cfg.k, "isolate_factor": self.cfg.isolate_factor,
                "series": {c: list(self.buf[c]) for c in MONITORED},
                "cross_series": list(self.cross_buf), "events": self.events[-10:]}
