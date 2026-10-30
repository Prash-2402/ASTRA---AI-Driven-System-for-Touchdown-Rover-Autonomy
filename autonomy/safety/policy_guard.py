"""Runtime guard for the learned (PPO) landing controller.

A learned policy has only seen its training world; in a different one it can fail *quietly* - its
outputs stay smooth and confident while they become wrong. The guard makes that failure loud:

  1. Out-of-envelope inputs: every observation is compared with the distribution the policy actually
     experienced in training (mean/std per input, measured by machine_learning/evaluation/policy_envelope.py).
     Sustained |z| > z_limit on any input = the policy is extrapolating.
  2. Disagreement with a classical reference: a shadow cascade-PID runs on the same estimate and target.
     A sustained gap between the two commanded accelerations (EWMA) = the policy is doing something the
     physics-based law would not.

Modes: "off" (no guard), "monitor" (flag + log only - shows the quiet failure), "fallback" (flag, log and
hand control to the PID for the rest of the descent).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class GuardConfig:
    z_limit: float = 4.5            # input sigmas outside the training envelope
    ood_hold_s: float = 1.0         # sustained for
    disagree_limit: float = 1.3     # m/s^2, EWMA of |a_ppo - a_pid| (home-world max ~1.05, calibrated)
    disagree_alpha: float = 0.08
    disagree_hold_s: float = 2.0
    min_agl: float = 8.0            # final flare: very low altitude is not judged
    warmup_s: float = 5.0           # navigation filter still converging from its initial uncertainty
    residual_limit: float = 0.8     # m/s^2: EWMA of |commanded - IMU-measured acceleration| (home max 0.57, calibrated)
    residual_alpha: float = 0.04
    residual_hold_s: float = 3.0


def load_envelope(model_path: str | Path) -> dict | None:
    f = Path(model_path).parent / "envelope.json"
    return json.loads(f.read_text()) if f.exists() else None


class PolicyGuard:
    def __init__(self, envelope: dict | None, cfg: GuardConfig | None = None, mode: str = "monitor"):
        self.cfg = cfg or GuardConfig()
        self.mode = mode
        self.mean = np.asarray(envelope["mean"]) if envelope else None
        self.std = np.maximum(np.asarray(envelope["std"]), 1e-3) if envelope else None
        self.names = envelope.get("names") if envelope else None
        # each policy is judged against its OWN normal disagreement with the PID reference in its training
        # world (measured by policy_envelope.py), with a 25 % margin; never below the configured floor
        if envelope and envelope.get("disagreement_max"):
            self.cfg = GuardConfig(**{**self.cfg.__dict__, "disagree_limit": max(self.cfg.disagree_limit, 1.2 * envelope["disagreement_max"])})
        self.ewma = 0.0
        self.res_ewma = 0.0
        self.t_res = 0.0
        self.t_ood = 0.0
        self.t_dis = 0.0
        self.flag: dict | None = None
        self.last = {"z_max": None, "z_input": None, "disagreement": 0.0}

    def check(self, t: float, obs: np.ndarray, a_ppo: np.ndarray, a_pid: np.ndarray, agl: float, dt: float,
              a_meas: np.ndarray | None = None) -> dict | None:
        c = self.cfg
        # 3. dynamics residual: does the vehicle accelerate the way the policy commands? (unmodelled engine,
        #    mass or gravity shows up here even when the policy's inputs look normal)
        if a_meas is not None and t >= c.warmup_s:
            r = float(np.linalg.norm(np.asarray(a_ppo) - np.asarray(a_meas)))
            self.res_ewma = (1 - c.residual_alpha) * self.res_ewma + c.residual_alpha * r
            self.t_res = self.t_res + dt if self.res_ewma > c.residual_limit else 0.0
        z_max, z_in = None, None
        if self.mean is not None:
            z = np.abs((np.asarray(obs) - self.mean) / self.std)
            i = int(np.argmax(z)); z_max = float(z[i]); z_in = self.names[i] if self.names else i
            self.t_ood = self.t_ood + dt if z_max > c.z_limit else 0.0
        d = float(np.linalg.norm(np.asarray(a_ppo) - np.asarray(a_pid)))
        self.ewma = (1 - c.disagree_alpha) * self.ewma + c.disagree_alpha * d
        self.t_dis = self.t_dis + dt if self.ewma > c.disagree_limit else 0.0
        self.last = {"z_max": z_max, "z_input": z_in, "disagreement": self.ewma, "dynamics_residual": self.res_ewma}
        if t < c.warmup_s:
            self.t_ood = self.t_dis = 0.0
        if self.flag or agl < c.min_agl or t < c.warmup_s:
            return None
        reasons = []
        if self.t_ood >= c.ood_hold_s:
            reasons.append(f"input '{z_in}' {z_max:.1f}σ outside the training envelope")
        if self.t_dis >= c.disagree_hold_s:
            reasons.append(f"command differs from the physics-based reference by {self.ewma:.2f} m/s² (sustained)")
        if self.t_res >= c.residual_hold_s:
            reasons.append(f"vehicle does not respond as commanded: {self.res_ewma:.2f} m/s² dynamics residual (sustained)")
        if reasons:
            self.flag = {"t": round(t, 2), "reasons": reasons, "z_max": z_max, "z_input": z_in,
                         "disagreement": self.ewma, "mode": self.mode, "action": "handed control to PID" if self.mode == "fallback" else "flag only"}
            return self.flag
        return None
