"""ASTRA TOUCHDOWN mission runner.

Rates (fixed, independent of rendering / websocket publishing):
  physics 100 Hz (RK4) | sensors per-channel | EKF predict 100 Hz | controller 20 Hz
  perception 1 Hz (below assessment altitude) | prediction 1 Hz | telemetry 10 Hz
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import numpy as np

from autonomy.control.lander_mpc import LanderMPCConfig, LanderMPCController
from autonomy.control.lander_pid import LanderPIDConfig, LanderPIDController
from autonomy.control.descent_profile import desired_velocity
from autonomy.decision.audit import DecisionAudit
from autonomy.decision.touchdown_supervisor import SupervisorConfig, TouchdownSupervisor
from autonomy.estimation.lander_ekf import LABELS, EKFConfig, LanderEKF
from autonomy.fault_detection.sensor_health import SensorHealthMonitor
from autonomy.framework import StateObservationManager, TimestampedEstimate
from autonomy.planning.landing_perception import LidarConfig, OrbitalDEM, PerceivedHazardMap
from autonomy.planning.landing_site import DiversionConfig, DiversionPlanner, LandingSiteAssessor, SiteCriteria
from autonomy.prediction.touchdown_predictor import TouchdownPredictor
from shared.enums import TouchdownPhase as Ph
from simulation.common.math3d import euler_to_quat
from simulation.common.rng import SeedManager
from simulation.touchdown.environment import Atmosphere, PlanetConfig
from simulation.touchdown.lander import ActuatorCommand, Lander, LanderParams
from simulation.touchdown.sensors import LanderSensorSuite, SensorConfig
from simulation.touchdown.terrain import Terrain, TerrainConfig

PHYSICS_DT = 0.01
CONTROL_DT = 0.05
PERCEPTION_DT = 1.0
TELEMETRY_DT = 0.1
HEALTH_WARMUP_S = 15.0


@dataclass
class TouchdownConfig:
    seed: int = 42
    controller: str = "pid"                 # pid | mpc | ppo
    environment: str = "mars"               # mars | moon (selects planet + terrain presets, see apply_environment_preset)
    initial_position: list[float] = field(default_factory=lambda: [-650.0, 320.0, 2900.0])
    initial_velocity: list[float] = field(default_factory=lambda: [32.0, -14.0, -62.0])
    initial_euler_deg: list[float] = field(default_factory=lambda: [3.0, -4.0, 0.0])
    target: list[float] = field(default_factory=lambda: [0.0, 0.0])
    planet: PlanetConfig = field(default_factory=PlanetConfig)
    terrain: TerrainConfig = field(default_factory=TerrainConfig)
    lander: LanderParams = field(default_factory=LanderParams)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    ekf: EKFConfig = field(default_factory=EKFConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    lidar: LidarConfig = field(default_factory=LidarConfig)
    site: SiteCriteria = field(default_factory=SiteCriteria)
    diversion: DiversionConfig = field(default_factory=DiversionConfig)
    pid: LanderPIDConfig = field(default_factory=LanderPIDConfig)
    mpc: LanderMPCConfig = field(default_factory=LanderMPCConfig)
    ppo_checkpoint: str | None = None
    enable_diversion: bool = True
    sensor_health: bool = True              # lying-sensor monitor (CUSUM + cross-check) with isolation
    hover_scan: bool = True                 # PID/MPC: arrest the descent over each pad and scan before committing
    hover_agl: float = 80.0                 # m above the pad (kept above the classic 70 m diversion floor)
    hover_s: float = 4.0                    # seconds of stable hover while the lidar scans at 2 Hz
    late_divert_agl: float = 8.0            # PID/MPC: slower final descent allows side-steps down to this AGL
    ppo_guard: str = "monitor"              # off | monitor | fallback (learned-controller runtime guard)

    @staticmethod
    def from_dict(d: dict) -> "TouchdownConfig":
        cfg = TouchdownConfig()
        sub = {"planet": PlanetConfig, "terrain": TerrainConfig, "lander": LanderParams, "supervisor": SupervisorConfig,
               "lidar": LidarConfig, "site": SiteCriteria, "diversion": DiversionConfig, "ekf": EKFConfig}
        for k, v in (d or {}).items():
            if k in sub and isinstance(v, dict):
                obj = getattr(cfg, k)
                for kk, vv in v.items():
                    if hasattr(obj, kk):
                        setattr(obj, kk, vv)
            elif k == "sensors" and isinstance(v, dict):
                cfg.sensors = SensorConfig(overrides=v.get("overrides", v))
            elif hasattr(cfg, k):
                setattr(cfg, k, v)
        cfg.terrain.target = list(cfg.target)
        if cfg.environment == "moon":
            # airless body: lunar gravity, no atmosphere (no drag, no wind), more densely cratered terrain
            cfg.planet.gravity = 1.625
            cfg.planet.rho0 = 0.0
            cfg.planet.wind = [0.0, 0.0, 0.0]
            cfg.planet.gust_std = 0.0
            cfg.terrain.n_craters = max(cfg.terrain.n_craters, 40)
        return cfg

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("pid", None); d.pop("mpc", None)
        return d


def make_controller(cfg: TouchdownConfig):
    if cfg.controller == "pid":
        return LanderPIDController(cfg.pid)
    if cfg.controller == "mpc":
        return LanderMPCController(cfg.mpc)
    if cfg.controller == "ppo":
        from autonomy.control.lander_ppo import LanderPPOController
        return LanderPPOController(cfg.ppo_checkpoint, guard=cfg.ppo_guard)
    raise ValueError(f"unknown controller {cfg.controller}")


class TouchdownMission:
    def __init__(self, cfg: TouchdownConfig, fast: bool = False):
        """``fast`` (RL training only): skip lidar scanning, the 10 Hz telemetry log and the 1 Hz prediction
        roll-outs. Physics, sensors, EKF and supervisor are unchanged."""
        self.cfg = cfg
        self.fast = fast
        self.seeds = SeedManager(cfg.seed)
        self.terrain = Terrain(cfg.terrain, self.seeds.stream("terrain"))
        self.atm = Atmosphere(cfg.planet, self.seeds.stream("wind"))
        self.g = cfg.planet.gravity
        q0 = euler_to_quat(*np.radians(cfg.initial_euler_deg))
        self.lander = Lander(cfg.lander, np.array(cfg.initial_position, float), np.array(cfg.initial_velocity, float), q0)
        self.sensors = LanderSensorSuite(cfg.sensors, self.seeds)
        self.dem = OrbitalDEM(self.terrain, self.seeds.stream("dem"))
        rng0 = self.seeds.stream("ekf_init")
        x0 = np.zeros(12)
        x0[0:3] = np.array(cfg.initial_position) + rng0.normal(0, [20, 20, 10])
        x0[3:6] = np.array(cfg.initial_velocity) + rng0.normal(0, 1.0, 3)
        x0[6:9] = np.radians(cfg.initial_euler_deg) + rng0.normal(0, 0.01, 3)
        self.ekf = LanderEKF(cfg.ekf, x0, self.g, dem=self.dem)
        self.controller = make_controller(cfg)
        self.supervisor = TouchdownSupervisor(cfg.supervisor)
        self.hmap = PerceivedHazardMap(cfg.lidar)
        self.assessor = LandingSiteAssessor(cfg.site)
        self.predictor = TouchdownPredictor(self.dem, cfg.lander.max_thrust, cfg.lander.isp, cfg.lander.dry_mass)
        self.planner = DiversionPlanner(cfg.diversion, self.assessor, self.predictor,
                                        {"dry_mass": cfg.lander.dry_mass, "isp": cfg.lander.isp,
                                         "max_thrust": cfg.lander.max_thrust})
        self.state_mgr = StateObservationManager()
        self.audit = DecisionAudit("touchdown")
        self.events: list[dict] = []
        self.telemetry: list[dict] = []
        self.target = np.array([cfg.target[0], cfg.target[1], self.dem.height(*cfg.target)])
        self.original_target = self.target.copy()
        self.t = 0.0
        self.cmd = ActuatorCommand()
        self.ctrl_info: dict = {}
        self.last_gyro = np.zeros(3)
        self.last_accel = np.array([0, 0, self.g])
        self.fuel_meas = cfg.lander.fuel_mass
        self.prediction: dict = {}
        self.reference: list = []
        self.site_status: dict | None = None
        self.diversions = 0
        self.result: dict | None = None
        self._next_ctrl = 0.0
        self._next_perc = 0.0
        self._next_tlm = 0.0
        self._next_pred = 0.0
        self._pending_hazard_event = None
        self._disturb_until = -1.0
        self.wall_time = 0.0
        self.max_est_err = 0.0
        self._target_verified = False
        # classical guidance (not PPO, not RL training): gentle final descent, hover-and-scan, late side-steps
        self.classic = cfg.controller in ("pid", "mpc") and not fast
        self.hovering = False
        self._hover_t0: float | None = None
        self._hover_start = 0.0
        self._hover_key = None
        self._hovered: set = set()
        self.hover_log: list[dict] = []
        if self.classic:
            self.predictor.k_low = (cfg.pid if cfg.controller == "pid" else cfg.mpc).profile_k_low
            cfg.supervisor.min_divert_agl = min(cfg.supervisor.min_divert_agl, cfg.late_divert_agl)
        self.health = SensorHealthMonitor() if (cfg.sensor_health and not fast) else None
        self._last_alt = None
        self.last_scan: dict | None = None
        self.obstacles: list[dict] = []
        self._lidar_base = (cfg.lidar.detect_prob, cfg.lidar.range_noise_base, cfg.lidar.range_noise_per_m, cfg.lidar.max_range)
        self.environment = {"wind_speed": float(np.hypot(*cfg.planet.wind[:2])),
                            "wind_dir_deg": float(np.degrees(np.arctan2(cfg.planet.wind[1], cfg.planet.wind[0]))),
                            "gust_std": cfg.planet.gust_std, "dust": 0.0}
        self.supervisor.transition(Ph.ENTRY if self._agl_true() > cfg.supervisor.ignition_agl else Ph.DESCENT, 0.0,
                                   "mission start")
        self._event("phase", f"Mission start in {self.supervisor.phase.value}")

    # ------------------------------------------------------------------
    def _agl_true(self) -> float:
        p = self.lander.pos
        return float(p[2] - self.cfg.lander.leg_height - self.terrain.height(p[0], p[1]))

    def _event(self, kind: str, message: str, **data):
        self.events.append({"t": round(self.t, 3), "kind": kind, "message": message, **data})

    def estimate(self) -> dict:
        x = self.ekf.x
        return {"p": x[0:3].copy(), "v": x[3:6].copy(), "euler": x[6:9].copy(), "omega": self.last_gyro.copy(),
                "mass": self.cfg.lander.dry_mass + max(self.fuel_meas, 0.0), "fuel": max(self.fuel_meas, 0.0),
                "agl": float(x[2] - self.cfg.lander.leg_height - self.dem.height(x[0], x[1])), "g": self.g,
                "max_thrust": self.cfg.lander.max_thrust,
                "min_thrust": self.cfg.lander.max_thrust * self.cfg.lander.min_throttle,
                "sigma": self.ekf.sigma(), "imu_accel": self.last_accel.copy(), "hover": getattr(self, "hovering", False)}

    # ------------------------------------------------------------------
    def step(self) -> None:
        if self.supervisor.terminal:
            return
        dt = PHYSICS_DT
        # sensors (truth -> measurements)
        for m in self.sensors.sample(self.t, self.lander, max(self._agl_true(), 0.0)):
            self.state_mgr.update_sensor(m.channel, self.t, m.valid)
            if not m.valid:
                continue
            if m.channel == "imu_accel": self.last_accel = m.value
            elif m.channel == "imu_gyro": self.last_gyro = m.value
            elif m.channel in ("position", "velocimeter", "altimeter"): self._nav_update(m)
            elif m.channel == "attitude": self.ekf.update_attitude(m.value)
            elif m.channel == "fuel": self.fuel_meas = float(m.value[0])
        self.ekf.predict(self.last_accel, self.last_gyro, dt)

        if self.t + 1e-9 >= self._next_ctrl:
            self._next_ctrl += CONTROL_DT
            self._control_step()
        if self.t + 1e-9 >= self._next_perc:
            self._next_perc += PERCEPTION_DT / 2 if self.hovering else PERCEPTION_DT   # 2 Hz scans while hovering
            if not self.fast:
                self._perception_step()
        if self.t >= self._disturb_until:
            self.lander.ext_force = np.zeros(3)

        self.atm.step(dt)
        self.lander.step(self.cmd, dt, self.atm, self.g, self.terrain.height(*self.lander.pos[:2]))
        self.t += dt

        err = float(np.linalg.norm(self.ekf.x[0:3] - self.lander.pos))
        self.max_est_err = max(self.max_est_err, err)
        if self._agl_true() <= 0.0:
            self._touchdown()
        elif self.t > self.cfg.supervisor.max_mission_time:
            self.supervisor.transition(Ph.FAILED, self.t, "mission time exceeded")
            self._finish("timeout")
        if (self.t + 1e-9 >= self._next_tlm or self.supervisor.terminal) and not self.fast:
            self._next_tlm += TELEMETRY_DT
            self.telemetry.append(self.frame())

    def _nav_update(self, m) -> None:
        """Navigation-sensor update routed through the sensor-health monitor. An isolated sensor is still
        observed (dry update) but no longer corrects the estimate."""
        ch, leg = m.channel, self.cfg.lander.leg_height
        z = m.value + leg if ch == "altimeter" else m.value
        dry = self.health is not None and self.health.isolated(ch)
        if ch == "position":
            self.ekf.update_position(z, dry=dry, delay=self.sensors.channels["position"].spec.delay_s)
        else:
            {"velocimeter": self.ekf.update_velocity, "altimeter": self.ekf.update_altimeter}[ch](z, dry=dry)
        # monitoring starts once the filter has converged from its initial uncertainty (the start-up
        # transient legitimately produces one-sided innovations)
        if self.health is None or self.t < HEALTH_WARMUP_S or self.ekf.position_sigma_h() > 12.0:
            return
        inn = self.ekf.last_innovation.get(ch)
        truth = {"altimeter": np.array([self._agl_true() + leg]), "position": self.lander.pos,
                 "velocimeter": self.lander.vel}[ch]
        changes = self.health.update(self.t, ch, inn["innovation"], inn["S_diag"], z, truth)
        if ch == "altimeter":
            self._last_alt = (self.t, float(z[0]), self.cfg.ekf.meas_std["altimeter"] + 0.002 * abs(float(z[0])))
        elif ch == "position" and self._last_alt and self.t - self._last_alt[0] < 0.3:
            gx, gy = self.dem.gradient(z[0], z[1])
            lag = self.sensors.channels["position"].spec.delay_s + (self.t - self._last_alt[0])
            v = self.ekf.x[3:6]
            px, py, pz = z[0] + v[0] * lag, z[1] + v[1] * lag, z[2] + v[2] * lag   # TRN fix brought to the altimeter epoch
            trn_h = float(pz - self.dem.height(px, py))
            trn_sig = float(np.hypot(self.cfg.ekf.meas_std["position"][2], 4.0 * np.hypot(gx, gy)))
            self.health.cross_check(self.t, self._last_alt[1], self._last_alt[2], trn_h, trn_sig)
        for c in changes:
            self._sensor_health_event(c)

    def _sensor_health_event(self, c: dict) -> None:
        d = self.sensors.drift.get(c["channel"])
        onset = d["t0"] if d else None
        delay = None if onset is None else round(c["t"] - onset, 2)
        if c["status"] == "SUSPECT":
            self._event("sensor_health", f"{c['channel']} SUSPECT: innovations leaning {c['direction']} "
                        f"(CUSUM {c['cusum']:.1f} > {c['threshold']:.0f})", **c)
            return
        est = self.estimate()
        ev = self.audit.record(
            t=self.t, trigger=f"persistent one-sided {c['channel']} innovations (CUSUM {c['cusum']:.1f} > h={c['threshold']:.0f})",
            decision=f"isolate {c['channel']} from the navigation filter",
            evidence={"cusum": c["cusum"], "threshold": c["threshold"], "direction": c["direction"],
                      "confirmed_by": c["confirmed_by"], "cross_check_cusum": c.get("cross_check"),
                      "mean_normalised_innovation": self.health.innov_mean[c["channel"]]},
            estimated_state={"p": est["p"], "v": est["v"], "agl": est["agl"]},
            uncertainty={"sigma": est["sigma"][:6]},
            expected_outcome={"navigation": "continues on the remaining sensors"},
            details={"drift_onset_t": onset, "detection_delay_s": delay,
                     "true_bias_at_detection": self.sensors.drift_bias(c["channel"], self.t)},
            safety_status="sensor fault")
        self._event("sensor_health", f"{c['channel'].upper()} DRIFT DETECTED at t={c['t']:.1f} s"
                    + (f", {delay:.1f} s after onset" if delay is not None else "") + " — sensor isolated",
                    decision_id=ev.event_id, **c)

    def inject_drift(self, channel: str, rate: float, axis: int | None = None) -> dict:
        d = self.sensors.set_drift(channel, rate, self.t, axis)
        self._event("injection", f"Slow drift injected on {channel}: {rate:+.2f} units/s from t={self.t:.1f} s "
                                 "(readings stay valid and noisy — nothing looks broken)")
        return {"channel": channel, **d}

    def _control_step(self):
        sup = self.supervisor
        est = self.estimate()
        self.state_mgr.update_estimate(TimestampedEstimate(self.t, self.ekf.x.copy(), self.ekf.P.copy(), LABELS))
        if sup.phase == Ph.ENTRY:
            if est["agl"] <= self.cfg.supervisor.ignition_agl:
                sup.transition(Ph.DESCENT, self.t, f"estimated AGL {est['agl']:.0f} m <= ignition altitude")
                self._event("phase", "Powered descent initiated")
        elif sup.phase == Ph.DESCENT and est["agl"] <= self.cfg.supervisor.approach_agl:
            sup.transition(Ph.LANDING_APPROACH, self.t, f"estimated AGL {est['agl']:.0f} m <= approach altitude")
            self._event("phase", "Landing approach")
        if self.classic and self.cfg.hover_scan and sup.phase in (Ph.LANDING_APPROACH, Ph.SITE_ASSESSMENT, Ph.DIVERSION):
            self._hover_step(est)
            est["hover"] = self.hovering
        if sup.engine_enabled:
            self.cmd, self.ctrl_info = self.controller.compute(est, self.target, CONTROL_DT, self.cfg.lander)
            ge = getattr(self.controller, "guard_event", None)
            if ge and not getattr(self, "_guard_logged", False):
                self._guard_logged = True
                self.guard_flag = {**ge, "mission_t": round(self.t, 2)}
                self.audit.record(t=self.t, trigger="learned controller outside its experience: " + "; ".join(ge["reasons"]),
                                  decision=ge["action"], evidence={k: ge[k] for k in ("z_max", "z_input", "disagreement")},
                                  estimated_state={"p": est["p"], "v": est["v"], "agl": est["agl"]},
                                  uncertainty={"sigma": est["sigma"][:6]}, expected_outcome={"controller_in_charge": "pid" if ge["mode"] == "fallback" else "ppo"},
                                  safety_status="policy out of distribution")
                self._event("guard", f"PPO GUARD at t={self.t:.1f} s: " + "; ".join(ge["reasons"]) + f" → {ge['action']}")
        else:
            # coast: engine off, RCS holds vertical attitude
            from autonomy.control.lander_allocation import AllocationConfig, allocate
            c, info = allocate(np.array([0, 0, self.g]), est["euler"], est["omega"], est["mass"], self.cfg.lander,
                               AllocationConfig())
            self.cmd = ActuatorCommand(0.0, np.zeros(2), c.torque)
            self.ctrl_info = {"coast": True, **info}
        if self.t + 1e-9 >= self._next_pred and not self.fast:
            self._next_pred += 1.0
            self.prediction = self.predictor.predict(np.r_[est["p"], est["v"]], target=self.target, fuel=est["fuel"],
                                                     gravity=self.g)
            self.reference = self._reference(est)

    def _hover_step(self, est) -> None:
        """Hover-and-scan over each pad: arrest the descent, hold for hover_s seconds once stable while the lidar
        scans at 2 Hz, then commit to the final descent. A diversion during the hover restarts it over the new pad."""
        c = self.cfg
        key = (round(float(self.target[0]), 1), round(float(self.target[1]), 1))
        agl = est["agl"]
        if not self.hovering:
            if key not in self._hovered and 25.0 < agl <= c.hover_agl:
                self.hovering, self._hover_key, self._hover_t0, self._hover_start = True, key, None, self.t
                self._event("hover", f"HOVER & SCAN: arresting the descent at {agl:.0f} m above the pad to scan it")
            return
        if key != self._hover_key:                          # diverted while hovering: scan the new pad
            self._hovered.add(self._hover_key)
            self._hover_key, self._hover_t0 = key, None
            self._event("hover", f"Re-centring the hover over the new pad ({key[0]:.0f}, {key[1]:.0f})")
        if self._hover_t0 is None and abs(est["v"][2]) < 0.6:
            self._hover_t0 = self.t
            self._event("hover", f"Hovering at {agl:.0f} m — lidar scanning the pad and surroundings for {c.hover_s:.0f} s")
        done = self._hover_t0 is not None and self.t - self._hover_t0 >= c.hover_s
        if done or self.t - self._hover_start > 30.0 or agl < 20.0:
            self.hovering = False
            self._hovered.add(key)
            ss = self.site_status or {}
            self.hover_log.append({"t0": round(self._hover_start, 1), "t1": round(self.t, 1), "pad": list(key),
                                   "agl": round(agl, 1), "scans": self.hmap.scans, "pad_safe": ss.get("safe")})
            self._event("hover", f"Scan complete after {self.t - self._hover_start:.1f} s: pad "
                        + ("clear — final descent" if ss.get("safe") else "NOT clear — re-planning" if ss.get("covered") else "unsensed — continuing"))

    def _reference(self, est) -> list:
        p = est["p"].copy(); pts = [p.tolist()]
        for _ in range(60):
            agl = p[2] - self.cfg.lander.leg_height - self.dem.height(p[0], p[1])
            if agl <= 0: break
            p = p + desired_velocity(p, self.target, agl) * 1.0
            pts.append(p.tolist())
        return pts

    def _perception_step(self):
        sup = self.supervisor
        est = self.estimate()
        agl = est["agl"]
        sc = self.cfg.supervisor
        if agl > sc.assessment_agl or sup.phase in (Ph.ENTRY, Ph.DESCENT) or sup.terminal:
            return
        scan = self.hmap.scan(self.terrain, self.lander.pos, est["p"], max(self._agl_true(), 1.0), self.target,
                              self.seeds.stream("lidar"))
        sigma_h = self.ekf.position_sigma_h()
        a = self.assessor.assess(self.target[0], self.target[1], self.hmap, sigma_h)
        self.site_status = a.to_dict()
        self.last_scan = scan
        # after the first safe verdict the lidar keeps re-scanning the target every second (continuous monitoring)
        # without toggling the phase; a later hazard re-enters SITE ASSESSMENT through _divert
        if sup.phase == Ph.LANDING_APPROACH and not self._target_verified:
            sup.transition(Ph.SITE_ASSESSMENT, self.t, "terrain sensing within range")
            self._event("assessment", "Landing-site assessment started", scan=scan)
        if sup.phase in (Ph.SITE_ASSESSMENT, Ph.DIVERSION, Ph.LANDING_APPROACH) and a.covered:
            if a.safe:
                if sup.phase == Ph.SITE_ASSESSMENT and self.hmap.scans >= 2:
                    sup.transition(Ph.LANDING_APPROACH if self.diversions == 0 else Ph.DIVERSION, self.t,
                                   "target assessed safe")
                    self._event("assessment", "Target assessed safe — continuous lidar monitoring", site=a.to_dict())
                    self._target_verified = True
                return
            if not self.cfg.enable_diversion or agl < sc.min_divert_agl:
                return
            self._divert(est, a, sigma_h)

    def _divert(self, est, assessment, sigma_h):
        sup = self.supervisor
        if sup.phase != Ph.SITE_ASSESSMENT:
            sup.transition(Ph.SITE_ASSESSMENT, self.t, "hazard detected at target")
        t0 = time.perf_counter()
        plan = self.planner.plan(est, self.target, self.hmap, sigma_h, self.g)
        plan_ms = 1000 * (time.perf_counter() - t0)
        ev = self.audit.record(
            t=self.t, trigger="landing-site hazard detected",
            decision="divert" if plan["selected"] else "abort",
            evidence={"hazard_assessment": assessment.to_dict(), "lidar_scans": self.hmap.scans,
                      "rocks_perceived": len(self.hmap.rocks)},
            estimated_state={"p": est["p"], "v": est["v"], "agl": est["agl"], "fuel": est["fuel"]},
            uncertainty={"sigma_pos_h": sigma_h, "sigma": est["sigma"][:6]},
            expected_outcome=plan["selected"]["predicted"] if plan["selected"] else {},
            details={"alternatives": plan["evaluated"], "candidates_safe": plan["candidates_safe"],
                     "candidates_total": plan["candidates_total"], "planning_ms": plan_ms,
                     "previous_target": self.target.tolist()},
            safety_status="hazard")
        if plan["selected"]:
            sel = plan["selected"]
            self.target = np.array([sel["x"], sel["y"], self.dem.height(sel["x"], sel["y"])])
            self.diversions += 1
            sup.transition(Ph.DIVERSION, self.t, f"diverting to ({sel['x']:.0f}, {sel['y']:.0f})")
            self._event("diversion", f"Diverting {np.hypot(*(self.target[:2]-est['p'][:2])):.0f} m to safer site",
                        decision_id=ev.event_id, target=self.target.tolist())
        else:
            lb = self.planner.least_bad(est, self.target, self.hmap, sigma_h)
            if lb:
                self.target = np.array([lb["x"], lb["y"], self.dem.height(lb["x"], lb["y"])])
            sup.transition(Ph.ABORT, self.t, "no planned diversion feasible: emergency side-step")
            self._event("abort", ("Late hazard: emergency side-step to the least-hazardous reachable point "
                                  f"({self.target[0]:.0f}, {self.target[1]:.0f})") if lb else
                        "No feasible site: landing at the least-hazardous reachable point", decision_id=ev.event_id)
        self._pending_hazard_event = ev.event_id

    def _touchdown(self):
        L = self.lander
        p = L.pos
        vz, vh = float(L.vel[2]), float(np.hypot(L.vel[0], L.vel[1]))
        tilt = L.tilt_deg()
        slope = self.terrain.slope_at(p[0], p[1], self.cfg.lander.footprint_radius)
        rocks = self.terrain.rocks_near(p[0], p[1], self.cfg.lander.footprint_radius)
        max_rock = float(rocks[:, 3].max()) if len(rocks) else 0.0
        checks = {"vertical_speed_ok": abs(vz) <= 2.5, "horizontal_speed_ok": vh <= 1.2, "tilt_ok": tilt <= 10.0,
                  "slope_ok": slope <= 12.0, "rock_clearance_ok": max_rock <= 0.4}
        ok = all(checks.values())
        if self.supervisor.phase != Ph.TOUCHDOWN:
            self.supervisor.transition(Ph.TOUCHDOWN, self.t, "footpad contact")
        self._event("touchdown", f"Contact: vz={vz:.2f} m/s, vh={vh:.2f} m/s, tilt={tilt:.1f}°")
        aborted = any(h["to"] == Ph.ABORT.value for h in self.supervisor.history)
        self.supervisor.transition(Ph.MISSION_COMPLETE if ok else Ph.FAILED, self.t,
                                   "touchdown within limits" if ok else "touchdown limits violated: " +
                                   ", ".join(k for k, v in checks.items() if not v))
        result = {"touchdown_position": p.tolist(), "vertical_speed": vz, "horizontal_speed": vh, "tilt_deg": tilt,
                  "site_slope_deg": slope, "max_rock_height_under_footprint": max_rock, "checks": checks,
                  "aborted": aborted}
        if self._pending_hazard_event:
            self.audit.resolve(self._pending_hazard_event, {"landed_safely": ok, **result,
                                                            "error_to_selected_site_m": float(np.hypot(*(p[:2] - self.target[:2])))})
        self._finish("landed" if ok else "crash", result)

    def _finish(self, outcome: str, touchdown: dict | None = None):
        L = self.lander
        p = L.pos
        self.result = {
            "outcome": outcome, "success": outcome == "landed", "phase": self.supervisor.phase.value,
            "controller": self.cfg.controller, "seed": self.cfg.seed, "mission_time_s": round(self.t, 2),
            "fuel_used_kg": L.fuel_used, "fuel_remaining_kg": L.fuel,
            "landing_error_m": float(np.hypot(*(p[:2] - self.target[:2]))),
            "distance_from_original_target_m": float(np.hypot(*(p[:2] - self.original_target[:2]))),
            "final_target": self.target.tolist(), "original_target": self.original_target.tolist(),
            "diversions": self.diversions, "max_position_estimation_error_m": self.max_est_err,
            "final_position_estimation_error_m": float(np.linalg.norm(self.ekf.x[0:3] - p)),
            "ekf_rejected_measurements": self.ekf.rejected, "phase_history": self.supervisor.history,
            "touchdown": touchdown,
            "sensor_faults": {ch: {**d, "final_bias": self.sensors.drift_bias(ch, self.t),
                                   **((self.health.first.get(ch) or {}) if self.health else {}),
                                   "detection_delay_s": (round(self.health.first[ch]["isolated"] - d["t0"], 2)
                                                         if self.health and "isolated" in self.health.first.get(ch, {}) else None)}
                              for ch, d in self.sensors.drift.items()},
            "false_alarms": [ch for ch, f in (self.health.first.items() if self.health else []) if ch not in self.sensors.drift],
            "ppo_guard": getattr(self, "guard_flag", None),
            "hover_scans": getattr(self, "hover_log", []), "obstacles": getattr(self, "obstacles", []),
        }

    # ------------------------------------------------------------------
    def frame(self) -> dict:
        L = self.lander
        x = self.ekf.x
        truth_e = L.euler()
        return {
            "t": round(self.t, 3), "phase": self.supervisor.phase.value,
            "truth": {"position": L.pos.tolist(), "velocity": L.vel.tolist(), "euler": truth_e.tolist(),
                      "omega": L.omega.tolist(), "fuel": L.fuel, "mass": L.mass, "agl": self._agl_true(),
                      "acceleration": L.last_accel.tolist(), "tilt_deg": L.tilt_deg()},
            "estimate": {"position": x[0:3].tolist(), "velocity": x[3:6].tolist(), "euler": x[6:9].tolist(),
                         "accel_bias": x[9:12].tolist(), "sigma": self.ekf.sigma().tolist(),
                         "agl": float(x[2] - self.cfg.lander.leg_height - self.dem.height(x[0], x[1]))},
            "error": {"position": (x[0:3] - L.pos).tolist(), "velocity": (x[3:6] - L.vel).tolist(),
                      "euler": (x[6:9] - truth_e).tolist()},
            "actuators": {"throttle": L.throttle, "lateral": L.lateral.tolist(), "torque": L.torque.tolist()},
            "command": self.cmd.to_dict(),
            "controller": {k: v for k, v in self.ctrl_info.items() if k in ("v_des", "a_cmd", "tilt_cmd_deg", "mpc", "att_error_deg", "ppo")},
            "target": self.target.tolist(),
            "predicted_touchdown": self.prediction.get("touchdown_point"),
            "innovations": {k: {"nis": v["nis"], "accepted": v["accepted"]} for k, v in self.ekf.last_innovation.items()},
        }

    def snapshot(self, include_paths: bool = True) -> dict:
        snap = {"module": "touchdown", "t": round(self.t, 3), "phase": self.supervisor.phase.value,
                "frame": self.telemetry[-1] if self.telemetry else self.frame(),
                "site_status": self.site_status, "diversions": self.diversions, "result": self.result,
                "events": self.events[-30:], "environment": {**self.environment, "name": self.cfg.environment,
                                                              "airless": self.cfg.planet.rho0 <= 0.0},
                "original_target": self.original_target.tolist(), "obstacles": self.obstacles,
                "drift": {k: {**v, "bias_now": round(self.sensors.drift_bias(k, self.t), 3)} for k, v in self.sensors.drift.items()},
                "hover": {"active": self.hovering, "stable_for": round(self.t - self._hover_t0, 1) if (self.hovering and self._hover_t0) else 0.0,
                          "duration": self.cfg.hover_s, "log": self.hover_log, "enabled": self.classic and self.cfg.hover_scan},
                "sensor_health": self.health.snapshot() if self.health else None}
        tx, ty = self.target[:2]
        reg = self.hmap.scan_regions[-1] if self.hmap.scan_regions else None
        snap["perception"] = {
            "scans": self.hmap.scans, "region": reg, "last_scan": self.last_scan,
            "rocks": [[round(r[0], 1), round(r[1], 1), round(r[3], 2)] for r in self.hmap.rocks
                      if (r[0] - tx) ** 2 + (r[1] - ty) ** 2 < 120 ** 2][:400],
            "hazard_limit_m": self.cfg.site.max_rock_height,
            "assessment_agl": self.cfg.supervisor.assessment_agl, "min_divert_agl": self.cfg.supervisor.min_divert_agl}
        if include_paths:
            snap["predicted_trajectory"] = self.prediction.get("trajectory", [])[::2]
            snap["desired_trajectory"] = self.reference
            if hasattr(self.controller, "predicted_trajectory"):
                snap["mpc_prediction"] = self.controller.predicted_trajectory()
            snap["actual_trajectory"] = [f["truth"]["position"] for f in self.telemetry[::5]]
            snap["estimated_trajectory"] = [f["estimate"]["position"] for f in self.telemetry[::5]]
        return snap

    def scene(self) -> dict:
        """Static scene for visualisation (true terrain grid, rocks, craters) + perceived hazard map."""
        rocks = self.terrain.rock_array()
        big = rocks[rocks[:, 3] > 0.3] if len(rocks) else rocks
        T = self.terrain
        cx, cy = self.original_target[:2]
        i0 = int(np.clip((cx - 260 - T.origin) / T.res, 0, T.n - 1)); i1 = int(np.clip((cx + 260 - T.origin) / T.res, 0, T.n - 1))
        j0 = int(np.clip((cy - 260 - T.origin) / T.res, 0, T.n - 1)); j1 = int(np.clip((cy + 260 - T.origin) / T.res, 0, T.n - 1))
        detail = {"x0": T.origin + i0 * T.res, "y0": T.origin + j0 * T.res, "resolution_m": T.res,
                  "heights": np.round(T.heights[i0:i1 + 1, j0:j1 + 1], 2).tolist(),
                  "slope_deg": np.round(T.slope_deg[i0:i1 + 1, j0:j1 + 1], 1).tolist()}
        return {"terrain": self.terrain.downsampled(5), "detail": detail, "rocks": np.round(big, 2).tolist(),
                "craters": self.terrain.craters, "original_target": self.original_target.tolist(),
                "perceived": self.hmap.to_dict()}

    # -- interventions ---------------------------------------------------
    def inject_hazard(self, x: float | None = None, y: float | None = None, radius: float = 25.0) -> dict:
        x = float(self.target[0] if x is None else x)
        y = float(self.target[1] if y is None else y)
        self.terrain.add_hazard_field(x, y, radius, self.seeds.stream("hazard_injection"))
        d_target = float(np.hypot(x - self.target[0], y - self.target[1]))
        affects = d_target < radius + self.cfg.site.footprint_radius + 4.0
        self.obstacles.append({"x": x, "y": y, "radius": radius, "t": round(self.t, 2), "affects_target": affects})
        self._event("injection", f"Obstacle field placed in TRUE terrain at ({x:.0f}, {y:.0f}) r={radius:.0f} m, "
                                 f"{d_target:.0f} m from the current target"
                                 + (" — the lander must detect it by lidar and re-plan" if affects else
                                    " — outside the landing footprint"))
        return {"x": x, "y": y, "radius": radius, "distance_to_target_m": d_target, "affects_target": affects,
                "can_still_divert": self._agl_true() > self.cfg.supervisor.min_divert_agl and not self.supervisor.terminal}

    def set_environment(self, wind_speed: float | None = None, wind_dir_deg: float | None = None,
                        gust_std: float | None = None, dust: float | None = None) -> dict:
        """Live environmental conditions. Wind/gusts change the true atmosphere the lander flies through
        (the guidance closes the loop on the resulting drift); dust degrades the hazard lidar."""
        env = self.environment
        airless = self.cfg.planet.rho0 <= 0.0
        if not airless:
            if wind_speed is not None: env["wind_speed"] = float(wind_speed)
            if wind_dir_deg is not None: env["wind_dir_deg"] = float(wind_dir_deg)
            if gust_std is not None: env["gust_std"] = float(gust_std)
            if dust is not None: env["dust"] = float(np.clip(dust, 0.0, 1.0))
            a = np.radians(env["wind_dir_deg"])
            self.cfg.planet.wind = [env["wind_speed"] * np.cos(a), env["wind_speed"] * np.sin(a), 0.0]
            self.cfg.planet.gust_std = env["gust_std"]
            dp, nb, npm, mr = self._lidar_base
            d = env["dust"]
            L = self.cfg.lidar
            L.detect_prob, L.range_noise_base, L.range_noise_per_m, L.max_range = dp * (1 - 0.45 * d), nb * (1 + 3 * d), npm * (1 + 3 * d), mr * (1 - 0.5 * d)
        self._event("environment", ("Environment unchanged: airless body (no wind, no dust storms)" if airless else
                                    f"Environment: wind {env['wind_speed']:.1f} m/s from {env['wind_dir_deg']:.0f}°, "
                                    f"gusts σ {env['gust_std']:.1f} m/s, dust opacity {env['dust']:.2f}"))
        return {**env, "airless": airless}

    def inject_disturbance(self, force: list[float], duration: float = 3.0, wind: list[float] | None = None) -> dict:
        self.lander.ext_force = np.asarray(force, float)
        self._disturb_until = self.t + duration
        if wind is not None:
            self.atm.extra_wind = np.asarray(wind, float)
        self._event("injection", f"Disturbance force {force} N for {duration}s" + (f", wind {wind}" if wind else ""))
        return {"force": force, "duration": duration, "wind": wind}

    def run(self, max_time: float | None = None) -> dict:
        t_wall = time.perf_counter()
        limit = max_time or self.cfg.supervisor.max_mission_time + 1
        while not self.supervisor.terminal and self.t < limit:
            self.step()
        self.wall_time += time.perf_counter() - t_wall
        return self.result or {}

    def debrief(self) -> dict:
        tl = self.telemetry
        return {"result": self.result, "config": self.cfg.to_dict(), "decisions": self.audit.to_list(),
                "events": self.events, "phase_history": self.supervisor.history,
                "series": {
                    "t": [f["t"] for f in tl],
                    "agl": [f["truth"]["agl"] for f in tl],
                    "vz": [f["truth"]["velocity"][2] for f in tl],
                    "fuel": [f["truth"]["fuel"] for f in tl],
                    "throttle": [f["actuators"]["throttle"] for f in tl],
                    "pos_err": [float(np.linalg.norm(f["error"]["position"])) for f in tl],
                    "pos_sigma": [float(np.linalg.norm(f["estimate"]["sigma"][0:3])) for f in tl],
                }}
