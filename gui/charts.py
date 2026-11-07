"""Clinic analytics charts (matplotlib). Every function takes a Figure.

Live (one simulated day):
    draw_waiting_room   - who is waiting (Emergency vs General) through the day
    draw_hourly_flow    - patients arriving / treated / leaving per clinic hour
    draw_wait_times     - wait distribution per patient type vs. emergency target
    draw_nurse_schedule - Gantt chart of what each nurse was doing

Compare (many simulated days per policy):
    draw_compare_waits     - average wait by patient type, with 95% CI
    draw_compare_emergency - % of emergencies seen within the target
    draw_compare_load      - patients left untreated and overtime
"""

import math

from matplotlib.ticker import FuncFormatter, MaxNLocator, MultipleLocator

from simulation import clock_text

EMERGENCY = "#dc2626"
GENERAL = "#2563eb"
NURSE = "#059669"
RENEGE = "#d97706"
MUTED = "#64748b"
PEAK = "#fef08a"


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------
def _hour_label(minutes, start_hour):
    """'9 AM' for whole hours, otherwise '9:30 AM'."""
    return clock_text(minutes, start_hour).replace(":00 ", " ")


def _clock_axis(ax, cfg, end):
    """Format an x-axis in simulation minutes as clinic clock time."""
    ax.set_xlim(0, max(cfg.duration, end) + 5)
    ax.xaxis.set_major_locator(MultipleLocator(60))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda x, _pos: _hour_label(x, cfg.shift_start_hour)))
    ax.tick_params(labelsize=8)


def _clinic_markers(ax, cfg, end):
    """Shade peak hours and overtime; mark when the clinic closes."""
    if cfg.use_peak_hours and cfg.peak_profile:
        labelled = False
        for hour in range(math.ceil(cfg.duration / 60)):
            if cfg.peak_profile[hour % len(cfg.peak_profile)] > 1.0:
                ax.axvspan(hour * 60, min((hour + 1) * 60, cfg.duration),
                           color=PEAK, alpha=0.25, lw=0,
                           label=None if labelled else "Peak hours")
                labelled = True
    ax.axvline(cfg.duration, color=MUTED, linestyle="--", linewidth=1,
               label="Clinic closes")
    if end > cfg.duration:
        ax.axvspan(cfg.duration, end, color=MUTED, alpha=0.12, lw=0,
                   hatch="//", label="Overtime")


def _placeholder(fig, text="Press ▶ Play or ⚡ Run Instantly to start"):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=10, color=MUTED)


def _finish(fig, ax, title):
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.set_title(title, fontsize=9.5, fontweight="bold", loc="left", color="#1a365d", pad=6)
    ax.grid(True, linestyle="--", alpha=0.35, color="#cbd5e1")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    fig.tight_layout()


# ----------------------------------------------------------------------
# Live charts (single day)
# ----------------------------------------------------------------------
def draw_waiting_room(fig, controller):
    if controller is None:
        return _placeholder(fig)
    fig.clear()
    ax = fig.add_subplot(111)
    cfg, now = controller.config, controller.env.now

    t = [p[0] for p in controller.timeline]
    total = [p[1] for p in controller.timeline]
    busy = [p[2] for p in controller.timeline]
    emerg = [p[3] for p in controller.timeline]
    # Extend the last state to "now" so the chart reaches the clock.
    t.append(now); total.append(total[-1]); busy.append(busy[-1]); emerg.append(emerg[-1])

    _clinic_markers(ax, cfg, now)
    ax.fill_between(t, 0, emerg, step="post", color=EMERGENCY, alpha=0.75,
                    label="Emergency waiting")
    ax.fill_between(t, emerg, total, step="post", color=GENERAL, alpha=0.45,
                    label="General waiting")
    ax.step(t, busy, where="post", color=NURSE, linewidth=1.6, label="Nurses busy")
    ax.axhline(cfg.nurses, color=NURSE, linestyle=":", linewidth=1,
               label=f"Nurses on duty ({cfg.nurses})")

    _clock_axis(ax, cfg, now)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Patients", fontsize=8)
    ax.legend(loc="upper left", fontsize=7, ncol=3)
    _finish(fig, ax, f"Waiting room through the day  (now {clock_text(now, cfg.shift_start_hour)})")


