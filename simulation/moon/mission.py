"""ASTRA Moon Landing mission (independent of Mars TOUCHDOWN).

Phases (Apollo terminology):
  APPROACH (P64)          Apollo-style quadratic (jerk + snap) guidance with fixed final time: the commanded
                          acceleration a(tau) = a0 + j tau + s tau^2/2 meets position, velocity AND acceleration
                          targets at low gate (net acceleration ~0 => thrust vertical at hand-over), re-solved at 10 Hz
  TERMINAL DESCENT (P66)  rate-of-descent mode: vertical speed target, horizontal velocity nulling
  CONTACT                 probe contact light -> engine shutdown after the crew/automation delay
  TOUCHDOWN -> LANDED | FAILED
Navigation: IMU propagation (noisy specific force) + landing-radar altitude/velocity updates
(complementary filter with fixed gains). Rates: physics 50 Hz, nav/guidance 10 Hz, telemetry 10 Hz.
Dust: plume-surface interaction erosion model (empirical, documented in docs/MOON_LANDING.md).
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import numpy as np

from autonomy.decision.audit import DecisionAudit
from simulation.common.rng import SeedManager
from simulation.moon.environment import MOON_GRAVITY, LunarTerrain, LunarTerrainConfig
from simulation.moon.lander import LunarLander, LunarLanderParams

DT = 0.02
GUID_DT = 0.1
TLM_DT = 0.1

PHASES = ["APPROACH (P64)", "TERMINAL DESCENT (P66)", "CONTACT", "TOUCHDOWN", "LANDED", "FAILED"]


@dataclass
class MoonConfig:
    seed: int = 11
    controller: str = "apollo-guidance"
    high_gate_altitude: float = 2000.0        # m above target
    high_gate_downrange: float = 4200.0       # m before target
    initial_velocity: list = field(default_factory=lambda: [70.0, 0.0, -24.0])
    crossrange_offset: float = 60.0
    approach_time: float = 95.0               # fixed final time of the approach phase, s
    low_gate_altitude: float = 35.0
    terminal_descent_rate: float = 1.0        # m/s (Apollo P66 typical ~1 m/s)
    shutdown_delay: float = 0.8               # contact light -> engine off, s
    radar_noise_alt: float = 0.01             # fraction
    radar_noise_vel: float = 0.3              # m/s
    imu_noise: float = 0.02                   # m/s^2
    lander: LunarLanderParams = field(default_factory=LunarLanderParams)
    terrain: LunarTerrainConfig = field(default_factory=LunarTerrainConfig)

    @staticmethod
    def from_dict(d: dict) -> "MoonConfig":
        c = MoonConfig()
        for k, v in (d or {}).items():
            if v is None:
                continue
            if k in ("lander", "terrain") and isinstance(v, dict):
                for kk, vv in v.items():
                    setattr(getattr(c, k), kk, vv)
            elif hasattr(c, k):
                setattr(c, k, v)
        return c

    def to_dict(self) -> dict:
        return asdict(self)


class MoonLandingMission:
    def __init__(self, cfg: MoonConfig):
        self.cfg = cfg
        self.seeds = SeedManager(cfg.seed)
        self.terrain = LunarTerrain(cfg.terrain, self.seeds.stream("lunar_terrain"))
        tx, ty = cfg.terrain.target
        self.target = np.array([tx, ty, self.terrain.height(tx, ty)])
        p0 = np.array([tx - cfg.high_gate_downrange, ty + cfg.crossrange_offset, self.target[2] + cfg.high_gate_altitude])
        self.lander = LunarLander(cfg.lander, p0, np.array(cfg.initial_velocity, float), pitch=np.radians(-35))
        self.rng = self.seeds.stream("moon_sensors")
        self.est_p = p0 + self.rng.normal(0, [30, 30, 8])
        self.est_v = np.array(cfg.initial_velocity, float) + self.rng.normal(0, 0.5, 3)
        self.t = 0.0
        self.phase = PHASES[0]
        self.history: list[dict] = []
        self.events: list[dict] = []
        self.telemetry: list[dict] = []
        self.audit = DecisionAudit("moon")
        self.terminal = False
        self.result: dict | None = None
        self.throttle_cmd = 0.6
        self.tau_cmd = np.zeros(2)
        self.a_cmd = np.zeros(3)
        self.plan: list = []
        self._next_guid = 0.0
        self._next_tlm = 0.0
        self._contact_t: float | None = None
        self.max_dust = 0.0
        self.dust_total = 0.0
        self.trail: list = []
        self._event("phase", f"High gate: {cfg.high_gate_altitude:.0f} m altitude, {cfg.high_gate_downrange:.0f} m downrange")

    # ------------------------------------------------------------------
    def _event(self, kind, msg, **d):
        self.events.append({"t": round(self.t, 2), "kind": kind, "message": msg, **d})

    def _go(self, phase: str, why: str):
        self.history.append({"t": round(self.t, 2), "from": self.phase, "to": phase, "reason": why})
        self.phase = phase
        self._event("phase", f"{phase}: {why}")

    def agl(self, p=None) -> float:
        p = self.lander.pos if p is None else p
        return float(p[2] - self.cfg.lander.leg_height - self.terrain.height(p[0], p[1]))

    def dust_rate(self) -> float:
        """Plume-surface erosion (empirical): zero above ~40 m, rising roughly exponentially as the
        plume stagnation pressure on the regolith grows. kg/s, order of Apollo post-flight estimates."""
        h = self.agl()
        T = self.lander.thrust()
        if h > 40 or T <= 0:
            return 0.0
        return float(1.2 * (T / 15_000.0) * np.exp(-max(h, 0.0) / 9.0))

    # ------------------------------------------------------------------
    def _navigate(self, dt):
        L = self.lander
        f_meas = L.last_accel + np.array([0, 0, MOON_GRAVITY]) + self.rng.normal(0, self.cfg.imu_noise, 3)
        self.est_v = self.est_v + (f_meas - np.array([0, 0, MOON_GRAVITY])) * dt
        self.est_p = self.est_p + self.est_v * dt
        h_true = L.pos[2] - self.terrain.height(L.pos[0], L.pos[1])
        if h_true < 6000:   # landing radar in range: altitude + velocity updates (complementary gains)
            h_meas = h_true * (1 + self.rng.normal(0, self.cfg.radar_noise_alt)) + self.rng.normal(0, 0.3)
            v_meas = L.vel + self.rng.normal(0, self.cfg.radar_noise_vel, 3)
            h_est = self.est_p[2] - self.terrain.height(self.est_p[0], self.est_p[1])
            self.est_p[2] += 0.3 * (h_meas - h_est)
            self.est_v += 0.3 * (v_meas - self.est_v)

    def _guide(self):
        c, L, p = self.cfg, self.lander, self.cfg.lander
        m = L.mass
        g = np.array([0, 0, -MOON_GRAVITY])
        r, v = self.est_p.copy(), self.est_v.copy()
        h_est = r[2] - p.leg_height - self.terrain.height(r[0], r[1])
        if self.phase == PHASES[0]:
            t_go = c.approach_time - self.t
            r_f = self.target + np.array([0, 0, c.low_gate_altitude + p.leg_height])
            v_f = np.array([0, 0, -c.terminal_descent_rate * 1.5])
            if t_go < 2.0 or h_est < c.low_gate_altitude:
                ev = self.audit.record(t=self.t, trigger=f"low gate: t_go={t_go:.1f} s, AGL={h_est:.1f} m",
                                       decision="switch to terminal descent (P66 rate-of-descent)",
                                       estimated_state={"p": r, "v": v, "agl": h_est},
                                       uncertainty={"radar_alt_noise_frac": c.radar_noise_alt},
                                       expected_outcome={"descent_rate": c.terminal_descent_rate})
                self._p66_event = ev.event_id
                self._go(PHASES[1], f"low gate reached at {h_est:.0f} m AGL")
            else:
                a_f = np.zeros(3)
                t = t_go
                A = np.array([[t, t ** 2 / 2, t ** 3 / 6], [t ** 2 / 2, t ** 3 / 6, t ** 4 / 24], [1, t, t ** 2 / 2]])
                coef = np.linalg.solve(A, np.vstack([v_f - v, r_f - r - v * t, a_f]))   # rows: a0, j, snap per axis
                c0, c1, c2 = coef
                self.a_cmd = c0 - g
                self.plan = [(r + v * k + c0 * k ** 2 / 2 + c1 * k ** 3 / 6 + c2 * k ** 4 / 24).tolist() for k in np.linspace(0, t_go, 30)]
        if self.phase == PHASES[1]:
            vz_des = -max(c.terminal_descent_rate, min(3.0, 0.08 * h_est))
            dxy = (self.target - r)[:2]
            vh_des = np.clip(0.03 * dxy, -1.0, 1.0)
            a_h = np.clip(0.18 * (vh_des - v[:2]), -0.35, 0.35)     # <= ~12 deg tilt: matched to RCS authority
            a_z = 1.2 * (vz_des - v[2])
            self.a_cmd = np.array([a_h[0], a_h[1], a_z]) - g
            self.plan = [r.tolist(), [self.target[0], self.target[1], self.target[2] + p.leg_height]]
        if self.phase in PHASES[:2]:
            a = self.a_cmd.copy()
            a[2] = max(a[2], 0.2)
            T = m * np.linalg.norm(a)
            d = a / np.linalg.norm(a)
            tilt = np.arccos(np.clip(d[2], -1, 1))
            if tilt > np.radians(50):
                h = np.hypot(d[0], d[1]); d = np.array([d[0] / h * np.sin(np.radians(50)), d[1] / h * np.sin(np.radians(50)), np.cos(np.radians(50))])
            th_d = np.arctan2(d[0], d[2]); ph_d = np.arcsin(np.clip(-d[1], -1, 1))
            wn, z = 0.7, 1.0      # attitude bandwidth limited by RCS torque / LM inertia (~0.05 rad/s^2)
            th, ph, q, rr = L.x[6], L.x[7], L.x[8], L.x[9]
            self.tau_cmd = np.array([p.inertia_pitch * (wn ** 2 * (th_d - th) - 2 * z * wn * q),
                                     p.inertia_roll * (wn ** 2 * (ph_d - ph) - 2 * z * wn * rr)])
            along = T * float(d @ L.thrust_dir())
            self.throttle_cmd = along / p.max_thrust
        else:
            self.tau_cmd = np.array([-p.inertia_pitch * 2 * L.x[8], -p.inertia_roll * 2 * L.x[9]])

    # ------------------------------------------------------------------
    def step(self):
        if self.terminal:
            return
        L, c = self.lander, self.cfg
        if self.t + 1e-9 >= self._next_guid:
            self._next_guid += GUID_DT
            self._guide()
        L.step(self.throttle_cmd, self.tau_cmd, DT)
        self._navigate(DT)
        self.t += DT
        dr = self.dust_rate()
        self.max_dust = max(self.max_dust, dr)
        self.dust_total += dr * DT
        h = self.agl()
        if self.phase in PHASES[:2] and h <= c.lander.probe_length:
            self._contact_t = self.t
            self._go(PHASES[2], f"contact light (probe {c.lander.probe_length} m) at vz={L.vel[2]:.2f} m/s")
        if self.phase == PHASES[2] and L.engine_on and self.t - self._contact_t >= c.shutdown_delay:
            L.engine_on = False
            L.throttle = 0.0
            self._event("engine", "Descent engine shutdown")
        if L.propellant <= 0 and L.engine_on and self.phase in PHASES[:2]:
            L.engine_on = False
            self._event("engine", "Propellant depleted — engine flame-out")
        if h <= 0:
            self._touchdown()
        elif self.t > 400:
            self._finish("timeout", None)
        if self.t + 1e-9 >= self._next_tlm or self.terminal:
            self._next_tlm += TLM_DT
            self.telemetry.append(self.frame())
            if len(self.telemetry) % 5 == 0:
                self.trail.append(L.pos.round(2).tolist())

    def _touchdown(self):
        L, p = self.lander, self.cfg.lander
        vz, vh = float(L.vel[2]), float(np.hypot(L.vel[0], L.vel[1]))
        tilt = float(np.degrees(np.arccos(np.clip(np.cos(L.x[6]) * np.cos(L.x[7]), -1, 1))))
        slope = self.terrain.slope_deg(L.pos[0], L.pos[1], p.footprint_radius)
        under = [b for b in self.terrain.boulders if np.hypot(b[0] - L.pos[0], b[1] - L.pos[1]) < p.footprint_radius]
        max_b = max([b[2] for b in under], default=0.0)
        checks = {"vertical_speed_ok": abs(vz) <= 3.0, "horizontal_speed_ok": vh <= 1.2, "tilt_ok": tilt <= 12.0,
                  "slope_ok": slope <= 12.0, "boulder_clearance_ok": max_b <= 0.6}
        ok = all(checks.values())
        self._go(PHASES[3], f"footpad contact vz={vz:.2f} m/s vh={vh:.2f} m/s")
        td = {"vertical_speed": vz, "horizontal_speed": vh, "tilt_deg": tilt, "site_slope_deg": slope,
              "max_boulder_under_footprint_m": max_b, "checks": checks, "position": L.pos.tolist()}
        if getattr(self, "_p66_event", None):
            self.audit.resolve(self._p66_event, {"landed_safely": ok, **td})
        self._go(PHASES[4] if ok else PHASES[5], "all touchdown limits met" if ok else
                 "limits violated: " + ", ".join(k for k, v in checks.items() if not v))
        self._finish("landed" if ok else "hard_landing", td)

    def _finish(self, outcome, td):
        if self.terminal:
            return
        self.terminal = True
        L = self.lander
        self.result = {"outcome": outcome, "success": outcome == "landed", "controller": self.cfg.controller,
                       "seed": self.cfg.seed, "mission_time_s": round(self.t, 2),
                       "propellant_remaining_kg": L.propellant,
                       "propellant_used_kg": self.cfg.lander.propellant - L.propellant,
                       "landing_error_m": float(np.hypot(*(L.pos[:2] - self.target[:2]))),
                       "nav_error_m": float(np.linalg.norm(self.est_p - L.pos)),
                       "max_dust_rate_kg_s": self.max_dust, "dust_eroded_kg": self.dust_total,
                       "phase_history": self.history, "touchdown": td}
        self.telemetry.append(self.frame())

    # ------------------------------------------------------------------
    def frame(self) -> dict:
        L = self.lander
        return {"t": round(self.t, 2), "phase": self.phase,
                "truth": {"position": L.pos.tolist(), "velocity": L.vel.tolist(), "pitch": float(L.x[6]),
                          "roll": float(L.x[7]), "agl": self.agl(), "mass": L.mass, "propellant": L.propellant},
                "estimate": {"position": self.est_p.tolist(), "velocity": self.est_v.tolist()},
                "error": {"position": float(np.linalg.norm(self.est_p - L.pos))},
                "engine": {"on": L.engine_on, "throttle": L.throttle, "thrust_n": L.thrust(),
                           "rcs_torque": L.tau.tolist(), "a_cmd": self.a_cmd.tolist()},
                "dust_rate": self.dust_rate(), "target": self.target.tolist()}

    def snapshot(self, include_paths: bool = True) -> dict:
        s = {"module": "moon", "t": round(self.t, 2), "phase": self.phase,
             "frame": self.telemetry[-1] if self.telemetry else self.frame(), "result": self.result,
             "events": self.events[-30:], "phases": PHASES}
        if include_paths:
            s["trail"] = self.trail + [self.lander.pos.round(2).tolist()]
            s["plan"] = self.plan
        return s

    def scene(self) -> dict:
        return {"terrain": self.terrain.visual(), "lander": asdict(self.cfg.lander)}

    def run(self, max_time=None):
        while not self.terminal and self.t < (max_time or 1e9):
            self.step()
        return self.result or {}

    def debrief(self) -> dict:
        tl = self.telemetry
        return {"result": self.result, "config": self.cfg.to_dict(), "decisions": self.audit.to_list(), "events": self.events,
                "series": {"t": [f["t"] for f in tl], "agl": [f["truth"]["agl"] for f in tl],
                           "vz": [f["truth"]["velocity"][2] for f in tl], "throttle": [f["engine"]["throttle"] for f in tl]}}
