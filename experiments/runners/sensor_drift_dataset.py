"""Synthetic "lying sensor" dataset + evidence plots.

Runs full TOUCHDOWN missions (physics, sensors, EKF, guidance) in three groups:
  clean      no fault                         -> false-alarm rate of the sensor-health monitor
  drift/on   slow bias drift, monitor ON       -> detection rate, delay, correct blame, landing outcome
  drift/off  same drifts and seeds, monitor OFF -> what the lie does when nobody catches it
Every navigation-sensor sample is recorded (measurement, truth, true injected bias, normalised EKF
innovation, CUSUM, status) to CSV; a summary.json and PNG figures are written next to them.

Usage:  python -m experiments.runners.sensor_drift_dataset --seeds 6 --workers 8
Output: data/sensor_drift_dataset/{runs/*.csv, summary.json, fig_*.png}
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from backend.core.config import settings

CHANNELS = ("altimeter", "position", "velocimeter")
DRIFTS = [("altimeter", 0.5), ("altimeter", 1.0), ("position", 0.6), ("velocimeter", 0.05)]
ONSET = 20.0


def _run(job) -> dict:
    from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
    group, seed, drift, out_dir = job
    cfg = TouchdownConfig.from_dict({"seed": seed, "sensor_health": group != "drift_off"})
    m = TouchdownMission(cfg)
    rows, last_t = [], {c: -1.0 for c in CHANNELS}
    injected = False
    while not m.supervisor.terminal and m.t < 400:
        if drift and not injected and m.t >= ONSET:
            m.inject_drift(drift[0], drift[1]); injected = True
        m.step()
        for ch in CHANNELS:
            inn = m.ekf.last_innovation.get(ch)
            if not inn or inn["t"] == last_t[ch]:
                continue
            last_t[ch] = inn["t"]
            i = 0 if ch == "altimeter" else 2
            e = inn["innovation"][i] / np.sqrt(max(inn["S_diag"][i], 1e-9))
            truth = {"altimeter": m._agl_true() + m.cfg.lander.leg_height, "position": m.lander.pos[2], "velocimeter": m.lander.vel[2]}[ch]
            bias = m.sensors.drift_bias(ch, m.t)
            st = m.health.status[ch] if m.health else "OFF"
            g = m.health.cusum[ch].value if m.health else None
            rows.append((round(m.t, 2), ch, round(truth + bias, 3), round(truth, 3), round(bias, 3),
                         round(float(e), 4), None if g is None else round(g, 3), st))
    name = f"{group}_{drift[0] if drift else 'none'}_{drift[1] if drift else 0}_s{seed}"
    with open(Path(out_dir) / "runs" / f"{name}.csv", "w") as f:
        f.write("t,channel,truth_plus_bias,truth,true_bias,normalised_innovation,cusum,status\n")
        for r in rows:
            f.write(",".join("" if v is None else str(v) for v in r) + "\n")
    r = m.result or {}
    first = m.health.first if m.health else {}
    blamed = sorted(ch for ch, f in first.items() if "isolated" in f)
    return {"name": name, "group": group, "seed": seed, "drift_channel": drift[0] if drift else None,
            "drift_rate": drift[1] if drift else 0.0, "outcome": r.get("outcome"), "success": bool(r.get("success")),
            "touchdown_vz": (r.get("touchdown") or {}).get("vertical_speed"),
            "landing_error_m": r.get("landing_error_m"), "final_nav_error_m": r.get("final_position_estimation_error_m"),
            "isolated": blamed, "suspected": sorted(first),
            "detection_t": first.get(drift[0], {}).get("isolated") if drift else None,
            "suspect_t": first.get(drift[0], {}).get("suspect") if drift else None,
            "detection_delay_s": (round(first[drift[0]]["isolated"] - ONSET, 2) if drift and "isolated" in first.get(drift[0], {}) else None),
            "correct_blame": (blamed == [drift[0]]) if drift and group == "drift_on" else None,
            "false_alarm": bool(blamed) if not drift else None}


def _plots(out: Path, runs: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9})
    alt_on = next(r for r in runs if r["group"] == "drift_on" and r["drift_channel"] == "altimeter" and r["drift_rate"] == 0.5)
    clean = next(r for r in runs if r["group"] == "clean")
    d = pd.read_csv(out / "runs" / f"{alt_on['name']}.csv"); d = d[d.channel == "altimeter"]
    c = pd.read_csv(out / "runs" / f"{clean['name']}.csv"); c = c[c.channel == "altimeter"]
    det = alt_on["detection_t"]
    # 1 - readings vs truth: the sensor keeps reporting, slowly wrong
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)
    ax[0].plot(d.t, d.truth, color="#111827", lw=1.2, label="true height above terrain")
    ax[0].scatter(d.t, d.truth + d.true_bias + np.random.default_rng(0).normal(0, 0.6, len(d)), s=2, color="#ef4444", alpha=.5, label="altimeter readings (drifting)")
    ax[0].set_ylabel("m"); ax[0].legend(loc="upper right"); ax[0].set_title("A sensor that keeps talking but is slowly wrong")
    ax[1].plot(d.t, d.true_bias, color="#ef4444", label="injected bias (hidden from the lander)")
    for a in ax:
        a.axvline(ONSET, color="#f59e0b", ls="--", lw=1); a.axvline(det, color="#16a34a", ls="--", lw=1) if det else None
    ax[1].set_ylabel("bias [m]"); ax[1].set_xlabel("mission time [s]"); ax[1].legend(loc="upper left")
    fig.tight_layout(); fig.savefig(out / "fig_1_readings_vs_truth.png"); plt.close(fig)
    # 2 - normalised innovations lean to one side
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for a, df, title, col in ((ax[0], c, "Honest altimeter (clean run)", "#2563eb"), (ax[1], d, "Lying altimeter (drift from t=20 s)", "#ef4444")):
        a.scatter(df.t, df.normalised_innovation, s=2, color=col, alpha=.45)
        a.plot(df.t, df.normalised_innovation.rolling(60, min_periods=10).mean(), color="#111827", lw=1.4, label="running mean")
        a.axhline(0, color="#9ca3af", lw=.8); a.set_title(title); a.set_xlabel("mission time [s]")
    ax[0].set_ylabel("normalised innovation  y/âˆšS"); ax[1].axvline(ONSET, color="#f59e0b", ls="--", lw=1); ax[0].legend()
    fig.suptitle("Honest noise scatters on both sides of zero - a drifting sensor keeps leaning one way")
    fig.tight_layout(); fig.savefig(out / "fig_2_innovation_lean.png"); plt.close(fig)
    # 3 - CUSUM vs threshold: the exact moment
    sus = alt_on["suspect_t"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(c.t, c.cusum, color="#2563eb", lw=1.2, label="CUSUM, clean run")
    ax.plot(d.t, d.cusum, color="#ef4444", lw=1.6, label="CUSUM, drifting altimeter")
    ax.axhline(14, color="#111827", ls=":", label="threshold h = 14")
    ax.axvline(ONSET, color="#f59e0b", ls="--", lw=1, label="drift begins (t = 20 s)")
    if sus:
        ax.axvline(sus, color="#a855f7", ls="--", lw=1, label=f"SUSPECT (+{sus - ONSET:.1f} s)")
    if det:
        ax.axvline(det, color="#16a34a", ls="--", lw=1.4, label=f"ISOLATED, confirmed by cross-check (+{det - ONSET:.1f} s)")
    ax.set_xlim(0, (det or 60) + 12); ax.set_ylim(0, 70)
    ax.set_xlabel("mission time [s]"); ax.set_ylabel("CUSUM statistic"); ax.legend(loc="upper left", fontsize=8); ax.set_title("The exact moment the system realised something was off")
    fig.tight_layout(); fig.savefig(out / "fig_3_cusum_detection.png"); plt.close(fig)
    # 4 - innovation distributions
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.hist(c.normalised_innovation, bins=60, range=(-5, 5), alpha=.6, color="#2563eb", density=True, label="clean")
    ax.hist(d[d.t > ONSET + 5].normalised_innovation, bins=60, range=(-5, 5), alpha=.6, color="#ef4444", density=True, label="drifting (after onset)")
    ax.axvline(0, color="#111827", lw=.8); ax.set_xlabel("normalised innovation"); ax.legend(); ax.set_title("Distribution shifts to one side")
    fig.tight_layout(); fig.savefig(out / "fig_4_innovation_histogram.png"); plt.close(fig)
    # 5 - consequence: monitor on vs off
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    labels = [f"{ch}\n{rt}" for ch, rt in DRIFTS]
    for k, (grp, col) in enumerate((("drift_off", "#9ca3af"), ("drift_on", "#16a34a"))):
        vals = [np.mean([r["success"] for r in runs if r["group"] == grp and r["drift_channel"] == ch and r["drift_rate"] == rt]) * 100 for ch, rt in DRIFTS]
        ax.bar(np.arange(len(DRIFTS)) + (k - 0.5) * 0.38, vals, 0.38, color=col, label="monitor OFF" if grp == "drift_off" else "monitor ON (detect + isolate)")
    ax.set_xticks(range(len(DRIFTS))); ax.set_xticklabels(labels); ax.set_ylabel("safe landings [%]"); ax.set_ylim(0, 105); ax.legend()
    ax.set_title("What the lie costs when nobody catches it"); fig.tight_layout(); fig.savefig(out / "fig_5_outcomes_on_vs_off.png"); plt.close(fig)


def main(seeds: int, workers: int) -> dict:
    out = settings.data_dir / "sensor_drift_dataset"
    (out / "runs").mkdir(parents=True, exist_ok=True)
    jobs = [("clean", s, None, str(out)) for s in range(1, seeds * 2 + 1)]
    jobs += [(g, s, d, str(out)) for g in ("drift_on", "drift_off") for d in DRIFTS for s in range(1, seeds + 1)]
    with Pool(workers) as p:
        runs = p.map(_run, jobs)
    clean = [r for r in runs if r["group"] == "clean"]
    summary = {"onset_s": ONSET, "seeds_per_case": seeds, "runs": len(runs),
               "false_alarm_rate": float(np.mean([r["false_alarm"] for r in clean])), "clean_runs": len(clean),
               "clean_success_rate": float(np.mean([r["success"] for r in clean])), "cases": []}
    for ch, rt in DRIFTS:
        on = [r for r in runs if r["group"] == "drift_on" and r["drift_channel"] == ch and r["drift_rate"] == rt]
        off = [r for r in runs if r["group"] == "drift_off" and r["drift_channel"] == ch and r["drift_rate"] == rt]
        delays = [r["detection_delay_s"] for r in on if r["detection_delay_s"] is not None]
        summary["cases"].append({"channel": ch, "rate": rt, "n": len(on),
                                 "detection_rate": len(delays) / len(on), "correct_blame_rate": float(np.mean([r["correct_blame"] for r in on])),
                                 "delay_mean_s": float(np.mean(delays)) if delays else None, "delay_max_s": float(np.max(delays)) if delays else None,
                                 "success_monitor_on": float(np.mean([r["success"] for r in on])),
                                 "success_monitor_off": float(np.mean([r["success"] for r in off])),
                                 "nav_error_on_m": float(np.mean([r["final_nav_error_m"] for r in on])),
                                 "nav_error_off_m": float(np.mean([r["final_nav_error_m"] for r in off]))})
    summary["runs_detail"] = runs
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    _plots(out, runs)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    s = main(a.seeds, a.workers)
    print(f"false alarms: {s['false_alarm_rate']:.0%} of {s['clean_runs']} clean runs")
    for c in s["cases"]:
        print(f"{c['channel']:12s} {c['rate']:>5}: detected {c['detection_rate']:.0%}, correct blame {c['correct_blame_rate']:.0%}, "
              f"delay {c['delay_mean_s']} s (max {c['delay_max_s']}) | safe landings ON {c['success_monitor_on']:.0%} vs OFF {c['success_monitor_off']:.0%}")
