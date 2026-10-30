import numpy as np
from scipy import stats
from typing import List, Dict, Any, Optional, Tuple
from shared.schemas.experiments import StatisticalSummary, ControllerComparisonResult

def compute_wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Computes Wilson Score Interval for binomial proportion:
    p_hat = successes / total
    """
    if total == 0:
        return 0.0, 0.0, 0.0

    p_hat = successes / total
    z = stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    z2 = z ** 2

    denominator = 1.0 + z2 / total
    center = (p_hat + z2 / (2.0 * total)) / denominator
    half_width = (z * np.sqrt((p_hat * (1.0 - p_hat) / total) + (z2 / (4.0 * (total ** 2))))) / denominator

    lower = max(0.0, float(center - half_width))
    upper = min(1.0, float(center + half_width))
    return float(p_hat), lower, upper

def compute_statistical_summary(trials: List[Dict[str, Any]]) -> StatisticalSummary:
    """Computes summary statistics, Wilson intervals, and standard deviations."""
    n = len(trials)
    if n == 0:
        return StatisticalSummary(
            sample_size=0,
            completion_rate=0.0,
            completion_rate_ci_lower_95=0.0,
            completion_rate_ci_upper_95=0.0,
            time_mean=0.0,
            time_std=0.0,
            energy_mean=0.0,
            energy_std=0.0,
            route_length_mean=0.0,
            safety_violations_mean=0.0,
            position_error_mean=0.0
        )

    successes = sum(1 for t in trials if t.get("success", False))
    comp_rate, ci_low, ci_high = compute_wilson_score_interval(successes, n)

    successful_trials = [t for t in trials if t.get("success", False)]
    times = [t.get("time_to_completion", 0.0) for t in successful_trials] or [0.0]
    energies = [t.get("energy_consumed", 0.0) for t in successful_trials] or [0.0]
    lengths = [t.get("route_length_m", 0.0) for t in trials]
    violations = [t.get("safety_violations", 0) for t in trials]
    pos_errors = [t.get("mean_position_error_m", 0.0) for t in trials]

    return StatisticalSummary(
        sample_size=n,
        completion_rate=comp_rate,
        completion_rate_ci_lower_95=ci_low,
        completion_rate_ci_upper_95=ci_high,
        time_mean=float(np.mean(times)),
        time_std=float(np.std(times, ddof=1) if len(times) > 1 else 0.0),
        energy_mean=float(np.mean(energies)),
        energy_std=float(np.std(energies, ddof=1) if len(energies) > 1 else 0.0),
        route_length_mean=float(np.mean(lengths)),
        safety_violations_mean=float(np.mean(violations)),
        position_error_mean=float(np.mean(pos_errors))
    )

def compare_controllers(
    condition_name: str,
    terrain_variant: int,
    fault_type: str,
    astra_trials: List[Dict[str, Any]],
    fsm_trials: List[Dict[str, Any]],
    is_held_out: bool
) -> ControllerComparisonResult:
    """Performs rigorous paired two-sample hypothesis testing between ASTRA and FSM baseline."""
    astra_stats = compute_statistical_summary(astra_trials)
    fsm_stats = compute_statistical_summary(fsm_trials)

    # 1. Completion rate significance test (Fisher exact / Chi-squared)
    n_a = len(astra_trials)
    n_f = len(fsm_trials)
    succ_a = sum(1 for t in astra_trials if t.get("success", False))
    succ_f = sum(1 for t in fsm_trials if t.get("success", False))

    if n_a > 0 and n_f > 0:
        table = [[succ_a, n_a - succ_a], [succ_f, n_f - succ_f]]
        _, p_val_comp = stats.fisher_exact(table)
    else:
        p_val_comp = None

    # 2. Time comparison (Two-sample Welch's t-test on successful runs)
    succ_times_a = [t["time_to_completion"] for t in astra_trials if t.get("success", False)]
    succ_times_f = [t["time_to_completion"] for t in fsm_trials if t.get("success", False)]
    if len(succ_times_a) >= 2 and len(succ_times_f) >= 2:
        _, p_val_time = stats.ttest_ind(succ_times_a, succ_times_f, equal_var=False)
    else:
        p_val_time = None

    # 3. Energy comparison
    succ_energies_a = [t["energy_consumed"] for t in astra_trials if t.get("success", False)]
    succ_energies_f = [t["energy_consumed"] for t in fsm_trials if t.get("success", False)]
    if len(succ_energies_a) >= 2 and len(succ_energies_f) >= 2:
        _, p_val_energy = stats.ttest_ind(succ_energies_a, succ_energies_f, equal_var=False)
    else:
        p_val_energy = None

    # Percentage improvements
    energy_savings = 0.0
    if fsm_stats.energy_mean > 0.0:
        energy_savings = float(100.0 * (fsm_stats.energy_mean - astra_stats.energy_mean) / fsm_stats.energy_mean)

    time_reduction = 0.0
    if fsm_stats.time_mean > 0.0:
        time_reduction = float(100.0 * (fsm_stats.time_mean - astra_stats.time_mean) / fsm_stats.time_mean)

    return ControllerComparisonResult(
        condition_name=condition_name,
        terrain=terrain_variant,
        fault_type=fault_type,
        astra_stats=astra_stats,
        fsm_stats=fsm_stats,
        p_value_completion=float(p_val_comp) if p_val_comp is not None else None,
        p_value_time=float(p_val_time) if p_val_time is not None else None,
        p_value_energy=float(p_val_energy) if p_val_energy is not None else None,
        astra_energy_savings_pct=energy_savings,
        astra_time_reduction_pct=time_reduction,
        is_held_out=is_held_out
    )
