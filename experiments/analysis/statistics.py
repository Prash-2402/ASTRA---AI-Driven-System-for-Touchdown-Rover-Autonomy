"""Statistical evaluation (docs/STATISTICAL_EVALUATION.md).

* Completion rate: proportion with 95 % Wilson score interval.
* Continuous metrics: mean, sample SD, n (missing values excluded and counted).
* Paired ASTRA-vs-FSM comparisons on matched seeds:
    - completion: exact McNemar test on discordant pairs (binomial, two-sided)
    - continuous: Wilcoxon signed-rank on pairs where both values exist
  p-values are reported, never converted into claims when n is small.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def describe(values) -> dict:
    v = np.array([x for x in values if x is not None and not (isinstance(x, float) and math.isnan(x))], float)
    if v.size == 0:
        return {"mean": None, "sd": None, "n": 0}
    return {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if v.size > 1 else 0.0, "n": int(v.size)}


def mcnemar_exact(a_success: list[bool], b_success: list[bool]) -> dict:
    b = sum(1 for x, y in zip(a_success, b_success) if x and not y)
    c = sum(1 for x, y in zip(a_success, b_success) if y and not x)
    n = b + c
    p = 1.0 if n == 0 else float(min(1.0, 2 * stats.binom.cdf(min(b, c), n, 0.5)))
    return {"astra_only": b, "fsm_only": c, "discordant": n, "p_value": p}


def wilcoxon_paired(a: list, b: list) -> dict:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 2:
        return {"n": len(pairs), "mean_diff": None, "p_value": None}
    d = np.array([x - y for x, y in pairs], float)
    if np.allclose(d, 0):
        return {"n": len(pairs), "mean_diff": 0.0, "p_value": 1.0}
    try:
        p = float(stats.wilcoxon(d, zero_method="wilcox").pvalue)
    except ValueError:
        p = None
    return {"n": len(pairs), "mean_diff": float(d.mean()), "p_value": p}


METRICS = ["time_to_completion_s", "energy_used_wh", "remaining_battery_soc", "route_length_m", "collisions",
           "safety_violations", "replanning_time_ms_mean", "position_error_mean_m", "heading_error_mean_rad",
           "position_sigma_mean_m", "recovery_success_rate", "classification_accuracy", "detection_delay_s"]


def summarize(trials: list[dict]) -> dict:
    """trials: dicts with terrain, condition, controller, seed, status, metrics."""
    done = [t for t in trials if t["status"] == "completed" and t.get("metrics")]
    groups: dict = {}
    for t in done:
        groups.setdefault((t["terrain"], t["condition"], t["controller"]), []).append(t)
    table = []
    for (terr, cond, ctrl), ts in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2])):
        n = len(ts)
        k = sum(1 for t in ts if t["metrics"].get("success"))
        lo, hi = wilson_interval(k, n)
        row = {"terrain": terr, "condition": cond, "controller": ctrl, "n": n, "successes": k,
               "completion_rate": k / n if n else None, "ci_low": lo, "ci_high": hi, "metrics": {}}
        for mname in METRICS:
            if mname == "detection_delay_s":
                vals = [min(t["metrics"].get("fault_detection_delay_s", {}).values(), default=None) for t in ts]
            else:
                vals = [t["metrics"].get(mname) for t in ts]
            row["metrics"][mname] = describe(vals)
        tm, en, sv = row["metrics"]["time_to_completion_s"], row["metrics"]["energy_used_wh"], row["metrics"]["safety_violations"]
        row["time_str"] = "-" if tm["n"] == 0 else f"{tm['mean']:.0f}±{tm['sd']:.0f} (n={tm['n']})"
        row["energy_str"] = "-" if en["n"] == 0 else f"{en['mean']:.2f}±{en['sd']:.2f}"
        row["violations_str"] = "-" if sv["n"] == 0 else f"{sv['mean']:.2f}"
        table.append(row)
    paired = []
    keys = {(t["terrain"], t["condition"]) for t in done}
    for terr, cond in sorted(keys, key=str):
        a = {t["seed"]: t["metrics"] for t in done if (t["terrain"], t["condition"], t["controller"]) == (terr, cond, "astra")}
        b = {t["seed"]: t["metrics"] for t in done if (t["terrain"], t["condition"], t["controller"]) == (terr, cond, "fsm")}
        seeds = sorted(set(a) & set(b))
        if not seeds:
            continue
        mc = mcnemar_exact([bool(a[s].get("success")) for s in seeds], [bool(b[s].get("success")) for s in seeds])
        paired.append({"terrain": terr, "condition": cond, "metric": "completion", "n": len(seeds),
                       "mean_diff": float(np.mean([bool(a[s].get("success")) - bool(b[s].get("success")) for s in seeds])),
                       "test": "McNemar exact", "p_value": mc["p_value"], "details": mc})
        for mname in ("time_to_completion_s", "energy_used_wh", "safety_violations"):
            w = wilcoxon_paired([a[s].get(mname) for s in seeds], [b[s].get(mname) for s in seeds])
            paired.append({"terrain": terr, "condition": cond, "metric": mname, "n": w["n"], "mean_diff": w["mean_diff"],
                           "test": "Wilcoxon signed-rank", "p_value": w["p_value"]})
    return {"table": table, "paired": paired, "trials_completed": len(done), "trials_total": len(trials)}


def summarize_touchdown(trials: list[dict]) -> dict:
    done = [t for t in trials if t["status"] == "completed" and t.get("metrics")]
    groups: dict = {}
    for t in done:
        groups.setdefault((t["condition"], t["controller"]), []).append(t["metrics"])
    table = []
    for (cond, ctrl), ms in sorted(groups.items()):
        n = len(ms); k = sum(1 for m in ms if m.get("success"))
        lo, hi = wilson_interval(k, n)
        td = [m.get("touchdown") or {} for m in ms]
        table.append({"terrain": "-", "condition": cond, "controller": ctrl, "n": n, "successes": k, "completion_rate": k / n,
                      "ci_low": lo, "ci_high": hi, "metrics": {
                          "landing_error_m": describe([m.get("landing_error_m") for m in ms]),
                          "fuel_used_kg": describe([m.get("fuel_used_kg") for m in ms]),
                          "touchdown_vertical_speed": describe([abs(x["vertical_speed"]) if x else None for x in td]),
                          "mission_time_s": describe([m.get("mission_time_s") for m in ms]),
                          "diversions": describe([m.get("diversions") for m in ms]),
                          "max_position_estimation_error_m": describe([m.get("max_position_estimation_error_m") for m in ms])}})
    for r in table:
        r["time_str"] = f"{r['metrics']['mission_time_s']['mean']:.0f}" if r["metrics"]["mission_time_s"]["n"] else "-"
        r["energy_str"] = f"{r['metrics']['fuel_used_kg']['mean']:.0f} kg" if r["metrics"]["fuel_used_kg"]["n"] else "-"
        r["violations_str"] = "-"
    return {"table": table, "paired": [], "trials_completed": len(done), "trials_total": len(trials)}
