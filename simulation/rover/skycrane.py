"""Sky-crane landing of the rover onto the crater floor (Mars), computed - not keyframed.

Bodies
  descent stage (DS): point mass with throttled engines, vertical PD on a velocity profile and lateral nulling
  rover: suspended below the DS on a bridle of length L(t); swing in two vertical planes modelled as a
  pendulum with a moving, accelerating pivot and time-varying length:
      theta'' = -((g + a_pz) sin(theta) + a_px cos(theta)) / L - 2 L' theta' / L
Phases: POWERED DESCENT -> SKY CRANE (bridle deploy, DS at constant 0.75 m/s) -> TOUCHDOWN (wheel contact,
tension loss detected) -> BRIDLE CUT -> FLYAWAY (DS pitches 45 deg, full throttle, departs).
Integrated with RK4-free semi-implicit Euler at 200 Hz (stiffness is low); output at 20 Hz.
Parameters follow published Mars 2020 EDL values (bridle 6.4-7.6 m, 0.75 m/s at touchdown); masses and thrust
are scaled by the configured rover mass so the landed vehicle is the same one that then drives in PyBullet.
"""
from __future__ import annotations

import numpy as np

G_MARS = 3.72076


def simulate_skycrane(landing_xy, ground_fn, heading: float = 0.0, seed: int = 0, rover_mass: float = 1025.0) -> dict:
    rng = np.random.default_rng(seed)
    gx, gy = landing_xy
    z0 = ground_fn(gx, gy)
    # Mars 2020 mass ratios (rover 1025 kg, descent stage 1070 kg, 8 x 3.06 kN) scaled to the simulated rover
    k = rover_mass / 1025.0
    m_rover, m_ds = rover_mass, 1070.0 * k
    t_max_thrust = 8 * 3060.0 * k
    bridle_max, winch = 7.5, 0.75
    rover_clear = 0.55                     # wheel bottom below the bridle attach point when hanging
    ds = np.array([gx - 18.0 + rng.normal(0, 2), gy + rng.normal(0, 2), z0 + 130.0])
    v = np.array([1.6, 0.0, -18.0])
    L, Ld = 0.4, 0.0
    th = np.zeros(2); thd = np.array([0.0, 0.0])
    phase = "POWERED DESCENT"
    dt, t = 0.005, 0.0
    frames, events = [], []
    rover_pos = ds - np.array([0, 0, L + 0.9])
    rover_on_ground = False
    cut_t = None
    ds_pitch = 0.0
    throttle = 0.6
    a_prev = np.zeros(3)
    next_out = 0.0
    touchdown_info = None

    def ev(msg):
        events.append({"t": round(t, 2), "phase": phase, "message": msg})

    ev("Powered descent: descent stage tracking velocity profile")
    while t < 60.0:
        h_ds = ds[2] - z0
        m = m_ds + (0 if (rover_on_ground or cut_t is not None) else m_rover)
        # --- guidance ---
        if phase == "POWERED DESCENT":
            vz_des = -max(0.75, min(18.0, 0.32 * (h_ds - 21.0) + 0.75))
            if h_ds <= 21.0:
                phase = "SKY CRANE"; ev("Sky crane: bridles + umbilical deploy, constant 0.75 m/s descent")
        elif phase in ("SKY CRANE", "TOUCHDOWN"):
            vz_des = -0.75
        if phase == "FLYAWAY":
            ds_pitch = min(ds_pitch + np.radians(25) * dt, np.radians(45))
            a_cmd = np.array([0.0, 0.0, 0.0])
            throttle = 1.0
            thrust_vec = throttle * t_max_thrust * np.array([np.sin(ds_pitch) * np.cos(heading), np.sin(ds_pitch) * np.sin(heading), np.cos(ds_pitch)])
        else:
            a_z = 2.0 * (vz_des - v[2]) + G_MARS
            a_h = np.clip(0.6 * (np.array([gx, gy]) - ds[:2]) - 1.2 * v[:2], -2.5, 2.5)
            a_cmd = np.array([a_h[0], a_h[1], a_z])
            thrust_vec = m * a_cmd
            n = np.linalg.norm(thrust_vec)
            if n > t_max_thrust:
                thrust_vec *= t_max_thrust / n
            throttle = float(np.linalg.norm(thrust_vec) / t_max_thrust)
        # --- descent-stage dynamics (bridle tension acts on DS while rover hangs) ---
        tension = 0.0
        if not rover_on_ground and cut_t is None:
            tension = m_rover * (G_MARS + a_prev[2])
        acc = thrust_vec / m_ds - np.array([0, 0, G_MARS]) - np.array([0, 0, tension / m_ds]) if (rover_on_ground or cut_t is not None) \
            else thrust_vec / m - np.array([0, 0, G_MARS])
        v = v + acc * dt
        ds = ds + v * dt
        a_prev = acc
        # --- bridle & pendulum ---
        if phase == "SKY CRANE" and not rover_on_ground:
            Ld = winch if L < bridle_max else 0.0
            L = min(L + Ld * dt, bridle_max)
        else:
            Ld = 0.0
        if phase == "POWERED DESCENT":
            th[:] = 0.0; thd[:] = 0.0                      # rover rigidly mated to the descent stage
            rover_pos = ds - np.array([0, 0, L + 0.9])
        elif not rover_on_ground and cut_t is None:
            for k in range(2):
                a_px = acc[k]
                thdd = -((G_MARS + acc[2]) * np.sin(th[k]) + a_px * np.cos(th[k])) / max(L, 0.3) - 2 * Ld * thd[k] / max(L, 0.3)
                thd[k] += thdd * dt - 0.02 * thd[k] * dt
                th[k] += thd[k] * dt
            rover_pos = ds + np.array([L * np.sin(th[0]), L * np.sin(th[1]), -L * np.cos(th[0]) * np.cos(th[1]) - 0.9])
            if rover_pos[2] - rover_clear <= ground_fn(rover_pos[0], rover_pos[1]):
                rover_on_ground = True
                touchdown_info = {"t": round(t, 3), "vertical_speed": float(v[2] - Ld), "swing_deg": np.degrees(th).round(2).tolist(),
                                  "position": rover_pos[:2].round(3).tolist(), "error_m": float(np.hypot(rover_pos[0] - gx, rover_pos[1] - gy))}
                phase = "TOUCHDOWN"; ev(f"Wheels on ground at {abs(v[2] - Ld):.2f} m/s; bridle tension lost")
        if phase == "TOUCHDOWN" and cut_t is None and t - touchdown_info["t"] > 0.7:
            cut_t = t; phase = "BRIDLE CUT"; ev("Pyrotechnic cutters fire: bridles and umbilical released")
        if phase == "BRIDLE CUT" and t - cut_t > 0.4:
            phase = "FLYAWAY"; ev("Flyaway: descent stage pitches 45° and departs at full throttle")
        if t >= next_out:
            next_out += 0.05
            frames.append({"t": round(t, 3), "phase": phase, "ds": ds.round(3).tolist(), "ds_pitch": float(ds_pitch),
                           "ds_velocity": v.round(3).tolist(), "throttle": throttle,
                           "rover": rover_pos.round(3).tolist(), "swing": th.round(4).tolist(),
                           "bridle": L if cut_t is None else 0.0, "rover_on_ground": rover_on_ground,
                           "altitude": float(h_ds)})
        t += dt
        if phase == "FLYAWAY" and ds[2] - z0 > 60 and np.hypot(ds[0] - gx, ds[1] - gy) > 80:
            ev("Descent stage clear of the landing site (impacts ~650 m away)")
            break
    return {"frames": frames, "events": events, "touchdown": touchdown_info, "ground": z0,
            "landing_point": [gx, gy], "heading": heading,
            "parameters": {"rover_mass": m_rover, "descent_stage_mass": m_ds, "bridle_max": bridle_max, "winch_rate": winch,
                           "max_thrust": t_max_thrust, "gravity": G_MARS}}
