"""Autonomous surface operations after landing (ASTRA ROVER ground missions).

The rover deploys beside the landed lander and works through a task list (collect sand, collect a
rock sample, capture images). A mission-level decision layer runs on top of the navigation stack and,
from ROVER-SIDE evidence only, decides to:
  continue           keep working through the task list
  replan             (handled by the navigation stack: newly perceived obstacles block the route)
  return & shelter   drive back to the lander and stay there (severe dust storm, damage, energy)
  resume             leave the lander once the hazard has cleared
Comms loss never stops the rover: every decision here is onboard; the ground only observes.

Default task sites are chosen at configuration time from orbital data (terrain class map + oracle
reachability), exactly as a mission team would pick them before the sol starts.
"""
from __future__ import annotations

import numpy as np

from simulation.rover.terrain import CRES, SIZE_M

TASK_LABEL = {"collect_sand": "Collect sand", "collect_sample": "Collect rock sample", "capture_image": "Capture images"}
TASK_DURATION = {"collect_sand": 20.0, "collect_sample": 25.0, "capture_image": 15.0}
STORM_RETURN_TAU = 3.5      # measured dust optical depth that triggers return & shelter
STORM_CLEAR_TAU = 2.0       # ... and below which the rover resumes
DAMAGE_RETURN_HEALTH = 0.5  # estimated worst-wheel torque capability
ENERGY_MARGIN = 0.85        # fraction of the usable budget the plan may commit
TASK_REACH_M = 1.5          # robotic-arm work envelope around a task site
HOME_REACH_M = 1.2


def _free_cells(terrain) -> np.ndarray:
    from scipy.ndimage import binary_dilation
    hard = (terrain.slope_grid() > 14.0) | binary_dilation(terrain.rock_cells() | (terrain.classes == 3),
                                                            structure=np.ones((5, 5), bool))
    hard[:4, :] = hard[-4:, :] = hard[:, :4] = hard[:, -4:] = True
    return ~hard


def _center(i: int, j: int) -> tuple[float, float]:
    return (-SIZE_M / 2 + (i + 0.5) * CRES, -SIZE_M / 2 + (j + 0.5) * CRES)


def _reachable(terrain, a, b) -> bool:
    from scipy.ndimage import binary_dilation

    from autonomy.planning.astar import astar
    hard = (terrain.slope_grid() > 22.0) | binary_dilation(terrain.rock_cells() | (terrain.classes == 3),
                                                            structure=np.ones((3, 3), bool))
    hard[:2, :] = hard[-2:, :] = hard[:, :2] = hard[:, -2:] = True
    return astar(np.ones(hard.shape), hard, a, b)["found"]


def default_tasks(terrain) -> list[dict]:
    """Sand at the loose-sand patch nearest the route midpoint, a rock sample on bedrock near the first
    third of the route, and a panorama at the far science site."""
    s, t = np.array(terrain.start, float), np.array(terrain.target, float)
    free = _free_cells(terrain)
    out = []

    def pick(cls_ok, anchor, min_from_start=7.0):
        pts = np.array([_center(i, j) for i, j in np.argwhere(free & cls_ok)])
        if not len(pts):
            return None
        for p in pts[np.argsort(np.hypot(*(pts - anchor).T))][:40]:
            if np.hypot(*(p - s)) < min_from_start or any(np.hypot(*(p - np.array([q["x"], q["y"]]))) < 6 for q in out):
                continue
            if _reachable(terrain, tuple(s), tuple(p)):
                return p
        return None

    side = np.array([-(t - s)[1], (t - s)[0]]) / max(np.hypot(*(t - s)), 1e-6)
    sample = pick(terrain.classes == 0, s + (t - s) * 0.33 + side * 5.0)
    if sample is not None:
        out.append({"kind": "collect_sample", "x": float(sample[0]), "y": float(sample[1])})
    sand = pick(terrain.classes == 2, s + (t - s) * 0.6)
    if sand is not None:
        out.append({"kind": "collect_sand", "x": float(sand[0]), "y": float(sand[1])})
    out.append({"kind": "capture_image", "x": float(t[0]), "y": float(t[1])})
    return out


