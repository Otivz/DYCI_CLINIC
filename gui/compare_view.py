"""Scenario comparison: many simulated days per policy or clinic, with 95% CIs."""

import tkinter as tk
from dataclasses import replace
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import get_clinic_config
from experiments import METRICS, POLICY_LABELS, compare_scenarios, format_ci
from export import export_comparison
from gui.charts import draw_compare_emergency, draw_compare_load, draw_compare_waits
from gui.params import POLICY_CHOICES


class CompareView(ttk.Frame):
    def __init__(self, parent, params):
        super().__init__(parent, padding=8)
        self.params = params
        self.results = None

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 8))

        # Comparison Mode selector
        ttk.Label(bar, text="Compare:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="Policies (within clinic)")
        self.mode_combo = ttk.Combobox(
            bar, textvariable=self.mode_var, state="readonly", width=22,
            values=["Policies (within clinic)", "Clinics (Elida vs Marciano)"]
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(4, 10))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_changed)

        # Policy checkboxes container
        self.policy_frame = ttk.Frame(bar)
        self.policy_frame.pack(side=tk.LEFT)
        ttk.Label(self.policy_frame, text="Policies:").pack(side=tk.LEFT)
        self.policy_vars = {}
        for policy, default in (("fifo", True), ("priority", True), ("preemptive", False)):
            var = tk.BooleanVar(value=default)
            ttk.Checkbutton(self.policy_frame, text=POLICY_LABELS[policy], variable=var).pack(side=tk.LEFT, padx=3)
            self.policy_vars[policy] = var

        # Clinic comparison policy container (shown when comparing clinics)
        self.clinic_mode_frame = ttk.Frame(bar)
        ttk.Label(self.clinic_mode_frame, text="Under Policy:").pack(side=tk.LEFT)
        self.clinic_policy_var = tk.StringVar(value="Priority (non-preemptive)")
        self.clinic_policy_combo = ttk.Combobox(
            self.clinic_mode_frame, textvariable=self.clinic_policy_var, state="readonly", width=22,
            values=list(POLICY_CHOICES.keys())
        )
        self.clinic_policy_combo.pack(side=tk.LEFT, padx=3)

        self.days_label = ttk.Label(bar, text="Days (replications):")
        self.days_label.pack(side=tk.LEFT, padx=(12, 4))
        self.reps_var = tk.StringVar(value="30")
        self.reps_spin = ttk.Spinbox(bar, from_=2, to=500, textvariable=self.reps_var, width=5)
        self.reps_spin.pack(side=tk.LEFT)

        ttk.Button(bar, text="▶ Run Comparison", command=self.run).pack(side=tk.LEFT, padx=(12, 4))
        ttk.Button(bar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT)

        self.status_label = ttk.Label(
            bar, foreground="#4a5568",
            text="Compares policies for the current clinic parameters above.")
        self.status_label.pack(side=tk.LEFT, padx=12)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        table_frame = ttk.LabelFrame(paned, text=" Results (mean ± 95% CI) ", padding=6)
        paned.add(table_frame, weight=3)
        self.tree = ttk.Treeview(table_frame, show="headings", height=10)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.insight_label = ttk.Label(table_frame, wraplength=560, foreground="#1a365d",
                                       font=("Segoe UI", 10))
        self.insight_label.pack(fill=tk.X, pady=(8, 0))

        chart_frame = ttk.LabelFrame(paned, text=" Clinic Analytics ", padding=4)
        paned.add(chart_frame, weight=2)
        self.chart_tabs = ttk.Notebook(chart_frame)
        self.chart_tabs.pack(fill=tk.BOTH, expand=True)
        self.charts = []    # (figure, canvas, draw function)
        for title, draw in (
            ("Waiting Time", lambda fig: draw_compare_waits(fig, self.results)),
            ("Emergency Response", lambda fig: draw_compare_emergency(
                fig, self.results, self._target)),
            ("Clinic Workload", lambda fig: draw_compare_load(fig, self.results)),
        ):
            frame = ttk.Frame(self.chart_tabs)
            figure = Figure(figsize=(5, 3.5), dpi=90)
            canvas = FigureCanvasTkAgg(figure, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.chart_tabs.add(frame, text=f" {title} ")
            self.charts.append((figure, canvas, draw))
        self._target = 5.0
        self._show_chart()

    def _on_mode_changed(self, event=None):
        if self.mode_var.get() == "Clinics (Elida vs Marciano)":
            self.policy_frame.pack_forget()
            self.clinic_mode_frame.pack(side=tk.LEFT, padx=(0, 8), before=self.days_label)
            self.status_label.config(
                text="Compares Clinic Elida vs. Clinic Marciano side-by-side.")
        else:
            self.clinic_mode_frame.pack_forget()
            self.policy_frame.pack(side=tk.LEFT, padx=(0, 8), before=self.days_label)
            self.status_label.config(
                text="Compares policies for the current clinic parameters above.")

    def run(self):
        try:
            reps = int(self.reps_var.get())
            if reps < 2:
                raise ValueError
        except ValueError:
            messagebox.showerror("Compare", "Days must be a whole number of at least 2.")
            return

        if self.mode_var.get() == "Clinics (Elida vs Marciano)":
            chosen_policy_str = self.clinic_policy_var.get()
            chosen_policy = POLICY_CHOICES.get(chosen_policy_str, "priority")
            base_config = self.params.get_config(show_errors=False)
            seed = base_config.random_seed if base_config else 42

            c_elida = get_clinic_config("Clinic Elida", policy=chosen_policy, random_seed=seed)
            c_marciano = get_clinic_config("Clinic Marciano", policy=chosen_policy, random_seed=seed)
            scenarios = {
                "Clinic Elida": c_elida,
                "Clinic Marciano": c_marciano,
            }
            self._target = c_elida.emergency_target
            self.status_label.config(
                text=f"Running {reps} days: Clinic Elida vs. Clinic Marciano ({chosen_policy_str})...")
        else:
            config = self.params.get_config()
            if config is None:
                return
            policies = [p for p, var in self.policy_vars.items() if var.get()]
            if not policies:
                messagebox.showwarning("Compare", "Select at least one policy.")
                return
            scenarios = {POLICY_LABELS[p]: replace(config, policy=p) for p in policies}
            self._target = config.emergency_target
            self.status_label.config(text=f"Running {reps} days x {len(scenarios)} policies...")

        self.config(cursor="watch")
        self.update_idletasks()
        try:
            first_cfg = next(iter(scenarios.values()))
            seed = first_cfg.random_seed
            self.results = compare_scenarios(scenarios, n=reps, base_seed=seed)
        finally:
            self.config(cursor="")

        if self.mode_var.get() == "Clinics (Elida vs Marciano)":
            self.status_label.config(
                text=f"Done: {reps} days simulated for Clinic Elida vs. Clinic Marciano ({self.clinic_policy_var.get()}).")
        else:
            self.status_label.config(
                text=f"Done: {reps} days per policy, seeds {seed}-{seed + reps - 1}.")

        self._show_table()
        self._show_chart()
        self._show_insight()

    def _show_table(self):
        names = list(self.results)
        columns = ["metric"] + names
        self.tree.configure(columns=columns)
        self.tree.heading("metric", text="Metric")
        self.tree.column("metric", width=220, anchor=tk.W)
        for name in names:
            self.tree.heading(name, text=name)
            self.tree.column(name, width=150, anchor=tk.CENTER)
        self.tree.delete(*self.tree.get_children())
        for key, (label, _extract) in METRICS.items():
            row = [label]
            for name in names:
                mean, half, _n = self.results[name]["stats"][key]
                row.append(format_ci(mean, half))
            self.tree.insert("", tk.END, values=row)

    def _show_chart(self):
        # Draw every tab so switching tabs is instant (comparison is static).
        for figure, canvas, draw in self.charts:
            draw(figure)
            canvas.draw_idle()

    def _show_insight(self):
        if not self.results:
            return

        if "Clinic Elida" in self.results and "Clinic Marciano" in self.results:
            elida = self.results["Clinic Elida"]
            marciano = self.results["Clinic Marciano"]
            ew, _, _ = elida["stats"]["overall_wait"]
            mw, _, _ = marciano["stats"]["overall_wait"]
            ee, _, _ = elida["stats"]["emergency_wait"]
            me, _, _ = marciano["stats"]["emergency_wait"]
            eu, _, _ = elida["stats"]["utilization"]
            mu, _, _ = marciano["stats"]["utilization"]
            eo, _, _ = elida["stats"]["overtime"]
            mo, _, _ = marciano["stats"]["overtime"]
            et, _, _ = elida["stats"]["emergency_within_target"]
            mt, _, _ = marciano["stats"]["emergency_within_target"]
            lines = [
                f"Clinic Elida vs. Clinic Marciano ({len(elida['runs'])} simulated days):",
                f"• Clinic Elida: Avg wait {ew:.1f}m (Emergency: {ee:.1f}m, {et:.0f}% on-target) | Nurse util: {eu:.1f}% | Overtime: {eo:.1f}m.",
                f"• Clinic Marciano: Avg wait {mw:.1f}m (Emergency: {me:.1f}m, {mt:.0f}% on-target) | Nurse util: {mu:.1f}% | Overtime: {mo:.1f}m.",
            ]
            if mw is not None and ew is not None:
                diff = mw - ew
                if abs(diff) > 0.5:
                    heavier = "Clinic Marciano" if diff > 0 else "Clinic Elida"
                    lines.append(f"Result: {heavier} experiences higher queue congestion (average waits are {abs(diff):.1f} min longer).")
                else:
                    lines.append("Result: Both clinics achieve comparable average patient waiting times under their respective staffing levels.")
            self.insight_label.config(text="\n".join(lines))
            return

        fifo = self.results.get(POLICY_LABELS["fifo"])
        prio = self.results.get(POLICY_LABELS["priority"])
        if not (fifo and prio):
            self.insight_label.config(text="Select both FIFO and Priority to see the main comparison.")
            return
        fe, fe_h, _ = fifo["stats"]["emergency_wait"]
        pe, pe_h, _ = prio["stats"]["emergency_wait"]
        fg, _, _ = fifo["stats"]["general_wait"]
        pg, _, _ = prio["stats"]["general_wait"]
        if None in (fe, pe, fg, pg):
            self.insight_label.config(text="Not enough emergency/general patients to compare.")
            return
        change = (fe - pe) / fe * 100 if fe else 0
        overlap = fe_h is not None and pe_h is not None and (pe + pe_h) >= (fe - fe_h)
        verdict = ("The confidence intervals overlap, so the difference is not clearly significant."
                   if overlap else
                   "The confidence intervals do not overlap: the reduction is statistically clear.")
        self.insight_label.config(text=(
            f"Priority triage cut the average emergency wait from {fe:.2f} to {pe:.2f} min "
            f"({change:.0f}% lower), while General patients' wait changed from {fg:.2f} "
            f"to {pg:.2f} min. {verdict}"))

    def export_csv(self):
        if not self.results:
            messagebox.showinfo("Export CSV", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="scenario_comparison.csv",
            filetypes=[("CSV files", "*.csv")])
        if path:
            export_comparison(self.results, path)
            messagebox.showinfo("Export CSV", f"Saved comparison to:\n{path}")

