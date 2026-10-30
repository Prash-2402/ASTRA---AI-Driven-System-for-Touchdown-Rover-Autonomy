"""Landing-site assessment and autonomous diversion planning (perceived terrain only)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from autonomy.framework import CandidateAction, DecisionEngine
from autonomy.planning.landing_perception import PerceivedHazardMap
from simulation.touchdown.environment import G0


@dataclass
class SiteCriteria:
    footprint_radius: float = 2.2
    max_slope_deg: float = 10.0
    max_rock_height: float = 0.35
    max_relief: float = 0.30           # plane-fit residual std [m]
    uncertainty_k: float = 2.0         # margin = k * sigma_pos_h


@dataclass
class SiteAssessment:
    x: float
    y: float
    covered: bool
    safe: bool
    score: float
    slope_deg: float | None = None
    max_rock_h: float = 0.0
    nearest_rock_m: float | None = None
    relief_m: float | None = None
    margin_m: float = 0.0
    reasons: list | None = None

    def to_dict(self):
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


class LandingSiteAssessor:
    def __init__(self, criteria: SiteCriteria | None = None):
        self.c = criteria or SiteCriteria()

    def assess(self, x: float, y: float, hmap: PerceivedHazardMap, sigma_pos_h: float) -> SiteAssessment:
        c = self.c
        margin = c.uncertainty_k * sigma_pos_h
        r = c.footprint_radius + margin
        reasons = []
        if not hmap.covered(x, y, r):
            return SiteAssessment(x, y, False, False, 0.0, margin_m=margin, reasons=["not yet sensed"])
        pts = hmap.patch(x, y, max(r, 4.0))
        A = np.c_[pts[:, 0], pts[:, 1], np.ones(len(pts))]
        coef, *_ = np.linalg.lstsq(A, pts[:, 2], rcond=None)
        slope = float(np.degrees(np.arctan(np.hypot(coef[0], coef[1]))))
        # roughness corrected for known lidar height noise (otherwise the metric measures the sensor, not terrain)
        resid_var = float(np.mean((pts[:, 2] - A @ coef) ** 2))
        noise_var = float(np.mean(pts[:, 3] ** 2)) if pts.shape[1] > 3 else 0.0
        relief = float(np.sqrt(max(resid_var - noise_var, 0.0)))
        max_h, nearest = 0.0, None
        for rx, ry, rr, rh in hmap.rocks:
            d = np.hypot(rx - x, ry - y) - rr
            if nearest is None or d < nearest:
                nearest = float(d)
            if d < r and rh > max_h:
                max_h = float(rh)
        if slope > c.max_slope_deg: reasons.append(f"slope {slope:.1f}° > {c.max_slope_deg}°")
        if max_h > c.max_rock_height: reasons.append(f"rock {max_h:.2f} m in footprint+margin")
        if relief > c.max_relief: reasons.append(f"relief {relief:.2f} m")
        safe = not reasons
        prox = 0.0 if nearest is None else np.exp(-max(nearest, 0) / 4.0)
        score = 1.0 - 0.45 * min(slope / c.max_slope_deg, 1.5) - 0.35 * min(max_h / c.max_rock_height, 1.5) \
            - 0.1 * min(relief / c.max_relief, 1.5) - 0.1 * prox
        return SiteAssessment(x, y, True, safe, float(score), slope, max_h, nearest, relief, margin, reasons)


@dataclass
class DiversionConfig:
    max_divert_m: float = 180.0
    grid_spacing: float = 6.0
    fuel_reserve_kg: float = 25.0
    tilt_max_deg: float = 30.0
    lateral_accel_margin: float = 0.6
    max_touchdown_error: float = 4.0
    w_safety: float = 0.6
    w_distance: float = 0.25
    w_fuel: float = 0.15


class DiversionDecisionEngine(DecisionEngine):
    def __init__(self, cfg: DiversionConfig):
        self.cfg = cfg

    def evaluate(self, candidates: list[CandidateAction], context: dict) -> CandidateAction | None:
        feas = [c for c in candidates if c.feasible]
        if not feas:
            return None
        return max(feas, key=lambda c: c.score)


class DiversionPlanner:
    """Generate -> assess -> check fuel / authority -> predict -> select."""

    def __init__(self, cfg: DiversionConfig, assessor: LandingSiteAssessor, predictor, vehicle: dict):
        self.cfg = cfg
        self.assessor = assessor
        self.predictor = predictor
        self.vehicle = vehicle      # dry_mass, isp, max_thrust
        self.engine = DiversionDecisionEngine(cfg)

    def plan(self, est: dict, current_target: np.ndarray, hmap: PerceivedHazardMap, sigma_h: float,
             gravity: float) -> dict:
        cfg = self.cfg
        p, v = est["p"], est["v"]
        agl = est["agl"]
        fuel = est["fuel"]
        m = self.vehicle["dry_mass"] + fuel
        a_lat_max = gravity * np.tan(np.radians(cfg.tilt_max_deg)) * cfg.lateral_accel_margin
        # 1) candidate generation around the current target within the sensed region
        cands = []
        rng = np.arange(-cfg.max_divert_m, cfg.max_divert_m + 1e-9, cfg.grid_spacing)
        for dx in rng:
            for dy in rng:
                if dx * dx + dy * dy > cfg.max_divert_m ** 2:
                    continue
                cands.append((current_target[0] + dx, current_target[1] + dy))
        assessed = [self.assessor.assess(x, y, hmap, sigma_h) for x, y in cands]
        safe = sorted([a for a in assessed if a.safe], key=lambda a: -a.score)[:25]
        # time-to-go estimate from the nominal prediction (used for authority check)
        nominal = self.predictor.predict(np.r_[p, v], target=np.r_[current_target[:2], 0.0], fuel=fuel, gravity=gravity)
        t_go = max(nominal["time_to_go"], 1.0)
        actions = []
        for a in safe:
            tgt = np.array([a.x, a.y, 0.0])
            d_vec = tgt[:2] - p[:2]
            d = float(np.linalg.norm(d_vec))
            # control authority: accelerate-decelerate manoeuvre in t_go
            v_along = float(v[:2] @ (d_vec / max(d, 1e-6)))
            a_req = 4.0 * abs(d - v_along * t_go / 2.0) / t_go ** 2
            act = CandidateAction(name="divert", params={"x": a.x, "y": a.y})
            act.predicted["a_req"] = a_req
            act.predicted["assessment"] = a.to_dict()
            if a_req > a_lat_max:
                act.feasible = False
                act.reasons.append(f"lateral accel {a_req:.2f} > {a_lat_max:.2f} m/s²")
            else:
                pred = self.predictor.predict(np.r_[p, v], target=np.r_[a.x, a.y, 0.0], fuel=fuel, gravity=gravity)
                err = float(np.hypot(pred["touchdown_point"][0] - a.x, pred["touchdown_point"][1] - a.y))
                act.predicted.update({"touchdown_error": err, "fuel_used": pred["fuel_used"],
                                      "time_to_go": pred["time_to_go"],
                                      "touchdown_velocity": pred["touchdown_velocity"]})
                fuel_margin = fuel - pred["fuel_used"] - cfg.fuel_reserve_kg
                act.predicted["fuel_margin"] = fuel_margin
                if fuel_margin < 0:
                    act.feasible = False; act.reasons.append("insufficient fuel reserve")
                if err > cfg.max_touchdown_error:
                    act.feasible = False; act.reasons.append(f"predicted miss {err:.1f} m")
                act.score = (cfg.w_safety * a.score + cfg.w_distance * (1 - d / cfg.max_divert_m)
                             + cfg.w_fuel * np.clip(fuel_margin / max(fuel, 1), 0, 1))
            actions.append(act)
        chosen = self.engine.evaluate(actions, {})
        return {"candidates_total": len(cands), "candidates_sensed": sum(a.covered for a in assessed),
                "candidates_safe": len([a for a in assessed if a.safe]),
                "evaluated": [{"x": c.params["x"], "y": c.params["y"], "feasible": c.feasible,
                               "score": round(c.score, 3), "reasons": c.reasons,
                               "predicted": {k: v for k, v in c.predicted.items() if k != "assessment"}}
                              for c in actions[:15]],
                "selected": None if chosen is None else {"x": chosen.params["x"], "y": chosen.params["y"],
                                                         "score": chosen.score, "predicted": chosen.predicted},
                "a_lat_max": a_lat_max, "t_go_nominal": t_go}

    def least_bad(self, est: dict, current_target, hmap, sigma_h) -> dict | None:
        """Abort response: best-scoring sensed point within immediately reachable range."""
        p = est["p"]
        best = None
        for dx in np.arange(-40, 41, 4.0):
            for dy in np.arange(-40, 41, 4.0):
                x, y = p[0] + dx, p[1] + dy
                a = self.assessor.assess(x, y, hmap, sigma_h)
                if a.covered and (best is None or a.score > best.score):
                    best = a
        return None if best is None else best.to_dict()