class GroundOps:
    def __init__(self, mission, tasks: list[dict] | None, kinds: list[str] | None = None):
        m = mission
        self.m = m
        t = m.terrain
        home = np.array(t.start, float)
        raw = tasks or [d for d in default_tasks(t) if not kinds or d["kind"] in kinds]
        self.tasks = [{"id": k + 1, "kind": d["kind"], "label": TASK_LABEL.get(d["kind"], d["kind"]),
                       "x": float(d["x"]), "y": float(d["y"]),
                       "duration": float(d.get("duration", TASK_DURATION.get(d["kind"], 20.0))),
                       "status": "pending", "t_done": None} for k, d in enumerate(raw)]
        first = np.array([self.tasks[0]["x"], self.tasks[0]["y"]]) if self.tasks else home + 1
        u = (first - home) / max(np.hypot(*(first - home)), 1e-6)
        self.home = home                                         # parking spot beside the lander
        self.lander = np.clip(home - u * 3.8, -SIZE_M / 2 + 2, SIZE_M / 2 - 2)
        self.mode = "TRANSIT"
        self.idx = 0
        self.work_until: float | None = None
        self.shelter_reason: str | None = None
        self.tau_est = 0.6
        self.comms_lost_since: float | None = None
        self._next_eval = 0.0
        if self.tasks:
            self.tasks[0]["status"] = "active"
            m.goal = first.copy()
        else:
            self.mode = "RETURNING"
            m.goal = home.copy()

    # ------------------------------------------------------------------
    def _decide(self, trigger: str, decision: str, evidence: dict, expected: dict, est: dict):
        m = self.m
        m.audit.record(t=m.t, trigger=trigger, decision=decision, evidence=evidence,
                       estimated_state={k: est[k] for k in ("x", "y", "psi", "v")},
                       uncertainty={"pos_sigma": est["pos_sigma"]}, fault_classification=None,
                       expected_outcome=expected, safety_status=m.safety["action"],
                       details={"mode": self.mode, "tasks": [(x["label"], x["status"]) for x in self.tasks]})
        m._event("decision", f"{decision} — {trigger}")

    def _set_goal(self, xy, reason: str):
        self.m.goal = np.array(xy, float)
        self.m._plan(reason)

    def _pending(self) -> list[dict]:
        return [x for x in self.tasks if x["status"] in ("pending", "active")]

    def _return(self, reason: str, shelter: bool, trigger: str, evidence: dict, est: dict):
        for x in self.tasks:
            if x["status"] == "active":
                x["status"] = "pending"
        self.mode = "RETURNING"
        self.shelter_reason = reason if shelter else None
        self._decide(trigger, "return to lander" + (" and shelter" if shelter else ""), evidence,
                     {"destination": self.home.tolist(), "stay_at_lander": shelter}, est)
        self._set_goal(self.home, f"return to lander: {reason}")

    def _energy_wh(self, pts: list) -> float:
        m = self.m
        dense = []
        for a, b in zip(pts[:-1], pts[1:]):
            n = max(int(np.hypot(b[0] - a[0], b[1] - a[1])), 1)
            dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
        dense.append(tuple(pts[-1]))
        e = m.energy.predict(dense, m.map.slope(), m.map.cam_class, m.cfg.max_speed)["energy_wh"]
        return e * 1.25                                         # detour allowance over the straight line

    # ------------------------------------------------------------------
    def update(self, soc: float, est: dict) -> bool:
        """Called at 10 Hz from the mission control loop. Returns True when the rover must hold still."""
        m = self.m
        here = np.array([est["x"], est["y"]])
        env = m.env
        # rover-side storm evidence: navcam sky-brightness optical depth (noisy, low-pass filtered)
        tau_meas = 0.6 + 4.4 * env["sandstorm"] + m.seeds.stream("tau").normal(0, 0.15)
        self.tau_est += 0.08 * (tau_meas - self.tau_est)
        if not env["comms"] and self.comms_lost_since is None:
            self.comms_lost_since = m.t
            self._decide("downlink lost (no ground acknowledgements)", "continue mission autonomously",
                         {"comms": False}, {"operator_input_required": False}, est)
        elif env["comms"] and self.comms_lost_since is not None:
            m._event("comms", f"Comms restored after {m.t - self.comms_lost_since:.0f} s; buffered telemetry downlinked")
            self.comms_lost_since = None

        # ---- mission-level decisions (1 Hz) ----
        if m.t >= self._next_eval and self.mode not in ("COMPLETE",):
            self._next_eval = m.t + 1.0
            budget = (soc - m.cfg.safety.battery_reserve_soc) * m.cfg.battery_capacity_wh
            health = float(np.min(m.actuator_health_est))
            ev = {"dust_optical_depth": round(self.tau_est, 2), "soc": round(soc, 3), "budget_wh": round(budget, 2),
                  "wheel_health_min": round(health, 2), "comms": env["comms"]}
            if self.mode in ("TRANSIT", "WORKING"):
                if self.tau_est > STORM_RETURN_TAU:
                    self._return("dust storm", True, f"dust optical depth {self.tau_est:.1f} > {STORM_RETURN_TAU}", ev, est)
                elif health < DAMAGE_RETURN_HEALTH:
                    self._return("mobility damage", True, f"worst wheel capability {health:.2f} < {DAMAGE_RETURN_HEALTH}", ev, est)
                else:
                    rest = [(x["x"], x["y"]) for x in self._pending()]
                    need_all = self._energy_wh([tuple(here)] + rest + [tuple(self.home)]) \
                        + sum(x["duration"] for x in self._pending()) * m.energy.p_fixed / 3600.0
                    need_home = self._energy_wh([tuple(here), tuple(self.home)])
                    ev.update(energy_all_tasks_wh=round(need_all, 2), energy_return_wh=round(need_home, 2))
                    if need_home > budget * 0.95:
                        self._return("energy", True, f"return energy {need_home:.1f} Wh ≈ budget {budget:.1f} Wh", ev, est)
                    elif need_all > budget * ENERGY_MARGIN and len(self._pending()) > 0:
                        dropped = self._pending()[-1]
                        dropped["status"] = "skipped"
                        self._decide(f"predicted energy {need_all:.1f} Wh > {ENERGY_MARGIN:.0%} of budget {budget:.1f} Wh",
                                     f"skip '{dropped['label']}' to keep the return reserve", ev,
                                     {"tasks_remaining": len(self._pending())}, est)
                        if not self._pending():
                            self._return("energy", False, "no affordable task left", ev, est)
            elif self.mode in ("SHELTERING", "RETURNING"):
                if self.shelter_reason == "dust storm" and self.tau_est < STORM_CLEAR_TAU and self._pending():
                    self._decide(f"dust optical depth {self.tau_est:.1f} < {STORM_CLEAR_TAU}", "resume mission",
                                 ev, {"next_task": self._pending()[0]["label"]}, est)
                    self.shelter_reason = None
                    self._go_next(est)

        # ---- task execution ----
        if self.mode == "WORKING":
            if m.t >= self.work_until:
                task = self.tasks[self.idx]
                task["status"], task["t_done"] = "done", round(m.t, 1)
                m._event("task", f"{task['label']} complete at ({task['x']:.1f}, {task['y']:.1f})")
                self._advance(est)
            return True
        if self.mode in ("SHELTERING", "COMPLETE"):
            return True
        # a sample site only needs the rover within arm's reach; the parking spot beside the lander a little tighter
        reach = TASK_REACH_M if self.mode == "TRANSIT" else HOME_REACH_M
        if float(np.hypot(*(here - m.goal))) < max(reach, m.cfg.arrival_radius):
            if self.mode == "TRANSIT":
                task = self.tasks[self.idx]
                task["status"] = "working"
                self.mode = "WORKING"
                self.work_until = m.t + task["duration"]
                m._event("task", f"Arrived at task site: {task['label']} ({task['duration']:.0f} s)")
                return True
            if self.mode == "RETURNING":
                if self.shelter_reason:
                    self.mode = "SHELTERING"
                    m._event("task", f"Parked at the lander — sheltering ({self.shelter_reason})")
                    return True
                self.mode = "COMPLETE"
                m._event("task", "All tasks finished; rover parked beside the lander")
                m._finish("mission_complete")
                return True
        return False

    def _advance(self, est):
        self.idx += 1
        self._go_next(est)

    def _go_next(self, est):
        nxt = self._pending()
        if nxt:
            task = nxt[0]
            self.idx = self.tasks.index(task)
            task["status"] = "active"
            self.mode = "TRANSIT"
            self._set_goal((task["x"], task["y"]), f"next task: {task['label']}")
        else:
            self.mode = "RETURNING"
            self.shelter_reason = None
            self._set_goal(self.home, "all tasks done: return to lander")

    def snapshot(self) -> dict:
        return {"mode": self.mode, "tasks": self.tasks, "lander": self.lander.tolist(), "home": self.home.tolist(),
                "goal": self.m.goal.tolist(), "dust_optical_depth": round(self.tau_est, 2),
                "shelter_reason": self.shelter_reason, "comms_lost_since": self.comms_lost_since}

    def summary(self) -> dict:
        return {"tasks_completed": sum(x["status"] == "done" for x in self.tasks), "tasks_total": len(self.tasks),
                "tasks_skipped": sum(x["status"] == "skipped" for x in self.tasks), "final_mode": self.mode,
                "tasks": [(x["label"], x["status"]) for x in self.tasks]}
