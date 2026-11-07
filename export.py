"""CSV export helpers."""

import csv

from experiments import METRICS


def _fmt(value):
    return "" if value is None else round(value, 3)


def export_patients(patients, path):
    """One row per patient from a single simulation run."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "patient_id", "type", "priority", "arrival_min",
            "service_start_min", "completion_min", "waiting_min",
            "service_min", "time_in_system_min", "nurse",
            "reneged", "leave_min", "preemptions",
        ])
        for p in patients:
            writer.writerow([
                p.patient_id, p.patient_type, p.priority,
                _fmt(p.arrival_time), _fmt(p.service_start),
                _fmt(p.completion_time), _fmt(p.waiting_time),
                _fmt(p.service_time), _fmt(p.time_in_system),
                p.assigned_nurse or "", p.reneged,
                _fmt(p.leave_time), p.preemptions,
            ])


def export_comparison(results, path):
    """One row per scenario/metric with mean, 95% CI and sample size."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "scenario", "metric", "mean", "ci95_half_width",
            "ci_low", "ci_high", "n",
        ])
        for scenario, result in results.items():
            for key, (label, _extract) in METRICS.items():
                mean, half, n = result["stats"][key]
                low = mean - half if mean is not None and half is not None else None
                high = mean + half if mean is not None and half is not None else None
                writer.writerow([
                    scenario, label, _fmt(mean), _fmt(half),
                    _fmt(low), _fmt(high), n,
                ])

