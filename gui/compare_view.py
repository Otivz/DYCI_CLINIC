"""Scenario comparison: many simulated days per policy, with 95% CIs."""

import tkinter as tk
from dataclasses import replace
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from experiments import METRICS, POLICY_LABELS, compare_scenarios, format_ci
from export import export_comparison
from gui.charts import draw_compare_emergency, draw_compare_load, draw_compare_waits


class CompareView(ttk.Frame):
    def __init__(self, parent, params):
        super().__init__(parent, padding=8)
        self.params = params
        self.results = None

        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(bar, text="Policies:").pack(side=tk.LEFT)
        self.policy_vars = {}
        for policy, default in (("fifo", True), ("priority", True), ("preemptive", False)):
            var = tk.BooleanVar(value=default)
            ttk.Checkbutton(bar, text=POLICY_LABELS[policy], variable=var).pack(side=tk.LEFT, padx=4)
            self.policy_vars[policy] = var

        ttk.Label(bar, text="Days (replications):").pack(side=tk.LEFT, padx=(16, 4))
        self.reps_var = tk.StringVar(value="30")
        ttk.Spinbox(bar, from_=2, to=500, textvariable=self.reps_var, width=6).pack(side=tk.LEFT)

        ttk.Button(bar, text="▶ Run Comparison", command=self.run).pack(side=tk.LEFT, padx=(16, 4))
        ttk.Button(bar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT)

        self.status_label = ttk.Label(
            bar, foreground="#4a5568",
            text="Uses the parameters above; the Policy dropdown is ignored here.")
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

    def run(self):
        config = self.params.get_config()
        if config is None:
            return
        policies = [p for p, var in self.policy_vars.items() if var.get()]
        if not policies:
            messagebox.showwarning("Compare", "Select at least one policy.")
            return
        try:
            reps = int(self.reps_var.get())
            if reps < 2:
                raise ValueError
        except ValueError:
            messagebox.showerror("Compare", "Days must be a whole number of at least 2.")
            return

        scenarios = {POLICY_LABELS[p]: replace(config, policy=p) for p in policies}
        self._target = config.emergency_target
        self.status_label.config(text=f"Running {reps} days x {len(scenarios)} policies...")
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.results = compare_scenarios(scenarios, n=reps, base_seed=config.random_seed)
        finally:
            self.config(cursor="")
        self.status_label.config(
            text=f"Done: {reps} days per policy, seeds {config.random_seed}-"
                 f"{config.random_seed + reps - 1} (same patients for every policy).")
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

