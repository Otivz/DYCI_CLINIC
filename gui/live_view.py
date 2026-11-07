"""Live, animated simulation view."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from export import export_patients
from gui.charts import LIVE_CHARTS
from simulation import SimulationController, clock_text

TICK_MS = 100            # GUI refresh interval
STEP_BUTTON_MIN = 10     # Minutes advanced by the Step button
CHART_EVERY = 3          # Redraw chart every N ticks while playing

COLORS = {
    "idle": "#c6f6d5",
    "General": "#bee3f8",
    "Emergency": "#fed7d7",
}


def _fmt(value, suffix=""):
    return "-" if value is None else f"{value:.2f}{suffix}"


class LiveView(ttk.Frame):
    def __init__(self, parent, params):
        super().__init__(parent, padding=8)
        self.params = params
        self.controller = None
        self.running = False
        self._after_id = None
        self._log_index = 0
        self._tick_count = 0
        self.nurse_tiles = []

        self._build_controls()
        self._build_kpis()
        self._build_body()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_controls(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 8))

        self.btn_play = ttk.Button(bar, text="▶ Play", command=self.play, width=9)
        self.btn_play.pack(side=tk.LEFT)
        ttk.Button(bar, text="⏸ Pause", command=self.pause, width=9).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text=f"⏭ Step +{STEP_BUTTON_MIN}m", command=self.step_once).pack(side=tk.LEFT)
        ttk.Button(bar, text="⟲ Reset", command=self.reset, width=9).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="⚡ Run Instantly", command=self.run_instant).pack(side=tk.LEFT)
        ttk.Button(bar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=4)

        ttk.Label(bar, text="Speed:").pack(side=tk.LEFT, padx=(16, 4))
        self.speed_var = tk.DoubleVar(value=10)
        ttk.Scale(bar, from_=1, to=60, variable=self.speed_var, length=140).pack(side=tk.LEFT)
        self.speed_var.trace_add("write", lambda *_: self._update_speed_label())
        self.speed_label = ttk.Label(bar, width=16)
        self.speed_label.pack(side=tk.LEFT, padx=4)
        self._update_speed_label()

        self.clock_label = ttk.Label(bar, text="--:--", font=("Segoe UI", 16, "bold"),
                                     foreground="#1a365d")
        self.clock_label.pack(side=tk.RIGHT)
        self.status_label = ttk.Label(bar, text="Ready", foreground="#4a5568")
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def _build_kpis(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.kpis = {}
        for col, (key, title) in enumerate([
            ("arrivals", "Arrivals"),
            ("completed", "Completed"),
            ("queue_length", "In Queue"),
            ("in_service", "Being Treated"),
            ("reneged", "Left Untreated"),
            ("average_wait", "Avg Wait (so far)"),
        ]):
            card = ttk.Frame(frame, relief=tk.SOLID, borderwidth=1, padding=8)
            card.grid(row=0, column=col, padx=3, sticky="nsew")
            ttk.Label(card, text=title, style="CardHeader.TLabel").pack(anchor=tk.W)
            value = ttk.Label(card, text="-", style="CardValue.TLabel")
            value.pack(anchor=tk.W)
            self.kpis[key] = value
            frame.columnconfigure(col, weight=1)

    def _build_body(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: nurses, waiting room, class comparison
        left = ttk.Frame(paned)
        paned.add(left, weight=2)

        self.nurse_frame = ttk.LabelFrame(left, text=" Nurses ", padding=6)
        self.nurse_frame.pack(fill=tk.X)

        wait_frame = ttk.LabelFrame(left, text=" Waiting Room ", padding=6)
        wait_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        self.wait_tree = ttk.Treeview(wait_frame, columns=("id", "type", "waited"),
                                      show="headings", height=6)
        for col, text, width in (("id", "Patient", 70), ("type", "Type", 110),
                                 ("waited", "Waiting (min)", 100)):
            self.wait_tree.heading(col, text=text)
            self.wait_tree.column(col, width=width, anchor=tk.CENTER)
        self.wait_tree.tag_configure("Emergency", background=COLORS["Emergency"])
        self.wait_tree.pack(fill=tk.BOTH, expand=True)

        class_frame = ttk.LabelFrame(left, text=" Priority Class Comparison ", padding=6)
        class_frame.pack(fill=tk.X)
        cols = ("type", "count", "wait", "service", "system")
        self.class_tree = ttk.Treeview(class_frame, columns=cols, show="headings", height=2)
        for col, text, width in (("type", "Category", 90), ("count", "Done", 50),
                                 ("wait", "Avg Wait", 75), ("service", "Avg Service", 85),
                                 ("system", "Avg System", 80)):
            self.class_tree.heading(col, text=text)
            self.class_tree.column(col, width=width, anchor=tk.CENTER)
        self.class_tree.pack(fill=tk.X)
        self.insight_label = ttk.Label(class_frame, text="Results appear when the day ends.",
                                       wraplength=420, foreground="#4a5568",
                                       font=("Segoe UI", 9, "italic"))
        self.insight_label.pack(fill=tk.X, pady=(4, 0))

        # Right: chart + event log
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        chart_frame = ttk.LabelFrame(right, text=" Clinic Analytics ", padding=4)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        self.chart_tabs = ttk.Notebook(chart_frame)
        self.chart_tabs.pack(fill=tk.BOTH, expand=True)
        self.charts = []    # (frame, figure, canvas, draw function)
        for title, draw in LIVE_CHARTS:
            frame = ttk.Frame(self.chart_tabs)
            figure = Figure(figsize=(6, 2.8), dpi=90)
            canvas = FigureCanvasTkAgg(figure, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.chart_tabs.add(frame, text=f" {title} ")
            self.charts.append((frame, figure, canvas, draw))
        self.chart_tabs.bind("<<NotebookTabChanged>>", lambda _e: self._draw_chart())
        self._draw_chart()

        log_frame = ttk.LabelFrame(right, text=" Event Log ", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.log_text = tk.Text(log_frame, wrap=tk.NONE, font=("Consolas", 9), height=10)
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.tag_config("emergency_arrival", foreground="#c53030",
                                 font=("Consolas", 9, "bold"))
        self.log_text.tag_config("start", foreground="#2b6cb0")
        self.log_text.tag_config("complete", foreground="#2f855a")
        self.log_text.tag_config("renege", foreground="#b7791f", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("preempt", foreground="#805ad5", font=("Consolas", 9, "bold"))

    def _build_nurse_tiles(self):
        for child in self.nurse_frame.winfo_children():
            child.destroy()
        self.nurse_tiles = []
        per_row = 4
        for i, nurse in enumerate(self.controller.nurses):
            tile = tk.Frame(self.nurse_frame, bd=1, relief=tk.SOLID, bg=COLORS["idle"],
                            padx=6, pady=4)
            tile.grid(row=i // per_row, column=i % per_row, padx=3, pady=3, sticky="nsew")
            name = tk.Label(tile, text=nurse.name, font=("Segoe UI", 10, "bold"),
                            bg=COLORS["idle"])
            name.pack(anchor=tk.W)
            status = tk.Label(tile, text="Idle", bg=COLORS["idle"], font=("Segoe UI", 9))
            status.pack(anchor=tk.W)
            util = tk.Label(tile, text="Util: 0.0%", bg=COLORS["idle"],
                            font=("Segoe UI", 8), fg="#4a5568")
            util.pack(anchor=tk.W)
            self.nurse_tiles.append((tile, name, status, util))
            self.nurse_frame.columnconfigure(i % per_row, weight=1)

    def _update_speed_label(self):
        self.speed_label.config(text=f"{self.speed_var.get():.0f} sim-min / sec")

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def reset(self):
        self.pause()
        config = self.params.get_config()
        if config is None:
            return False
        self.controller = SimulationController(config)
        self._log_index = 0
        self._tick_count = 0
        self.log_text.delete("1.0", tk.END)
        for tree in (self.wait_tree, self.class_tree):
            tree.delete(*tree.get_children())
        self.insight_label.config(text="Results appear when the day ends.")
        self._build_nurse_tiles()
        self.status_label.config(text="Ready")
        self.refresh(force_chart=True)
        return True

    def _ensure_controller(self):
        if self.controller is None or self.controller.is_finished():
            return self.reset()
        return True

    def play(self):
        if self.running or not self._ensure_controller():
            return
        self.running = True
        self.status_label.config(text="Running...")
        self._tick()

    def pause(self):
        self.running = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self.controller and not self.controller.is_finished():
            self.status_label.config(text="Paused")

    def step_once(self):
        self.pause()
        if not self._ensure_controller():
            return
        self.controller.step(STEP_BUTTON_MIN)
        self.refresh(force_chart=True)

    def run_instant(self):
        if not self.reset():
            return
        self.controller.run()
        self.refresh(force_chart=True)

    def _tick(self):
        self._after_id = None
        if not self.running:
            return
        minutes = self.speed_var.get() * TICK_MS / 1000
        self.controller.step(minutes)
        self._tick_count += 1
        self.refresh(force_chart=self._tick_count % CHART_EVERY == 0)
        if self.controller.is_finished():
            self.running = False
        else:
            self._after_id = self.after(TICK_MS, self._tick)

    def export_csv(self):
        if self.controller is None or not self.controller.patients:
            messagebox.showinfo("Export CSV", "Run a simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile="clinic_patients.csv",
            filetypes=[("CSV files", "*.csv")])
        if path:
            export_patients(self.controller.patients, path)
            messagebox.showinfo("Export CSV", f"Saved {len(self.controller.patients)} patients to:\n{path}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def refresh(self, force_chart=False):
        snap = self.controller.snapshot()
        cfg = self.controller.config

        self.clock_label.config(text=snap["clock"])
        for key in ("arrivals", "completed", "queue_length", "in_service", "reneged"):
            self.kpis[key].config(text=str(snap[key]))
        self.kpis["average_wait"].config(text=f"{snap['average_wait']:.2f} m")

        # Nurse tiles
        for (tile, name, status, util), n in zip(self.nurse_tiles, snap["nurses"]):
            color = COLORS[n["patient_type"]] if n["busy"] else COLORS["idle"]
            text = (f"Treating #{n['patient_id']} ({n['patient_type']})"
                    if n["busy"] else "Idle")
            for widget in (tile, name, status, util):
                widget.config(bg=color)
            status.config(text=text)
            util.config(text=f"Util: {n['utilization']:.1f}%  |  Served: {n['served']}")

        # Waiting room (emergencies listed first, matching service order)
        self.wait_tree.delete(*self.wait_tree.get_children())
        ordered = sorted(snap["waiting"], key=lambda w: (
            cfg.policy != "fifo" and w["type"] != "Emergency", -w["waited"]))
        for w in ordered:
            label = w["type"] + (" (resume)" if w["resumed"] else "")
            self.wait_tree.insert("", tk.END, values=(f"#{w['id']}", label, f"{w['waited']:.1f}"),
                                  tags=(w["type"],))

        # Stream new log lines
        new = self.controller.event_log[self._log_index:]
        for t, kind, msg in new:
            self.log_text.insert(tk.END, f"{clock_text(t, cfg.shift_start_hour):>8}  "
                                         f"{t:6.1f}  {msg}\n", kind)
        if new:
            self.log_text.see(tk.END)
        self._log_index = len(self.controller.event_log)

        if snap["finished"]:
            self._show_final()
            force_chart = True
        elif self.running:
            phase = "Overtime - clearing queue" if snap["overtime"] else "Running..."
            self.status_label.config(text=phase)

        if force_chart:
            self._draw_chart()

    def _draw_chart(self):
        """Redraw only the chart tab the user is looking at."""
        index = self.chart_tabs.index(self.chart_tabs.select())
        _frame, figure, canvas, draw = self.charts[index]
        draw(figure, self.controller)
        canvas.draw_idle()

    def _show_final(self):
        s = self.controller.summary()
        self.class_tree.delete(*self.class_tree.get_children())
        for label, key in (("Emergency", "Emergency"), ("General", "General")):
            g = s["by_type"][key]
            self.class_tree.insert("", tk.END, values=(
                label, g["count"], _fmt(g["avg_wait"]),
                _fmt(g["avg_service"]), _fmt(g["avg_system"])))

        e = s["by_type"]["Emergency"]["avg_wait"]
        g = s["by_type"]["General"]["avg_wait"]
        lines = []
        if e is not None and g is not None:
            lines.append(f"Emergency patients waited {e:.2f} min vs. {g:.2f} min for General "
                         f"({g - e:+.2f} min difference).")
        lines.append(f"Overtime: {s['overtime']:.1f} min. Max queue: {s['max_queue']}.")
        if s["reneged"]:
            lines.append(f"{s['reneged']} General patient(s) left untreated.")
        if s["preemptions"]:
            lines.append(f"{s['preemptions']} treatment(s) interrupted by emergencies.")
        lines.append("This is ONE simulated day - use Compare Scenarios for averages with "
                     "confidence intervals.")
        self.insight_label.config(text="\n".join(lines))
        self.status_label.config(text="Day complete")
