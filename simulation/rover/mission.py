"""ASTRA ROVER mission runner.

Rates: physics 240 Hz (PyBullet) | IMU 50 Hz | odometry 20 Hz | lidar 5 Hz | camera 2 Hz | visloc 1 Hz
       battery 2 Hz | control/decision 10 Hz | telemetry 5 Hz
Controllers: 'astra' (fault-specific adaptive response) or 'fsm' (fixed-rule baseline).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import numpy as np

from autonomy.control.pure_pursuit import PurePursuit, PurePursuitConfig
from autonomy.decision.audit import DecisionAudit
from autonomy.decision.fsm_baseline import FSMBaseline, FSMConfig
from autonomy.estimation.rover_ekf import LABELS, RoverEKF
from autonomy.fault_detection.detector import (AnomalyDetector, AstraResponseSelector, ClassificationDebouncer,
                                               DetectorConfig, FaultClassifier, RecoveryVerifier, Response)
from autonomy.fault_detection.evidence import Evidence, EvidenceBuilder
from autonomy.framework import StateObservationManager, TimestampedEstimate
from autonomy.planning.astar import astar, path_blocked
from autonomy.planning.rover_perception import RoverPerceivedMap, cell_of, orbital_prior
from autonomy.planning.traversability import CostWeights, build_costmap
from autonomy.prediction.rover_energy import RouteEnergyModel
from autonomy.safety.rover_supervisor import RoverSafetySupervisor, SafetyConfig
from simulation.common.rng import SeedManager
from simulation.rover.faults import FaultInjector, FaultSpec
from simulation.rover.power import Battery, BatteryConfig
from simulation.rover.sensors import RoverSensorConfig, RoverSensors, yaw_of
from simulation.rover.terrain import CLASS_FRICTION, CLASS_ROLLING_RESISTANCE, HRES, generate
from simulation.rover.urdf import RoverGeometry
from simulation.rover.world import RoverWorld, WorldConfig

CONTROL_DT = 0.1
TELEMETRY_DT = 0.2


@dataclass
class RoverConfig:
    seed: int = 7
    terrain: int = 1
    controller: str = "astra"
    start: list | None = None
    target: list | None = None
    rover_mass: float | None = None          # total mass; chassis mass adjusted
    initial_battery: float = 0.8
    battery_capacity_wh: float = 20.0
    wheel_torque: float = 8.0          # per-wheel motor limit; ~2-3x the demand of 15 deg slopes in sand
    max_speed: float = 0.4
    duration: float = 600.0
    physics_hz: float = 120.0          # convergence-checked against 240 Hz (docs/ROVER_PHYSICS.md)
    arrival_radius: float = 0.6
    success_radius: float = 1.5
    faults: list = field(default_factory=list)
    ground_ops: bool = False           # autonomous surface operations: task list + return to lander
    tasks: list = field(default_factory=list)
    task_kinds: list = field(default_factory=list)   # subset of default task kinds (empty = all)
    sensors: RoverSensorConfig = field(default_factory=RoverSensorConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)

    @staticmethod
    def from_dict(d: dict) -> "RoverConfig":
        c = RoverConfig()
        for k, v in (d or {}).items():
            if v is None:
                continue
            if k in ("sensors", "safety", "detector") and isinstance(v, dict):
                obj = getattr(c, k)
                for kk, vv in v.items():
                    setattr(obj, kk, vv)
            elif hasattr(c, k):
                setattr(c, k, v)
        return c

    def to_dict(self) -> dict:
        return asdict(self)


class RoverMission:
    def __init__(self, cfg: RoverConfig):
        self.cfg = cfg
        if cfg.ground_ops or cfg.tasks:
            # a whole sol of surface work is budgeted, not the 20 Wh slice of a single benchmark traverse
            cfg.battery_capacity_wh = max(cfg.battery_capacity_wh, 60.0)
            cfg.max_speed = max(cfg.max_speed, 0.6)
        self.seeds = SeedManager(cfg.seed)
        self.terrain = generate(cfg.terrain)
        if cfg.ground_ops or cfg.tasks:
            self._thin_rocks()
        if cfg.start: self.terrain.start = tuple(cfg.start)
        if cfg.target: self.terrain.target = tuple(cfg.target)
        geom = RoverGeometry()
        if cfg.rover_mass:
            geom.chassis_mass = max(cfg.rover_mass - (geom.total_mass - geom.chassis_mass), 5.0)
        sx, sy = self.terrain.start
        tx, ty = self.terrain.target
        heading0 = float(np.arctan2(ty - sy, tx - sx))
        self.world = RoverWorld(self.terrain, WorldConfig(physics_hz=cfg.physics_hz, geometry=geom), start_heading=heading0)
        self.geom = geom
        self.dt = self.world.dt
        self.battery = Battery(BatteryConfig(capacity_wh=cfg.battery_capacity_wh, initial_soc=cfg.initial_battery,
                                             reserve_soc=cfg.safety.battery_reserve_soc))
        self.sensors = RoverSensors(cfg.sensors, self.world, self.seeds.stream("sensors"), cfg.seed)
        self.actuator_factor = np.ones(6)         # TRUE torque capability (fault-modified)
        self.injector = FaultInjector([FaultSpec(**f) if isinstance(f, dict) else f for f in cfg.faults],
                                      self.sensors, self.battery, self.actuator_factor)
        pos, orn, _, _ = self.world.base_state()
        rng0 = self.seeds.stream("ekf_init")
        self.ekf = RoverEKF(np.array([pos[0] + rng0.normal(0, .05), pos[1] + rng0.normal(0, .05), pos[2], 0.0,
                                      yaw_of(orn) + rng0.normal(0, .02), 0.0, 0.0, 0.0]))
        self.map = RoverPerceivedMap(orbital_prior(self.terrain.heights, HRES, self.seeds.stream("prior")))
        self.goal = np.array(self.terrain.target, float)
        ops = bool(cfg.ground_ops or cfg.tasks)
        # surface operations: tight path tracking, pivot turns from 45 deg, and a faster cruise; benchmark
        # missions keep the original tracker so experiment results stay comparable
        self.pp = PurePursuit(PurePursuitConfig(v_max=cfg.max_speed, wheel_torque=cfg.wheel_torque,
                                                motor_peak=cfg.wheel_torque * 1.35,
                                                **({"precise": True, "lookahead": 1.4, "turn_in_place_deg": 45.0} if ops else {})))
        self.energy = RouteEnergyModel(geom.total_mass)
        self.supervisor = RoverSafetySupervisor(cfg.safety)
        self.detector = AnomalyDetector(cfg.detector)
        self.classifier = FaultClassifier()
        self.responder = AstraResponseSelector()
        self.debounce = ClassificationDebouncer()
        self.fsm_debounce = ClassificationDebouncer()     # identical hysteresis for the baseline's anomaly signal
        self.recovery = RecoveryVerifier()
        self.fsm = FSMBaseline(FSMConfig(battery_halt_soc=cfg.safety.battery_reserve_soc + 0.03))
        bc = self.battery.cfg
        self.evb = EvidenceBuilder(cfg.wheel_torque, bc.electronics_w, bc.motor_efficiency, bc.copper_loss_k)
        self.ev = Evidence()
        self.state_mgr = StateObservationManager()
        self.audit = DecisionAudit("rover")
        # surface operations keep a tighter clearance around perceived rocks (about one 1 m cell instead of two)
        self.base_weights = CostWeights(inflation_m=0.55) if ops else CostWeights()
        self.weights = self.base_weights
        self.response = Response()
        self.actuator_health_est = np.ones(6)
        self.path: dict = {"found": False, "path": [], "cells": []}
        self.path_history: list[dict] = []
        self.events: list[dict] = []
        self.fault_log: list[dict] = []
        self.telemetry: list[dict] = []
        self.t = 0.0
        self.terminal = False
        self.result: dict | None = None
        self.wheel_cmd = np.zeros(6)
        self.torque_cmd = np.full(6, cfg.wheel_torque)
        self.normals = np.full(6, geom.total_mass * 3.72 / 6)
        self.last_seen = {"lidar": 0.0, "camera": 0.0, "visloc": 0.0}
        self.last_lidar = None
        self.last_odom = None
        self.class_labels: set = set()
        self.first_detect: dict[str, float] = {}
        self.first_class: dict[str, dict] = {}
        self.collisions = 0
        self._in_contact = set()
        self.violations: list[dict] = []
        self.halt_since: float | None = None
        self.no_path_since: float | None = None
        self.replans = []
        self.true_trail = [pos[:2].tolist()]
        self.route_length = 0.0
        self._last_pos = pos[:2].copy()
        self.est_err, self.head_err, self.sig_hist = [], [], []
        self._next_ctrl = 0.0
        self._next_tlm = 0.0
        self.wall_time = 0.0
        self.policy_state = "NOMINAL"
        self.safety = self.supervisor.last
        sc = cfg.sensors
        self._sensor_base = (sc.lidar_noise, sc.lidar_range, sc.camera_confusion, sc.camera_range, sc.visloc_noise_xy, sc.dropout_prob)
        self.env = {"sandstorm": 0.0, "wind_speed": 4.0 if (cfg.ground_ops or cfg.tasks) else 0.0, "comms": True}
        self.added_obstacles: list[list[float]] = []
        self.ops = None
        self._event("phase", f"Rover mission start on terrain {cfg.terrain} ({self.terrain.name}) with {cfg.controller.upper()}")
        if cfg.ground_ops or cfg.tasks:
            from simulation.rover.ground_ops import GroundOps
            cfg.duration = max(cfg.duration, 1800.0)
            self.ops = GroundOps(self, cfg.tasks, cfg.task_kinds)
            self._event("phase", "Surface operations: deployed beside the lander; tasks: "
                        + ", ".join(t["label"] for t in self.ops.tasks))
        self._plan("initial path")

    # ------------------------------------------------------------------
    def _thin_rocks(self, keep_fraction: float = 0.6, big_m: float = 0.5) -> None:
        """Surface-operations demo terrain: the benchmark terrains are dense enough that a perceived rock plus
        the safety clearance can close every corridor (dead end -> safe halt). Keep every big boulder and every
        rock inside a rock field (the terrain still looks and drives rocky), drop ~40 % of the small/medium
        scattered rocks, chosen deterministically. Benchmark/experiment missions are not affected."""
        t = self.terrain
        kept = []
        for k, (x, y, r, h) in enumerate(t.obstacles):
            in_field = t.classes[t.cell(x, y)] == 3
            u = (np.sin(k * 12.9898 + x * 78.233 + y * 37.719) * 43758.5453) % 1.0
            if in_field or r >= big_m or u < keep_fraction:
                kept.append((x, y, r, h))
        t.obstacles = kept
        t._rock_cells = None

    def _event(self, kind, message, **data):
        self.events.append({"t": round(self.t, 2), "kind": kind, "message": message, **data})

    def est_dict(self) -> dict:
        x = self.ekf.x
        return {"x": x[0], "y": x[1], "z": x[2], "v": x[3], "psi": x[4], "omega": x[5], "roll": x[6], "pitch": x[7],
                "pos_sigma": self.ekf.pos_sigma(), "sigma": self.ekf.sigma()}

    def _dist_goal_est(self):
        return float(np.hypot(*(self.ekf.x[:2] - self.goal)))

    def _plan(self, reason: str, decision_event=None) -> dict:
        cost, hard, info = build_costmap(self.map, self.weights, self.ekf.pos_sigma(), float(np.min(self.actuator_health_est)))
        before = self.path.get("path", [])
        res = astar(cost, hard, self.ekf.x[:2], self.goal)
        res["reason"] = reason
        res["t"] = round(self.t, 2)
        res["costmap"] = info
        if res["found"]:
            e = self.energy.predict(res["path"], self.map.slope(), self.map.cam_class, self.cfg.max_speed * self.response.speed_factor or self.cfg.max_speed)
            res["energy"] = e
            self.path = res
            self.pp.set_path(res["path"])
            self.no_path_since = None
        else:
            if self.no_path_since is None:
                self.no_path_since = self.t
        self.replans.append(res["time_ms"])
        self.path_history.append({"t": res["t"], "reason": reason, "found": res["found"], "length": res.get("length"),
                                  "path": res["path"][::2] if res["found"] else []})
        self.path_history = self.path_history[-20:]
        self._event("replan", f"Path {'found' if res['found'] else 'NOT found'} ({reason})"
                    + (f": {res['length']:.1f} m, {res['time_ms']:.0f} ms" if res["found"] else ""))
        if decision_event is not None:
            decision_event.details["route_before"] = before[::3]
            decision_event.details["route_after"] = res["path"][::3] if res["found"] else []
            decision_event.details["replan_ms"] = res["time_ms"]
        return res

    # ------------------------------------------------------------------
    def step(self):
        if self.terminal:
            return
        for f in self.injector.update(self.t):
            self.fault_log.append(f)
            self._event("fault", f"FAULT {f['phase']}: {f['fault_type']}", fault=f)
        # sensors + estimation + perception
        for pk in self.sensors.sample(self.t, self.battery, self.wheel_cmd):
            self.state_mgr.update_sensor(pk.kind, self.t, pk.valid)
            if not pk.valid:
                continue
            d = pk.data
            if pk.kind == "imu":
                self.ekf.predict(1.0 / self.cfg.sensors.imu_hz)
                self.ekf.update_gyro(float(d["gyro"][2]), self.t)
                self.ekf.update_tilt(d["roll_pitch"], self.t)
            elif pk.kind == "odometry":
                v_odom = float(np.mean(d["wheel_speed"])) * self.geom.wheel_radius
                # odometry noise grows with observed slip evidence (slip makes wheel odometry biased)
                self.ekf.update_odometry(v_odom, self.t, sigma=0.03 + (0.15 + 0.8 * max(self.evb.slip, 0.0)) * abs(v_odom))
                self.last_odom = d
                self.evb.slip_update(v_odom, self.ekf.x[3])
                self.evb.wheel_update(d["wheel_cmd"], d["wheel_speed"], d["wheel_torque"])
            elif pk.kind == "visloc":
                self.ekf.update_visloc(d["xy"], d["z"], d["yaw"], self.t)
                self.evb.nis_update(self.ekf.last_nis.get("visloc", 0.0))
                self.last_seen["visloc"] = self.t
            elif pk.kind == "lidar":
                self.last_seen["lidar"] = self.t
                self.last_lidar = d
                x = self.ekf.x
                self.map.integrate_lidar(self.t, d["points_body"], np.array([x[0], x[1], x[2], x[4]]), x[6:8])
                self.ev.lidar_corruption = self.evb.lidar_corruption(d["points_body"], d["tilt_rows"], self.cfg.sensors.lidar_height,
                                                                     self.cfg.sensors.lidar_tilts_deg, x[6], x[7])
            elif pk.kind == "camera":
                self.last_seen["camera"] = self.t
                x = self.ekf.x
                self.map.integrate_camera(self.t, d["cells"], np.array([x[0], x[1], x[2], x[4]]))
            elif pk.kind == "battery":
                if self.last_odom is not None:
                    self.evb.battery_update(d["power"], self.last_odom["wheel_torque"], self.last_odom["wheel_speed"])
                self.meas_soc = d["soc"]
        if self.t + 1e-9 >= self._next_ctrl:
            self._next_ctrl += CONTROL_DT
            self._control()
        # terrain interaction (true terrain) + actuation + physics
        speeds, _ = self.world.wheel_states()
        cls = [self.terrain.class_at(*wp[:2]) for wp in self._wheel_pos] if hasattr(self, "_wheel_pos") else [0] * 6
        self.world.apply_rolling_resistance(np.array([CLASS_ROLLING_RESISTANCE[c] for c in cls]), self.normals, speeds)
        if self.env["wind_speed"] > 0:
            # aerodynamic drag of the Martian wind on the vehicle (rho ~0.02 kg/m^3: small even in storms)
            self.world.apply_wind(0.5 * 0.020 * 1.1 * 0.9 * self.env["wind_speed"] ** 2)
        self.world.step()
        speeds, torques = self.world.wheel_states()
        self.battery.step(torques, speeds, self.dt)
        self.t += self.dt
        self._bookkeeping()
        if self.t + 1e-9 >= self._next_tlm or self.terminal:
            self._next_tlm += TELEMETRY_DT
            self.telemetry.append(self.frame())

    def _control(self):
        c = self.cfg
        # true wheel-ground interaction parameters (physics side)
        self._wheel_pos = self.world.wheel_positions()
        self.world.set_wheel_friction(np.array([CLASS_FRICTION[self.terrain.class_at(*wp[:2])] for wp in self._wheel_pos]))
        self.normals = np.maximum(self.world.wheel_contact_normals(), 0.0)
        # ---- evidence ----
        ev = self.ev
        ev.t = self.t
        ev.lidar_stale = self.t - self.last_seen["lidar"]
        ev.camera_stale = self.t - self.last_seen["camera"]
        ev.visloc_stale = self.t - self.last_seen["visloc"]
        ev.visloc_nis = float(np.mean(self.evb.nis_hist)) if self.evb.nis_hist else 0.0
        ev.wheel_residual = self.evb.wheel_res.copy()
        ev.wheel_capability = self.evb.capability.copy()
        ev.slip = self.evb.slip
        ev.battery_ratio = self.evb.batt_ratio
        ev.p_fixed_est = self.evb.p_fixed
        ev.perception_inconsistency, ev.perception_checked = self.map.inconsistency_rate()
        est = self.est_dict()
        self.state_mgr.update_estimate(TimestampedEstimate(self.t, self.ekf.x.copy(), self.ekf.P.copy(), LABELS))
        # ---- detection ----
        anomaly = self.detector.update(ev)
        active = self.injector.active_types()
        if anomaly["anomaly"]:
            for ft in active:
                if ft not in self.first_detect:
                    inj_t = max(f["t"] for f in self.fault_log if f["fault_type"] == ft and f["phase"] == "injected")
                    self.first_detect[ft] = self.t - inj_t
                    self._event("detection", f"Anomaly detected ({', '.join(anomaly['flags'])}) "
                                              f"{self.t - inj_t:.1f} s after injection", flags=anomaly["flags"])
        # ---- policy ----
        speed_factor = 1.0
        hold = False
        replan_reason = None
        soc = getattr(self, "meas_soc", self.battery.soc)
        if c.controller == "astra":
            cls = self.classifier.classify(ev, anomaly)
            raw = set(cls["labels"]) | ({"uncertain"} if cls["uncertain"] else set())
            labels = set(self.debounce.update(self.t, raw))
            cls = {**cls, "labels": sorted(labels - {"uncertain"}), "uncertain": "uncertain" in labels}
            if labels != self.class_labels:
                new = labels - self.class_labels
                self.class_labels = labels
                resp = self.responder.select(cls, ev, est)
                for ft in active:
                    if ft not in self.first_class and (cls["labels"] or cls["uncertain"]):
                        self.first_class[ft] = {"labels": cls["labels"], "correct": ft in cls["labels"],
                                                "confidence": cls["confidence"].get(ft, 0.0)}
                if new:
                    self._event("classification", f"Classified: {sorted(labels) or ['nominal']} -> {resp.description}",
                                classification=cls)
                self._apply_response(resp, cls, ev, est, anomaly, active)
                if resp.replan:
                    replan_reason = "fault-specific adaptive replanning"
            elif "dropout" in " ".join(labels) or "sensor_dropout" in labels:
                # re-evaluate hold/speed as uncertainty evolves during dropout
                self.response = self.responder.select(cls, ev, est)
            speed_factor = self.response.speed_factor
            hold = self.response.hold
            self.policy_state = self.response.description
        else:
            stable = self.fsm_debounce.update(self.t, set(anomaly["flags"]))
            dec = self.fsm.decide(self.t, {"anomaly": bool(stable), "flags": {k: anomaly["flags"].get(k, self.t) for k in stable}}, ev, soc)
            speed_factor = dec["speed_factor"]
            hold = speed_factor == 0
            if dec["halt"]:
                self._halt("FSM fixed-rule halt: " + (self.fsm.transitions[-1]["reason"] if self.fsm.transitions else ""))
                return
            if self.fsm.transitions and self.fsm.transitions[-1]["t"] == round(self.t, 2):
                tr = self.fsm.transitions[-1]
                self._event("fsm", f"FSM {tr['from']} -> {tr['to']}: {tr['reason']}")
                ev_rec = self.audit.record(t=self.t, trigger=tr["reason"], decision=f"FSM state {tr['to']}",
                                           evidence=ev.to_dict(), estimated_state={k: est[k] for k in ("x", "y", "psi", "v")},
                                           uncertainty={"pos_sigma": est["pos_sigma"]}, fault_classification=None,
                                           expected_outcome={"speed_factor": speed_factor},
                                           safety_status=self.safety["action"],
                                           details={"faults_injected": active, "anomaly": anomaly})
                if tr["to"] in ("DEGRADED", "SENSOR_WAIT"):
                    self.recovery.start(f"fsm-{tr['to']}-{self.t:.0f}", self.t, self._dist_goal_est(), ev_rec.event_id)
            self.policy_state = self.fsm.state
        # ---- route energy feasibility & independent safety supervision ----
        route_infeasible = False
        if self.path.get("found") and int(self.t / CONTROL_DT) % 20 == 0:
            rem = self.path["path"][self.pp.idx:]
            e = self.energy.predict([tuple(self.ekf.x[:2])] + rem, self.map.slope(), self.map.cam_class,
                                    max(self.cfg.max_speed * max(speed_factor, 0.2), 0.05))
            budget = (soc - c.safety.battery_reserve_soc) * c.battery_capacity_wh
            route_infeasible = e["energy_wh"] > budget
            self.route_energy = {"predicted_wh": e["energy_wh"], "budget_wh": budget}
        front = None
        if self.last_lidar is not None and self.t - self.last_seen["lidar"] < 1.0:
            pb = self.last_lidar["points_body"]
            rows = self.last_lidar["tilt_rows"]
            n = len(pb) // rows
            first = pb[:n]               # shallowest ring: obstacles ahead
            rng = np.hypot(first[:, 0], first[:, 1])
            ang = np.arctan2(first[:, 1], first[:, 0])
            fwd = np.isfinite(rng) & (np.abs(ang) < np.radians(35)) & (first[:, 2] > -0.25)
            front = float(rng[fwd].min()) if fwd.any() else None
        self.safety = self.supervisor.check({
            "front_range": front, "lidar_stale": ev.lidar_stale, "roll_deg": np.degrees(est["roll"]),
            "pitch_deg": np.degrees(est["pitch"]), "slip": ev.slip, "soc": soc, "pos_sigma": est["pos_sigma"],
            "route_energy_infeasible": route_infeasible, "wheel_capability": ev.wheel_capability,
            "position": (est["x"], est["y"])})
        speed_factor = min(speed_factor, self.safety["speed_cap"])
        if self.safety["action"] == "safe_halt":
            if self.halt_since is None:
                self.halt_since = self.t
                self._event("safety", "Safety supervisor SAFE-HALT: " + "; ".join(self.safety["reasons"]))
            if self.t - self.halt_since > 15.0 or soc < c.safety.battery_reserve_soc:
                self._halt("safety supervisor safe-halt: " + "; ".join(self.safety["reasons"]))
                return
        else:
            self.halt_since = None
        if self.safety["action"] == "replan" and (not self.replans or int(self.t * 10) % 20 == 0):
            replan_reason = replan_reason or ("safety supervisor: " + "; ".join(self.safety["reasons"]))
        # ---- planning ----
        cost_hard = None
        if self.path.get("found") and int(self.t * 10) % 5 == 0:
            _, cost_hard, _ = build_costmap(self.map, self.weights, self.ekf.pos_sigma(), float(np.min(self.actuator_health_est)))
            if path_blocked(self.path["cells"], cost_hard, max(self.pp.idx - 2, 0), cell_of(*self.ekf.x[:2])):
                replan_reason = replan_reason or "route blocked by newly perceived hazard"
        if not self.path.get("found") and int(self.t * 10) % 20 == 0:
            replan_reason = replan_reason or "retry: no path"
        if replan_reason:
            self._plan(replan_reason, getattr(self, "_pending_decision", None))
            self._pending_decision = None
        if self.no_path_since is not None and self.t - self.no_path_since > 30.0:
            self._halt("no traversable path for 30 s")
            return
        # ---- recovery verification ----
        for eid, outcome in self.recovery.check(self.t, self._dist_goal_est(), self.halt_since is not None):
            self.audit.resolve(eid, outcome)
            self._event("recovery", f"Recovery {'verified' if outcome['recovered'] else 'NOT verified'}: "
                                    f"{outcome['progress_m']} m progress in {outcome['window_s']} s")
        # ---- arrival / surface-operations layer ----
        if self.ops is not None:
            if self.ops.update(soc, est) or self.terminal:
                self.wheel_cmd = np.zeros(6)
                self.world.set_wheels(np.zeros(6), np.full(6, c.wheel_torque))
                return
        elif self._dist_goal_est() < c.arrival_radius:
            self.world.set_wheels(np.zeros(6), np.full(6, c.wheel_torque))
            self._finish("arrived")
            return
        # ---- motion control ----
        if hold or not self.path.get("found"):
            speed_factor = 0.0
        slip = max(ev.slip, 0.0)
        speeds, torques, info = self.pp.compute((est["x"], est["y"], est["psi"]), speed_factor, slip,
                                                self.actuator_health_est, gentle=self.response.gentle_turns)
        self.ctrl_info = info
        self.wheel_cmd = speeds
        self.torque_cmd = torques
        self.world.set_wheels(speeds, torques * self.actuator_factor)   # true actuator capability applies in physics

    def _apply_response(self, resp: Response, cls, ev, est, anomaly, active):
        self.response = resp
        w = self.base_weights.with_(**resp.weights) if resp.weights else self.base_weights
        self.weights = w
        if resp.actuator_health is not None:
            self.actuator_health_est = resp.actuator_health
        if resp.energy_update:
            self.energy.p_fixed = resp.energy_update["p_fixed"]
        rec = self.audit.record(
            t=self.t, trigger="classification change: " + (", ".join(sorted(cls["labels"])) or ("uncertain" if cls["uncertain"] else "cleared")),
            decision=resp.description, evidence=ev.to_dict(),
            estimated_state={k: est[k] for k in ("x", "y", "psi", "v")}, uncertainty={"pos_sigma": est["pos_sigma"]},
            fault_classification=cls, expected_outcome={"speed_factor": resp.speed_factor, "replan": resp.replan,
                                                        "hold": resp.hold},
            safety_status=self.safety["action"],
            details={"faults_injected": active, "anomaly": anomaly, "weights": asdict(w)})
        self._pending_decision = rec
        if cls["labels"] or cls["uncertain"]:
            self.recovery.start(f"astra-{rec.event_id}", self.t, self._dist_goal_est(), rec.event_id)

    def _bookkeeping(self):
        pos, orn, lin, ang = self.world.base_state()
        d = np.hypot(*(pos[:2] - self._last_pos))
        if d > 0.05:
            self.route_length += d
            self._last_pos = pos[:2].copy()
            self.true_trail.append(pos[:2].tolist())
        hits = set(self.world.rock_contacts())
        new = hits - self._in_contact
        if new:
            self.collisions += len(new)
            self.violations.append({"t": round(self.t, 2), "type": "collision", "count": len(new)})
            self._event("safety", f"COLLISION with {len(new)} obstacle(s)")
        self._in_contact = hits
        import pybullet as p
        roll, pitch, yaw = p.getEulerFromQuaternion(orn)
        tilt = np.degrees(max(abs(roll), abs(pitch)))
        if tilt > 30 and (not self.violations or self.violations[-1].get("type") != "tilt"):
            self.violations.append({"t": round(self.t, 2), "type": "tilt", "deg": tilt})
        if self.battery.soc < 0.05 and not any(v["type"] == "battery" for v in self.violations):
            self.violations.append({"t": round(self.t, 2), "type": "battery", "soc": self.battery.soc})
        if int(self.t / self.dt) % 24 == 0:
            self.est_err.append(float(np.hypot(*(self.ekf.x[:2] - pos[:2]))))
            self.head_err.append(float(abs((self.ekf.x[4] - yaw + np.pi) % (2 * np.pi) - np.pi)))
            self.sig_hist.append(self.ekf.pos_sigma())
        if tilt > 60:
            self._finish("rollover")
        elif self.t >= self.cfg.duration:
            self._finish("timeout")

    def _halt(self, why: str):
        self.world.set_wheels(np.zeros(6), np.full(6, self.cfg.wheel_torque))
        self._event("halt", why)
        self._finish("safe_halt", why)

    def _finish(self, outcome: str, why: str = ""):
        if self.terminal:
            return
        self.terminal = True
        pos, _, _, _ = self.world.base_state()
        dist = float(np.hypot(*(pos[:2] - self.goal)))
        reached = outcome == "arrived" and dist <= self.cfg.success_radius
        if self.ops is not None:
            # parked beside the lander: the estimate is within 1.2 m of the spot, so allow navigation error on top
            reached = outcome == "mission_complete" and dist <= self.cfg.success_radius + 1.0
        safe = self.collisions == 0 and not any(v["type"] in ("tilt", "battery") for v in self.violations)
        injected = sorted({f["fault_type"] for f in self.fault_log if f["phase"] == "injected"})
        cls_correct = [self.first_class[f]["correct"] for f in injected if f in self.first_class]
        recov = [e.actual_outcome["recovered"] for e in self.audit.events if e.actual_outcome and "recovered" in e.actual_outcome]
        self.result = {
            "outcome": outcome, "reason": why, "success": bool(reached and safe), "reached_target": reached,
            "controller": self.cfg.controller, "terrain": self.cfg.terrain, "seed": self.cfg.seed,
            "time_to_completion_s": round(self.t, 2) if reached and safe else None, "mission_time_s": round(self.t, 2),
            "final_distance_to_target_m": dist, "energy_used_wh": self.battery.energy_used_wh,
            "remaining_battery_soc": self.battery.soc, "route_length_m": self.route_length,
            "collisions": self.collisions, "safety_violations": len(self.violations), "violations": self.violations,
            "faults_injected": injected,
            "fault_detection_delay_s": {k: round(v, 2) for k, v in self.first_detect.items()},
            "fault_classification": self.first_class,
            "classification_accuracy": (float(np.mean(cls_correct)) if cls_correct else None) if self.cfg.controller == "astra" else None,
            "recovery_success_rate": float(np.mean(recov)) if recov else None,
            "replans": len(self.replans), "ekf_relocalizations": self.ekf.relocalizations, "replanning_time_ms_mean": float(np.mean(self.replans)) if self.replans else None,
            "position_error_mean_m": float(np.mean(self.est_err)) if self.est_err else None,
            "position_error_max_m": float(np.max(self.est_err)) if self.est_err else None,
            "heading_error_mean_rad": float(np.mean(self.head_err)) if self.head_err else None,
            "position_sigma_mean_m": float(np.mean(self.sig_hist)) if self.sig_hist else None,
            "fsm_transitions": self.fsm.transitions if self.cfg.controller == "fsm" else None,
        }
        if self.ops is not None:
            self.result["ground_ops"] = self.ops.summary()
        self._event("phase", f"Mission end: {outcome} (success={self.result['success']}, {dist:.2f} m from target)")

    # ------------------------------------------------------------------
    def frame(self) -> dict:
        import pybullet as p
        pos, orn, lin, ang = self.world.base_state()
        rpy = p.getEulerFromQuaternion(orn)
        speeds, torques = self.world.wheel_states()
        x = self.ekf.x
        return {
            "t": round(self.t, 2),
            "truth": {"position": pos.tolist(), "rpy": list(rpy), "velocity": lin.tolist(), "speed": float(np.hypot(lin[0], lin[1])),
                      "yaw_rate": float(ang[2])},
            "estimate": {"position": x[0:3].tolist(), "v": float(x[3]), "heading": float(x[4]), "omega": float(x[5]),
                         "roll": float(x[6]), "pitch": float(x[7]), "sigma": self.ekf.sigma().tolist(),
                         "pos_sigma": self.ekf.pos_sigma()},
            "error": {"position": float(np.hypot(*(x[:2] - pos[:2]))),
                      "heading": float(abs((x[4] - rpy[2] + np.pi) % (2 * np.pi) - np.pi))},
            "battery": {"soc": self.battery.soc, "voltage": self.battery.voltage, "current": self.battery.current,
                        "power": self.battery.power, "energy_used_wh": self.battery.energy_used_wh},
            "wheels": {"speed": speeds.tolist(), "torque": torques.tolist(), "cmd": self.wheel_cmd.tolist(),
                       "torque_limit": self.torque_cmd.tolist(), "health_est": np.round(self.actuator_health_est, 3).tolist(),
                       "joints": {k: round(v, 4) for k, v in self.world.joint_angles().items()}},
            "slip": self.ev.slip, "safety": self.safety, "policy": self.policy_state,
            "faults_active": self.injector.active_types(), "classification": sorted(self.class_labels),
            "evidence": self.ev.to_dict(), "nis": {k: round(v, 3) for k, v in self.ekf.last_nis.items()},
            "controller": getattr(self, "ctrl_info", {}),
        }

    def snapshot(self, include_paths: bool = True) -> dict:
        s = {"module": "rover", "t": round(self.t, 2), "phase": "complete" if self.terminal else "running",
             "frame": self.telemetry[-1] if self.telemetry else self.frame(), "result": self.result,
             "events": self.events[-30:], "goal": self.goal.tolist(), "controller": self.cfg.controller}
        if include_paths:
            s["planned_path"] = self.path.get("path", [])
            s["actual_path"] = self.true_trail[::2]
            s["estimated_path"] = [f["estimate"]["position"][:2] for f in self.telemetry[::5]]
            s["path_history"] = [{k: v for k, v in h.items() if k != "path"} | {"path": h["path"]} for h in self.path_history[-4:]]
            if self.last_lidar is not None and self.t - self.last_seen["lidar"] < 1.0:
                x = self.ekf.x
                pb = self.last_lidar["points_body"]
                fin = np.all(np.isfinite(pb), axis=1)
                c, sn = np.cos(x[4]), np.sin(x[4])
                P = pb[fin][::3]
                s["lidar"] = np.round(np.c_[x[0] + c * P[:, 0] - sn * P[:, 1], x[1] + sn * P[:, 0] + c * P[:, 1], x[2] + P[:, 2]], 2).tolist()
            s["perceived"] = {"obstacles": np.argwhere(self.map.obstacle).tolist(),
                              "untraversable": np.argwhere(self.map.cam_trav == 0).tolist()}
        s["environment"] = dict(self.env)
        s["added_obstacles"] = self.added_obstacles
        if self.ops is not None:
            s["ops"] = self.ops.snapshot()
        return s

    def scene(self) -> dict:
        return {"terrain": self.terrain.visual(step=2), "summary": self.terrain.summary()}

    def set_environment(self, sandstorm: float | None = None, wind_speed: float | None = None,
                        comms: bool | None = None) -> dict:
        """Surface conditions (TRUE world). A dust storm degrades lidar, cameras and visual localisation;
        wind pushes on the vehicle; comms loss only removes the ground link. The rover is not told any of
        this - it infers the storm from its own navcam optical-depth measurement."""
        if sandstorm is not None: self.env["sandstorm"] = float(np.clip(sandstorm, 0.0, 1.0))
        if wind_speed is not None: self.env["wind_speed"] = float(wind_speed)
        if comms is not None: self.env["comms"] = bool(comms)
        s = self.env["sandstorm"]
        ln, lr, cc, cr, vn, dp = self._sensor_base
        sc = self.sensors.cfg
        sc.lidar_noise, sc.lidar_range = ln * (1 + 1.5 * s), lr * (1 - 0.4 * s)
        sc.camera_confusion, sc.camera_range = cc + 0.22 * s, cr * (1 - 0.5 * s)
        sc.visloc_noise_xy, sc.dropout_prob = vn * (1 + 3 * s), dp + 0.35 * s
        self._event("environment", f"Surface conditions: dust storm {s:.2f}, wind {self.env['wind_speed']:.0f} m/s, "
                                   f"comms {'up' if self.env['comms'] else 'LOST'}")
        return dict(self.env)

    def add_obstacle(self, x: float, y: float, radius: float = 0.6) -> dict:
        pos, _, _, _ = self.world.base_state()
        if np.hypot(x - pos[0], y - pos[1]) < radius + 1.2:
            raise ValueError("too close to the rover")
        if self.ops is not None and np.hypot(*(np.array([x, y]) - self.ops.lander)) < radius + 2.6:
            raise ValueError("too close to the lander")
        h = radius * 1.2
        self.world.add_rock(x, y, radius, h)
        self.terrain.obstacles.append((float(x), float(y), float(radius), float(h)))
        self.terrain._rock_cells = None
        self.added_obstacles.append([float(x), float(y), float(radius), float(h)])
        on_route = any(np.hypot(px - x, py - y) < radius + 1.0 for px, py in self.path.get("path", []))
        self._event("injection", f"Obstacle placed at ({x:.1f}, {y:.1f}) r={radius:.1f} m"
                                 + (" ON the planned route — the rover must perceive it and re-plan" if on_route else ""))
        return {"x": x, "y": y, "radius": radius, "height": h, "on_route": on_route}

    def inject_fault(self, fault_type: str, duration: float | None, params: dict) -> dict:
        s = self.injector.inject_now(self.t, fault_type, duration, params)
        self._event("injection", f"Operator injected {fault_type} (duration {duration or 'until end'})")
        return s.to_dict()

    def run(self, max_time: float | None = None) -> dict:
        t0 = time.perf_counter()
        while not self.terminal and self.t < (max_time or 1e9):
            self.step()
        self.wall_time += time.perf_counter() - t0
        return self.result or {}

    def debrief(self) -> dict:
        tl = self.telemetry
        return {"result": self.result, "config": self.cfg.to_dict(), "decisions": self.audit.to_list(), "events": self.events,
                "series": {"t": [f["t"] for f in tl], "soc": [f["battery"]["soc"] for f in tl],
                           "pos_err": [f["error"]["position"] for f in tl], "pos_sigma": [f["estimate"]["pos_sigma"] for f in tl],
                           "speed": [f["truth"]["speed"] for f in tl], "power": [f["battery"]["power"] for f in tl]}}

    def close(self):
        self.world.close()
