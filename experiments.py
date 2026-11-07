"""Run many simulated days and compare policies with confidence intervals."""

import math
import statistics
from dataclasses import replace

from simulation import SimulationController

# Two-sided 95% critical values of Student's t distribution.
_T_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    40: 2.021, 60: 2.000, 120: 1.980,
}

# key: (label, function extracting the value from a run summary)
METRICS = {
    "emergency_wait": (
        "Emergency avg wait (min)",
        lambda s: s["by_type"]["Emergency"]["avg_wait"]),
    "general_wait": (
        "General avg wait (min)",
        lambda s: s["by_type"]["General"]["avg_wait"]),
    "overall_wait": (
        "Overall avg wait (min)",
        lambda s: s["average_wait"]),
    "system_time": (
        "Avg time in system (min)",
        lambda s: s["average_system_time"]),
    "emergency_within_target": (
        "Emergencies seen within target (%)",
        lambda s: s["emergency_within_target_pct"]),
    "reneged": (
        "Patients who left untreated",
        lambda s: s["reneged"]),
    "max_queue": (
        "Max queue length",
        lambda s: s["max_queue"]),
    "overtime": (
        "Overtime (min)",
        lambda s: s["overtime"]),
    "utilization": (
        "Avg nurse utilization, shift (%)",
        lambda s: s["average_shift_utilization"]),
}

POLICY_LABELS = {
    "fifo": "FIFO (no priority)",
    "priority": "Priority",
    "preemptive": "Preemptive priority",
}


def t_critical(df):
    if df <= 0:
        return math.nan
    if df in _T_95:
        return _T_95[df]
    for limit in (40, 60, 120):
        if df < limit:
            return _T_95[limit]
    return 1.960


def mean_ci(values):
    """Return (mean, 95% CI half-width, n). Missing values are skipped."""
    data = [v for v in values if v is not None]
    n = len(data)
    if n == 0:
        return None, None, 0
    mean = statistics.fmean(data)
    if n == 1:
        return mean, None, 1
    half = t_critical(n - 1) * statistics.stdev(data) / math.sqrt(n)
    return mean, half, n


def run_replications(config, n=30, base_seed=None):
    """Simulate n independent days. Seeds are base_seed, base_seed+1, ..."""
    if base_seed is None:
        base_seed = config.random_seed
    summaries = []
    for i in range(n):
        controller = SimulationController(
            replace(config, random_seed=base_seed + i)
        )
        controller.run()
        summaries.append(controller.summary())

    stats = {
        key: mean_ci([extract(s) for s in summaries])
        for key, (_label, extract) in METRICS.items()
    }
    return {"config": config, "runs": summaries, "stats": stats}


def compare_scenarios(scenarios, n=30, base_seed=42):
    """Run each named config with the SAME seeds (common random numbers).

    Because arrivals and service times are drawn in the same order
    regardless of policy, every scenario sees the identical stream of
    patients, so differences come from the policy alone.
    """
    return {
        name: run_replications(cfg, n=n, base_seed=base_seed)
        for name, cfg in scenarios.items()
    }


def format_ci(mean, half, digits=2):
    if mean is None:
        return "n/a"
    if half is None:
        return f"{mean:.{digits}f}"
    return f"{mean:.{digits}f} ± {half:.{digits}f}"