def draw_hourly_flow(fig, controller):
    if controller is None:
        return _placeholder(fig)
    fig.clear()
    ax = fig.add_subplot(111)
    cfg, now = controller.config, controller.env.now
    hours = max(1, math.ceil(max(cfg.duration, now) / 60))

    emerg = [0] * hours
    general = [0] * hours
    treated = [0] * hours
    left = [0] * hours
    for p in controller.patients:
        h = min(int(p.arrival_time // 60), hours - 1)
        (emerg if p.patient_type == "Emergency" else general)[h] += 1
        if p.completion_time is not None:
            treated[min(int(p.completion_time // 60), hours - 1)] += 1
        if p.reneged:
            left[min(int(p.leave_time // 60), hours - 1)] += 1

    xs = list(range(hours))
    ax.bar(xs, emerg, color=EMERGENCY, alpha=0.85, label="Emergency arrivals")
    ax.bar(xs, general, bottom=emerg, color=GENERAL, alpha=0.6, label="General arrivals")
    ax.plot(xs, treated, color=NURSE, marker="o", linewidth=1.6, label="Treated")
    if cfg.reneging:
        ax.plot(xs, left, color=RENEGE, marker="x", linestyle="--", label="Left untreated")

    closing = cfg.duration / 60 - 0.5
    ax.axvline(closing, color=MUTED, linestyle="--", linewidth=1, label="Clinic closes")
    ax.set_xticks(xs)
    ax.set_xticklabels([_hour_label(h * 60, cfg.shift_start_hour) for h in xs], fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.tick_params(labelsize=8)
    ax.set_ylabel("Patients per hour", fontsize=8)
    ax.legend(loc="upper right", fontsize=7)
    _finish(fig, ax, "Patient flow per clinic hour")


def draw_wait_times(fig, controller):
    if controller is None:
        return _placeholder(fig)
    fig.clear()
    ax = fig.add_subplot(111)
    cfg = controller.config

    groups, labels, colors = [], [], []
    for kind, color in (("Emergency", EMERGENCY), ("General", GENERAL)):
        waits = [p.waiting_time for p in controller.patients
                 if p.patient_type == kind and p.service_start is not None]
        if waits:
            groups.append(waits)
            labels.append(f"{kind}\n(n={len(waits)}, avg {sum(waits) / len(waits):.1f} min)")
            colors.append(color)
    if not groups:
        return _placeholder(fig, "No patients treated yet")

    box = ax.boxplot(groups, vert=False, patch_artist=True, widths=0.5,
                     showmeans=True, meanprops={"marker": "D", "markerfacecolor": "white",
                                                "markeredgecolor": "black", "markersize": 5})
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.55)
    ax.set_yticks(range(1, len(labels) + 1))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(cfg.emergency_target, color=EMERGENCY, linestyle="--", linewidth=1.2,
               label=f"Emergency target ({cfg.emergency_target:g} min)")
    ax.set_xlabel("Waiting time before treatment (minutes)", fontsize=8)
    ax.set_xlim(left=0)
    ax.tick_params(labelsize=8)
    ax.legend(loc="lower right", fontsize=7)
    _finish(fig, ax, "How long patients waited  (box = middle 50%, ◇ = average)")


def draw_nurse_schedule(fig, controller):
    if controller is None:
        return _placeholder(fig)
    fig.clear()
    ax = fig.add_subplot(111)
    cfg, now = controller.config, controller.env.now

    blocks = list(controller.treatments)
    for n in controller.nurses:          # treatments still in progress
        if n.busy:
            blocks.append({"nurse": n.name, "type": n.current_patient.patient_type,
                           "start": n.started_at, "end": now, "interrupted": False})

    names = [n.name for n in controller.nurses]
    row = {name: i for i, name in enumerate(names)}
    for kind, color in (("Emergency", EMERGENCY), ("General", GENERAL)):
        for interrupted in (False, True):
            for name in names:
                spans = [(b["start"], b["end"] - b["start"]) for b in blocks
                         if b["nurse"] == name and b["type"] == kind
                         and b["interrupted"] == interrupted]
                if spans:
                    ax.broken_barh(spans, (row[name] - 0.35, 0.7), facecolors=color,
                                   alpha=0.8, edgecolor="white", linewidth=0.5,
                                   hatch="xx" if interrupted else None)

    _clinic_markers(ax, cfg, now)
    # Legend proxies
    ax.bar(0, 0, color=EMERGENCY, alpha=0.8, label="Treating Emergency")
    ax.bar(0, 0, color=GENERAL, alpha=0.8, label="Treating General")
    if any(b["interrupted"] for b in blocks):
        ax.bar(0, 0, color=GENERAL, alpha=0.8, hatch="xx", label="Interrupted")

    util = {n["name"]: n["utilization"] for n in controller.snapshot()["nurses"]}
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{name}\n{util[name]:.0f}% busy" for name in names], fontsize=8)
    ax.set_ylim(len(names) - 0.5, -0.5)
    _clock_axis(ax, cfg, now)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7, ncol=6, frameon=False)
    ax.set_title("Nurse schedule  (white gaps = idle)", fontsize=10, loc="left", color="#1a365d")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()


LIVE_CHARTS = (
    ("Waiting Room", draw_waiting_room),
    ("Hourly Flow", draw_hourly_flow),
    ("Wait Times", draw_wait_times),
    ("Nurse Schedule", draw_nurse_schedule),
)


# ----------------------------------------------------------------------
# Comparison charts (many days per policy)
# ----------------------------------------------------------------------
def _stat(results, name, key):
    mean, half, _n = results[name]["stats"][key]
    return (mean if mean is not None else 0.0), (half or 0.0)


def _short(name):
    return name.replace(" (", "\n(")


def _label_bars(ax, bars, values, errs, fmt):
    for bar, value, err in zip(bars, values, errs):
        top = value + (err or 0.0)
        ax.annotate(fmt.format(value), (bar.get_x() + bar.get_width() / 2, top),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)


def draw_compare_waits(fig, results):
    if not results:
        return _placeholder(fig, "Press ▶ Run Comparison")
    fig.clear()
    ax = fig.add_subplot(111)
    names = list(results)
    series = (("emergency_wait", "Emergency", EMERGENCY),
              ("general_wait", "General", GENERAL),
              ("overall_wait", "All patients", MUTED))
    width = 0.8 / len(series)
    peak = 1.0
    for i, (key, label, color) in enumerate(series):
        vals = [_stat(results, n, key) for n in names]
        means = [v[0] for v in vals]
        errs = [v[1] for v in vals]
        peak = max(peak, *(m + e for m, e in zip(means, errs)))
        xs = [x + (i - (len(series) - 1) / 2) * width for x in range(len(names))]
        bars = ax.bar(xs, means, width, yerr=errs,
                      capsize=3, color=color, alpha=0.85, label=label)
        _label_bars(ax, bars, means, errs, "{:.1f}")
    ax.set_ylim(0, peak * 1.18)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([_short(n) for n in names], fontsize=8)
    ax.set_ylabel("Average wait (minutes)", fontsize=8)
    ax.tick_params(labelsize=8)
    ax.legend(fontsize=7)
    _finish(fig, ax, "Average waiting time by patient type  (error bars = 95% CI)")


def draw_compare_emergency(fig, results, target):
    if not results:
        return _placeholder(fig, "Press ▶ Run Comparison")
    fig.clear()
    ax = fig.add_subplot(111)
    names = list(results)
    vals = [_stat(results, n, "emergency_within_target") for n in names]
    means = [v[0] for v in vals]
    errs = [v[1] for v in vals]
    bars = ax.bar(range(len(names)), means, 0.55,
                  yerr=errs, capsize=4, color=EMERGENCY, alpha=0.85)
    _label_bars(ax, bars, means, errs, "{:.0f}%")
    ax.set_ylim(0, 116)
    ax.axhline(100, color=MUTED, linestyle=":", linewidth=1)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([_short(n) for n in names], fontsize=8)
    ax.set_ylabel("Emergencies seen in time (%)", fontsize=8)
    ax.tick_params(labelsize=8)
    _finish(fig, ax, f"Emergencies treated within {target:g} minutes")


def draw_compare_load(fig, results):
    if not results:
        return _placeholder(fig, "Press ▶ Run Comparison")
    fig.clear()
    names = list(results)
    panels = (("reneged", "Patients left untreated", "Patients", RENEGE, "{:.1f}"),
              ("overtime", "Overtime after closing", "Minutes", MUTED, "{:.0f}m"),
              ("utilization", "Nurse shift utilization", "Busy %", NURSE, "{:.0f}%"))
    for i, (key, title, ylabel, color, fmt) in enumerate(panels):
        ax = fig.add_subplot(len(panels), 1, i + 1)
        vals = [_stat(results, n, key) for n in names]
        means = [v[0] for v in vals]
        errs = [v[1] for v in vals]
        peak = max(1.0, *(m + e for m, e in zip(means, errs)))
        bars = ax.bar(range(len(names)), means, 0.45,
                      yerr=errs, capsize=3, color=color, alpha=0.85)
        _label_bars(ax, bars, means, errs, fmt)
        ax.set_ylim(0, peak * 1.28)
        ax.set_xticks(range(len(names)))
        if i == len(panels) - 1:
            ax.set_xticklabels([_short(n) for n in names], fontsize=8)
        else:
            ax.set_xticklabels([])
        ax.set_ylabel(ylabel, fontsize=7.5)
        ax.tick_params(labelsize=7.5)
        ax.set_title(title, fontsize=8.5, loc="left", color="#1a365d", pad=2)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

