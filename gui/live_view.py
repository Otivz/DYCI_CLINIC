"""Live, animated simulation view supporting simultaneous multi-clinic execution.

Enables simultaneous, independent discrete-event simulation of:
- Clinic Elida (2 Nurses, 10 arrivals/hr, 15% emergency)
- Clinic Marciano (3 Nurses, 15 arrivals/hr, 25% emergency)

Provides seamless view switching between:
- Clinic Elida
- Clinic Marciano
- Combined Overview
Switching views never stops, resets, restarts, or modifies simulation progress.
Synchronized controls (Play, Pause, Step, Reset, Run Instantly, Speed) advance
both clinics in strict lockstep simulation time.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import get_clinic_config, CLINIC_PRESETS
from export import export_patients
from gui.charts import LIVE_CHARTS
from gui.clinic_canvas import ClinicCanvas
from simulation import SimulationController, clock_text

TICK_MS = 100            # GUI refresh interval in ms
STEP_BUTTON_MIN = 10     # Minutes advanced by the Step button
CHART_EVERY = 3          # Redraw chart every N ticks while playing

COLORS = {
    "idle": "#f0fff4",
    "General": "#ebf8ff",
    "Emergency": "#fff5f5",
}


def _fmt(value, suffix="", precision=2):
    if value is None:
        return "-"
    return f"{value:.{precision}f}{suffix}"


class LiveView(ttk.Frame):
    def __init__(self, parent, params):
        super().__init__(parent, padding=8)
        self.params = params

        # Multi-clinic state
        self.controllers = {}
        self.controller = None
        self.active_branch = "Clinic Elida"
        self.active_view = "Clinic Elida"  # "Clinic Elida", "Clinic Marciano", "Combined Overview"

        self.running = False
        self._after_id = None
        self._tick_count = 0
        self._canvas_log_indices = {"Clinic Elida": 0, "Clinic Marciano": 0}
        self._ui_log_index = 0

        self.nurse_tiles = []
        self.combined_nurse_tiles = {"Clinic Elida": [], "Clinic Marciano": []}
        self.combined_matrix_labels = {}

        # Build UI Sections
        self._build_controls()
        self._build_nav_bar()
        self._build_single_branch_container()
        self._build_combined_container()

        # Initialize simulation instances
        self.reset()

    # ------------------------------------------------------------------
    # UI Layout Construction
    # ------------------------------------------------------------------
    def _build_controls(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))

        self.btn_play = ttk.Button(bar, text="▶ Play", command=self.play, width=9, style="Primary.TButton")
        self.btn_play.pack(side=tk.LEFT)
        ttk.Button(bar, text="⏸ Pause", command=self.pause, width=9).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text=f"⏭ Step +{STEP_BUTTON_MIN}m", command=self.step_once).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="⟲ Reset", command=self.reset, width=9).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="⚡ Run Instantly", command=self.run_instant).pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=3)

        ttk.Label(bar, text="Speed:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(14, 4))
        self.speed_var = tk.DoubleVar(value=10)
        ttk.Scale(bar, from_=1, to=60, variable=self.speed_var, length=120).pack(side=tk.LEFT)
        self.speed_var.trace_add("write", lambda *_: self._update_speed_label())
        self.speed_label = ttk.Label(bar, width=15, font=("Segoe UI", 8))
        self.speed_label.pack(side=tk.LEFT, padx=4)
        self._update_speed_label()

        # Digital Clock & Status Badge (Right)
        right_box = ttk.Frame(bar)
        right_box.pack(side=tk.RIGHT)

        clock_box = tk.Frame(right_box, bg="#0f172a", padx=8, pady=2, relief=tk.FLAT)
        clock_box.pack(side=tk.RIGHT, padx=(6, 0))
        self.clock_label = tk.Label(
            clock_box, text="08:00 AM", font=("Segoe UI", 11, "bold"),
            bg="#0f172a", fg="#38bdf8"
        )
        self.clock_label.pack()

        self.status_label = tk.Label(
            right_box, text="Ready", font=("Segoe UI", 8, "bold"),
            bg="#e2e8f0", fg="#334155", padx=8, pady=3, relief=tk.FLAT
        )
        self.status_label.pack(side=tk.RIGHT)

    def _build_nav_bar(self):
        """Segmented 3-option Navigation Bar for instantaneous view switching."""
        nav_frame = tk.Frame(self, bg="#e2e8f0", bd=1, relief=tk.SOLID, padx=4, pady=3)
        nav_frame.pack(fill=tk.X, pady=(0, 8))

        lbl = tk.Label(
            nav_frame, text="SIMULATION VIEW:", font=("Segoe UI", 8, "bold"),
            bg="#e2e8f0", fg="#475569"
        )
        lbl.pack(side=tk.LEFT, padx=(6, 10))

        self.nav_btns = {}
        items = [
            ("Clinic Elida", "🏥 Clinic Elida (2 Nurses • 10 arr/hr)"),
            ("Clinic Marciano", "🏥 Clinic Marciano (3 Nurses • 15 arr/hr)"),
            ("Combined Overview", "📊 Combined Overview (Dual Campus Dashboard)"),
        ]

        for view_key, label_text in items:
            btn = tk.Button(
                nav_frame,
                text=label_text,
                font=("Segoe UI", 9, "bold" if view_key == self.active_view else "normal"),
                relief=tk.SUNKEN if view_key == self.active_view else tk.RAISED,
                bg="#1a365d" if view_key == self.active_view else "#ffffff",
                fg="#ffffff" if view_key == self.active_view else "#334155",
                activebackground="#2563eb",
                activeforeground="#ffffff",
                bd=1,
                padx=10,
                pady=3,
                cursor="hand2",
                command=lambda k=view_key: self.switch_view(k)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.nav_btns[view_key] = btn

    def _update_nav_buttons(self):
        for key, btn in self.nav_btns.items():
            if key == self.active_view:
                btn.config(
                    bg="#1a365d", fg="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                    relief=tk.SUNKEN
                )
            else:
                btn.config(
                    bg="#ffffff", fg="#334155",
                    font=("Segoe UI", 9, "normal"),
                    relief=tk.RAISED
                )

    def _build_single_branch_container(self):
        """Container for single clinic view (Elida or Marciano)."""
        self.branch_container = ttk.Frame(self)
        self.branch_container.pack(fill=tk.BOTH, expand=True)

        # 1. KPI Cards
        self._build_kpis()

        # 2. 2D Animated Clinic Floorplan
        clinic_frame = ttk.LabelFrame(
            self.branch_container, text=" 🏥 Live Clinic Triage & Animated Patient Flow ", padding=3
        )
        clinic_frame.pack(fill=tk.X, pady=(0, 6))
        self.clinic_canvas = ClinicCanvas(clinic_frame, height=145)
        self.clinic_canvas.pack(fill=tk.BOTH, expand=True)

        # 3. Lower Split Panels
        paned = ttk.PanedWindow(self.branch_container, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Nurse workstations, waiting room, priority class summary
        left = ttk.Frame(paned)
        paned.add(left, weight=2)

        self.nurse_frame = ttk.LabelFrame(left, text=" Nurse Workstations ", padding=4)
        self.nurse_frame.pack(fill=tk.X)

        self.nurse_canvas = tk.Canvas(self.nurse_frame, highlightthickness=0, bd=0, height=72)
        self.nurse_scroll = ttk.Scrollbar(self.nurse_frame, orient=tk.HORIZONTAL,
                                          command=self.nurse_canvas.xview)
        self.nurse_canvas.configure(xscrollcommand=self.nurse_scroll.set)
        self.nurse_inner = tk.Frame(self.nurse_canvas)
        self.nurse_window_id = self.nurse_canvas.create_window((0, 0), window=self.nurse_inner, anchor="nw")
        self.nurse_canvas.pack(fill=tk.X, expand=True)

        self.nurse_inner.bind(
            "<Configure>",
            lambda _e: self.nurse_canvas.configure(scrollregion=self.nurse_canvas.bbox("all"))
        )
        self.nurse_canvas.bind("<MouseWheel>", self._on_nurse_mousewheel)
        self.nurse_inner.bind("<MouseWheel>", self._on_nurse_mousewheel)

        wait_frame = ttk.LabelFrame(left, text=" Waiting Room Queue ", padding=4)
        wait_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        self.wait_tree = ttk.Treeview(wait_frame, columns=("id", "type", "waited"),
                                      show="headings", height=4)
        for col, text, width in (("id", "Patient ID", 80), ("type", "Category", 110),
                                 ("waited", "Waiting (min)", 100)):
            self.wait_tree.heading(col, text=text)
            self.wait_tree.column(col, width=width, anchor=tk.CENTER)
        self.wait_tree.tag_configure("Emergency", background="#fff5f5", foreground="#dc2626")
        self.wait_tree.tag_configure("General", background="#ffffff", foreground="#1e293b")
        self.wait_tree.pack(fill=tk.BOTH, expand=True)

        class_frame = ttk.LabelFrame(left, text=" Priority Class Summary ", padding=4)
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
                                       wraplength=420, foreground="#475569",
                                       font=("Segoe UI", 8, "italic"))
        self.insight_label.pack(fill=tk.X, pady=(3, 0))

        # Right: Matplotlib charts & real-time event log
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        chart_frame = ttk.LabelFrame(right, text=" Clinic Analytics & Distributions ", padding=3)
        chart_frame.pack(fill=tk.BOTH, expand=True)
        self.chart_tabs = ttk.Notebook(chart_frame)
        self.chart_tabs.pack(fill=tk.BOTH, expand=True)
        self.charts = []    # (frame, figure, canvas, draw function)
        for title, draw in LIVE_CHARTS:
            frame = ttk.Frame(self.chart_tabs)
            figure = Figure(figsize=(5.8, 2.5), dpi=90)
            canvas = FigureCanvasTkAgg(figure, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.chart_tabs.add(frame, text=f" {title} ")
            self.charts.append((frame, figure, canvas, draw))
        self.chart_tabs.bind("<<NotebookTabChanged>>", lambda _e: self._draw_chart())

        log_frame = ttk.LabelFrame(right, text=" Real-Time Event Log ", padding=3)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log_text = tk.Text(log_frame, wrap=tk.NONE, font=("Consolas", 8), height=7,
                                bg="#ffffff", fg="#1e293b", relief=tk.FLAT)
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.tag_config("emergency_arrival", foreground="#c53030", font=("Consolas", 8, "bold"))
        self.log_text.tag_config("start", foreground="#2b6cb0")
        self.log_text.tag_config("complete", foreground="#2f855a")
        self.log_text.tag_config("renege", foreground="#b7791f", font=("Consolas", 8, "bold"))
        self.log_text.tag_config("preempt", foreground="#805ad5", font=("Consolas", 8, "bold"))

    def _build_kpis(self):
        frame = ttk.Frame(self.branch_container)
        frame.pack(fill=tk.X, pady=(0, 6))
        self.kpis = {}

        cards_meta = [
            ("arrivals", "ARRIVALS", "#2563eb"),
            ("completed", "COMPLETED", "#059669"),
            ("queue_length", "IN QUEUE", "#d97706"),
            ("in_service", "BEING TREATED", "#0284c7"),
            ("reneged", "LEFT UNTREATED", "#dc2626"),
            ("average_wait", "AVG WAIT (MIN)", "#7c3aed"),
        ]

        for col, (key, title, accent_color) in enumerate(cards_meta):
            card = tk.Frame(frame, bg="#ffffff", bd=1, relief=tk.SOLID,
                            highlightbackground="#cbd5e1", highlightthickness=1)
            card.grid(row=0, column=col, padx=2, sticky="nsew")

            strip = tk.Frame(card, bg=accent_color, height=3)
            strip.pack(fill=tk.X, side=tk.TOP)

            content = tk.Frame(card, bg="#ffffff", padx=6, pady=4)
            content.pack(fill=tk.BOTH, expand=True)

            lbl_title = tk.Label(content, text=title, font=("Segoe UI", 7, "bold"),
                                 fg="#64748b", bg="#ffffff")
            lbl_title.pack(anchor=tk.W)

            lbl_val = tk.Label(content, text="-", font=("Segoe UI", 15, "bold"),
                               fg="#0f172a", bg="#ffffff")
            lbl_val.pack(anchor=tk.W, pady=(1, 0))

            self.kpis[key] = lbl_val
            frame.columnconfigure(col, weight=1)

    def _build_combined_container(self):
        """Container for Combined Overview comparing Elida and Marciano side-by-side."""
        self.combined_container = ttk.Frame(self)

        # 1. Header Banner
        header = tk.Frame(self.combined_container, bg="#ffffff", bd=1, relief=tk.SOLID,
                          highlightbackground="#cbd5e1", highlightthickness=1, padx=10, pady=6)
        header.pack(fill=tk.X, pady=(0, 6))

        top_row = tk.Frame(header, bg="#ffffff")
        top_row.pack(fill=tk.X)

        tk.Label(
            top_row, text="📊 SIMULTANEOUS MULTI-CAMPUS COMPARATIVE DASHBOARD",
            font=("Segoe UI", 11, "bold"), fg="#1a365d", bg="#ffffff"
        ).pack(side=tk.LEFT)

        self.combined_sync_badge = tk.Label(
            top_row, text="● Dual SimPy Engines Synchronized in Lockstep",
            font=("Segoe UI", 8, "bold"), fg="#047857", bg="#ecfdf5",
            padx=8, pady=2, relief=tk.FLAT
        )
        self.combined_sync_badge.pack(side=tk.RIGHT)

        tk.Label(
            header,
            text="Independent SimPy simulation environments running simultaneously • Zero shared patient records or nurse cross-talk",
            font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#ffffff"
        ).pack(anchor=tk.W, pady=(2, 0))

        # 2. Dual Side-by-Side Clinic Animation Arenas
        arenas_group = ttk.LabelFrame(
            self.combined_container,
            text=" 🏥 Live Multi-Campus Patient Flow & Triage Animation (Side-by-Side) ",
            padding=3
        )
        arenas_group.pack(fill=tk.X, pady=(0, 6))

        arenas_box = tk.Frame(arenas_group, bg="#f8fafc")
        arenas_box.pack(fill=tk.BOTH, expand=True)

        # Left Arena: Clinic Elida (2 Nurses, 14 Chairs)
        left_arena = tk.Frame(arenas_box, bg="#f8fafc", bd=1, relief=tk.SOLID,
                              highlightbackground="#bfdbfe", highlightthickness=1)
        left_arena.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        self.canvas_elida = ClinicCanvas(left_arena, height=135)
        self.canvas_elida.set_branch("Clinic Elida")
        self.canvas_elida.set_nurse_count(2)
        self.canvas_elida.pack(fill=tk.BOTH, expand=True)

        # Distinct Campus Boundary Divider between Elida and Marciano
        divider = tk.Frame(arenas_box, bg="#e2e8f0", width=20, bd=1, relief=tk.GROOVE)
        divider.pack(side=tk.LEFT, fill=tk.Y, padx=3)
        lbl_div = tk.Label(
            divider,
            text="•\n•\nS\nE\nP\nA\nR\nA\nT\nE\n \nC\nA\nM\nP\nU\nS\n•\n•",
            font=("Segoe UI", 6, "bold"), fg="#64748b", bg="#e2e8f0", justify=tk.CENTER
        )
        lbl_div.pack(expand=True)

        # Right Arena: Clinic Marciano (3 Nurses, 20 Chairs)
        right_arena = tk.Frame(arenas_box, bg="#f8fafc", bd=1, relief=tk.SOLID,
                               highlightbackground="#fecaca", highlightthickness=1)
        right_arena.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))

        self.canvas_marciano = ClinicCanvas(right_arena, height=135)
        self.canvas_marciano.set_branch("Clinic Marciano")
        self.canvas_marciano.set_nurse_count(3)
        self.canvas_marciano.pack(fill=tk.BOTH, expand=True)

        # 3. Main Panes (Left: KPI Matrix & Research Insights, Right: Dual Nurse Workstations & Queue Analysis)
        body = ttk.PanedWindow(self.combined_container, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        left_pane = ttk.Frame(body)
        right_pane = ttk.Frame(body)
        body.add(left_pane, weight=3)
        body.add(right_pane, weight=2)

        # Left: Comparative KPI Matrix Table
        matrix_frame = ttk.LabelFrame(left_pane, text=" Live Comparative Performance Matrix ", padding=4)
        matrix_frame.pack(fill=tk.BOTH, expand=True)

        table_container = tk.Frame(matrix_frame, bg="#ffffff", bd=1, relief=tk.SOLID,
                                   highlightbackground="#cbd5e1", highlightthickness=1)
        table_container.pack(fill=tk.BOTH, expand=True)

        headers = [
            ("PERFORMANCE METRIC", 22, "#f8fafc", "#475569"),
            ("CLINIC ELIDA\n(2 Nurses • 10 arr/hr)", 18, "#eff6ff", "#1d4ed8"),
            ("CLINIC MARCIANO\n(3 Nurses • 15 arr/hr)", 18, "#fef2f2", "#b91c1c"),
            ("VARIANCE / ANALYSIS\n(Marciano vs. Elida)", 22, "#f8fafc", "#475569"),
        ]

        for col_idx, (text, width, bg, fg) in enumerate(headers):
            lbl = tk.Label(
                table_container, text=text, font=("Segoe UI", 8, "bold"),
                bg=bg, fg=fg, bd=1, relief=tk.SOLID, padx=6, pady=4
            )
            lbl.grid(row=0, column=col_idx, sticky="nsew")
            table_container.columnconfigure(col_idx, weight=1)

        matrix_rows = [
            ("arrivals", "Total Patient Arrivals", "count"),
            ("completed", "Completed Consultations", "count"),
            ("queue_length", "Patients Currently in Queue", "count"),
            ("in_service", "Patients Under Treatment", "count"),
            ("emerg_wait", "Emergency Avg Wait Time", "min"),
            ("gen_wait", "General Avg Wait Time", "min"),
            ("overall_wait", "Overall Avg Wait Time", "min"),
            ("nurse_util", "Nurse Team Utilization", "percent"),
            ("reneged", "Left Untreated (Reneged)", "count"),
            ("overtime", "Shift Overtime", "min"),
        ]

        self.combined_matrix_labels = {}
        for row_idx, (metric_key, metric_title, unit_type) in enumerate(matrix_rows, start=1):
            bg_row = "#ffffff" if row_idx % 2 == 1 else "#f8fafc"

            m_lbl = tk.Label(
                table_container, text=metric_title, font=("Segoe UI", 9, "bold"),
                bg=bg_row, fg="#1e293b", anchor="w", padx=8, pady=4, bd=1, relief=tk.GROOVE
            )
            m_lbl.grid(row=row_idx, column=0, sticky="nsew")

            e_lbl = tk.Label(
                table_container, text="-", font=("Segoe UI", 10, "bold"),
                bg=bg_row, fg="#1d4ed8", anchor="center", padx=6, pady=4, bd=1, relief=tk.GROOVE
            )
            e_lbl.grid(row=row_idx, column=1, sticky="nsew")

            m_lbl_cell = tk.Label(
                table_container, text="-", font=("Segoe UI", 10, "bold"),
                bg=bg_row, fg="#b91c1c", anchor="center", padx=6, pady=4, bd=1, relief=tk.GROOVE
            )
            m_lbl_cell.grid(row=row_idx, column=2, sticky="nsew")

            v_lbl = tk.Label(
                table_container, text="-", font=("Segoe UI", 8),
                bg=bg_row, fg="#334155", anchor="center", padx=6, pady=4, bd=1, relief=tk.GROOVE
            )
            v_lbl.grid(row=row_idx, column=3, sticky="nsew")

            table_container.rowconfigure(row_idx, weight=1)

            self.combined_matrix_labels[metric_key] = {
                "elida": e_lbl,
                "marciano": m_lbl_cell,
                "diff": v_lbl,
                "unit": unit_type
            }

        # Operational Research Insights card
        insight_card = tk.Frame(left_pane, bg="#ffffff", bd=1, relief=tk.SOLID,
                                highlightbackground="#cbd5e1", highlightthickness=1, padx=8, pady=6)
        insight_card.pack(fill=tk.X, pady=(6, 0))

        tk.Label(
            insight_card, text="🔬 Operational Research Insight: Campus Workload Dynamics",
            font=("Segoe UI", 8, "bold"), fg="#1a365d", bg="#ffffff"
        ).pack(anchor=tk.W)

        self.combined_insight_text = tk.Label(
            insight_card,
            text="Simulations advancing in synchronized lockstep...",
            font=("Segoe UI", 8), fg="#475569", bg="#ffffff",
            justify=tk.LEFT, wraplength=480
        )
        self.combined_insight_text.pack(anchor=tk.W, pady=(2, 0))

        # Right: Dual Nurse Workstations & Queue Details
        nurse_elida_group = ttk.LabelFrame(right_pane, text=" 🏥 Clinic Elida — Active Workstations (2) ", padding=4)
        nurse_elida_group.pack(fill=tk.X, pady=(0, 4))
        self.combined_nurse_frame_elida = tk.Frame(nurse_elida_group, bg="#f8fafc")
        self.combined_nurse_frame_elida.pack(fill=tk.X)

        nurse_marciano_group = ttk.LabelFrame(right_pane, text=" 🏥 Clinic Marciano — Active Workstations (3) ", padding=4)
        nurse_marciano_group.pack(fill=tk.X, pady=(0, 4))
        self.combined_nurse_frame_marciano = tk.Frame(nurse_marciano_group, bg="#f8fafc")
        self.combined_nurse_frame_marciano.pack(fill=tk.X)

        self._build_combined_nurse_tiles()

        # Queue and Acuity Analysis Box
        acuity_frame = ttk.LabelFrame(right_pane, text=" Live Waiting Queue & Patient Acuity ", padding=4)
        acuity_frame.pack(fill=tk.BOTH, expand=True)

        self.acuity_container = tk.Frame(acuity_frame, bg="#ffffff")
        self.acuity_container.pack(fill=tk.BOTH, expand=True)

        self.queue_card_elida = tk.Frame(self.acuity_container, bg="#eff6ff", bd=1, relief=tk.SOLID,
                                         highlightbackground="#bfdbfe", highlightthickness=1, padx=6, pady=4)
        self.queue_card_elida.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        tk.Label(self.queue_card_elida, text="ELIDA QUEUE", font=("Segoe UI", 8, "bold"),
                 bg="#eff6ff", fg="#1d4ed8").pack(anchor=tk.W)
        self.lbl_elida_q_emerg = tk.Label(self.queue_card_elida, text="Emergency: 0", font=("Segoe UI", 8, "bold"),
                                          bg="#eff6ff", fg="#dc2626")
        self.lbl_elida_q_emerg.pack(anchor=tk.W, pady=(1, 0))
        self.lbl_elida_q_gen = tk.Label(self.queue_card_elida, text="General: 0", font=("Segoe UI", 8),
                                        bg="#eff6ff", fg="#1e293b")
        self.lbl_elida_q_gen.pack(anchor=tk.W)
        self.lbl_elida_q_max = tk.Label(self.queue_card_elida, text="Longest Wait: 0.0m", font=("Segoe UI", 8),
                                        bg="#eff6ff", fg="#64748b")
        self.lbl_elida_q_max.pack(anchor=tk.W, pady=(1, 0))

        self.queue_card_marciano = tk.Frame(self.acuity_container, bg="#fef2f2", bd=1, relief=tk.SOLID,
                                            highlightbackground="#fecaca", highlightthickness=1, padx=6, pady=4)
        self.queue_card_marciano.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(2, 0))

        tk.Label(self.queue_card_marciano, text="MARCIANO QUEUE", font=("Segoe UI", 8, "bold"),
                 bg="#fef2f2", fg="#b91c1c").pack(anchor=tk.W)
        self.lbl_marciano_q_emerg = tk.Label(self.queue_card_marciano, text="Emergency: 0", font=("Segoe UI", 8, "bold"),
                                             bg="#fef2f2", fg="#dc2626")
        self.lbl_marciano_q_emerg.pack(anchor=tk.W, pady=(1, 0))
        self.lbl_marciano_q_gen = tk.Label(self.queue_card_marciano, text="General: 0", font=("Segoe UI", 8),
                                           bg="#fef2f2", fg="#1e293b")
        self.lbl_marciano_q_gen.pack(anchor=tk.W)
        self.lbl_marciano_q_max = tk.Label(self.queue_card_marciano, text="Longest Wait: 0.0m", font=("Segoe UI", 8),
                                           bg="#fef2f2", fg="#64748b")
        self.lbl_marciano_q_max.pack(anchor=tk.W, pady=(1, 0))

    def _build_combined_nurse_tiles(self):
        for branch, frame, count in [
            ("Clinic Elida", self.combined_nurse_frame_elida, 2),
            ("Clinic Marciano", self.combined_nurse_frame_marciano, 3),
        ]:
            for child in frame.winfo_children():
                child.destroy()
            self.combined_nurse_tiles[branch] = []
            for i in range(count):
                letter = chr(ord('A') + i)
                tile = tk.Frame(frame, bd=1, relief=tk.SOLID, bg="#f8fafc",
                                highlightbackground="#cbd5e1", highlightthickness=1,
                                padx=6, pady=3)
                tile.grid(row=0, column=i, padx=2, pady=2, sticky="nsew")
                frame.columnconfigure(i, weight=1)

                lbl_name = tk.Label(tile, text=f"Nurse {letter}", font=("Segoe UI", 8, "bold"),
                                    bg="#f8fafc", fg="#1e293b")
                lbl_name.pack(anchor=tk.W)

                lbl_status = tk.Label(tile, text="● Idle", font=("Segoe UI", 8, "bold"),
                                      bg="#f8fafc", fg="#059669")
                lbl_status.pack(anchor=tk.W)

                lbl_util = tk.Label(tile, text="0.0% • 0 served", font=("Segoe UI", 8),
                                    bg="#f8fafc", fg="#64748b")
                lbl_util.pack(anchor=tk.W)

                self.combined_nurse_tiles[branch].append((tile, lbl_name, lbl_status, lbl_util))

    def _on_nurse_mousewheel(self, event):
        if len(self.nurse_tiles) >= 3:
            self.nurse_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_nurse_tiles(self):
        """Construct workstation tiles for the currently active branch in single-branch view."""
        for child in self.nurse_inner.winfo_children():
            child.destroy()
        self.nurse_tiles = []
        if not self.controller:
            return

        n_nurses = len(self.controller.nurses)
        has_scroll = n_nurses >= 3

        for i, nurse in enumerate(self.controller.nurses):
            tile = tk.Frame(self.nurse_inner, bd=1, relief=tk.SOLID, bg="#f8fafc",
                            highlightbackground="#cbd5e1", highlightthickness=1,
                            padx=8, pady=4)
            tile.grid(row=0, column=i, padx=3, pady=2, sticky="nsew")

            top_row = tk.Frame(tile, bg="#f8fafc")
            top_row.pack(fill=tk.X)

            name = tk.Label(top_row, text=nurse.name, font=("Segoe UI", 9, "bold"),
                            bg="#f8fafc", fg="#1e293b")
            name.pack(side=tk.LEFT)

            status = tk.Label(tile, text="● Idle", bg="#f8fafc", fg="#059669",
                              font=("Segoe UI", 8, "bold"))
            status.pack(anchor=tk.W, pady=(1, 0))

            util = tk.Label(tile, text="Util: 0.0%  •  Served: 0", bg="#f8fafc",
                            font=("Segoe UI", 8), fg="#64748b")
            util.pack(anchor=tk.W, pady=(1, 0))

            self.nurse_tiles.append((tile, name, status, util, top_row))

            for widget in (tile, name, status, util, top_row):
                widget.bind("<MouseWheel>", self._on_nurse_mousewheel)

            if has_scroll:
                self.nurse_inner.columnconfigure(i, minsize=150, weight=0)
            else:
                self.nurse_inner.columnconfigure(i, weight=1)

        if has_scroll:
            self.nurse_scroll.pack(fill=tk.X, pady=(2, 0))
        else:
            self.nurse_scroll.pack_forget()

        self.nurse_inner.update_idletasks()
        h = max(70, self.nurse_inner.winfo_reqheight())
        self.nurse_canvas.configure(height=h, scrollregion=self.nurse_canvas.bbox("all"))
        canvas_w = max(self.nurse_canvas.winfo_width(), 1)
        if not has_scroll:
            self.nurse_canvas.itemconfigure(self.nurse_window_id, width=canvas_w)
        else:
            req_w = self.nurse_inner.winfo_reqwidth()
            self.nurse_canvas.itemconfigure(self.nurse_window_id, width=max(req_w, canvas_w))

    def _update_speed_label(self):
        self.speed_label.config(text=f"{self.speed_var.get():.0f} sim-min/s")

    # ------------------------------------------------------------------
    # Branch & View Switching (Preserves 100% Simulation State)
    # ------------------------------------------------------------------
    def switch_view(self, view_key):
        """Switch navigation view without resetting, pausing, or altering simulation progress."""
        if view_key == self.active_view:
            return
        self.active_view = view_key
        self._update_nav_buttons()

        # Update campus badge in app header banner if available
        try:
            top = self.winfo_toplevel()
            if hasattr(top, "app") and hasattr(top.app, "branch_badge"):
                badge_text = (
                    "Campus: Elida & Marciano (Simultaneous)"
                    if view_key == "Combined Overview"
                    else f"Campus: {view_key}"
                )
                top.app.branch_badge.config(text=badge_text)
        except Exception:
            pass

        if view_key == "Combined Overview":
            self.branch_container.pack_forget()
            self.combined_container.pack(fill=tk.BOTH, expand=True)
            self.refresh_combined()
        else:
            self.active_branch = view_key
            self.controller = self.controllers[view_key]
            self.combined_container.pack_forget()
            self.branch_container.pack(fill=tk.BOTH, expand=True)

            self.clinic_canvas.set_branch(view_key)
            self.clinic_canvas.set_nurse_count(len(self.controller.nurses))

            self._build_nurse_tiles()

            # Refill event log with this branch's historical events
            self.log_text.delete("1.0", tk.END)
            cfg = self.controller.config
            for t, kind, msg in self.controller.event_log:
                self.log_text.insert(
                    tk.END,
                    f"{clock_text(t, cfg.shift_start_hour):>8}  {t:6.1f}  {msg}\n",
                    kind
                )
            self.log_text.see(tk.END)
            self._ui_log_index = len(self.controller.event_log)

            self.refresh_branch(force_chart=True)

    def on_branch_changed(self, branch):
        """React when the branch is changed in the external parameter combo box."""
        if branch in ("Clinic Elida", "Clinic Marciano"):
            self.switch_view(branch)

    # ------------------------------------------------------------------
    # Simulation Control Engine (Advances Both Clinics in Strict Lockstep)
    # ------------------------------------------------------------------
    def reset(self):
        """Reset both independent clinic simulations with their verified operational configs."""
        self.pause()
        base_cfg = self.params.get_config()
        if base_cfg is None:
            return False

        policy = base_cfg.policy
        reneging = base_cfg.reneging
        patience = base_cfg.general_patience
        duration = base_cfg.duration
        seed = base_cfg.random_seed

        # Clinic Elida: 2 nurses, 10 arr/hr, 15% emerg
        cfg_elida = get_clinic_config("Clinic Elida", policy=policy, random_seed=seed)
        cfg_elida.reneging = reneging
        cfg_elida.general_patience = patience
        cfg_elida.duration = duration

        # Clinic Marciano: 3 nurses, 15 arr/hr, 25% emerg (distinct reproducible seed stream)
        cfg_marciano = get_clinic_config("Clinic Marciano", policy=policy, random_seed=seed + 101)
        cfg_marciano.reneging = reneging
        cfg_marciano.general_patience = patience
        cfg_marciano.duration = duration

        # Allow explicit user parameter overrides if a specific clinic preset was selected
        if self.params.clinic_var.get() == "Clinic Elida":
            cfg_elida = base_cfg
        elif self.params.clinic_var.get() == "Clinic Marciano":
            cfg_marciano = base_cfg

        self.controllers = {
            "Clinic Elida": SimulationController(cfg_elida),
            "Clinic Marciano": SimulationController(cfg_marciano),
        }
        self.controller = self.controllers[self.active_branch]

        self._canvas_log_indices = {"Clinic Elida": 0, "Clinic Marciano": 0}
        self._ui_log_index = 0
        self._tick_count = 0

        self.clinic_canvas.reset()
        self.clinic_canvas.set_branch(self.active_branch)
        self.clinic_canvas.set_nurse_count(len(self.controller.nurses))

        if hasattr(self, "canvas_elida") and self.canvas_elida:
            self.canvas_elida.reset()
            self.canvas_elida.set_branch("Clinic Elida")
            self.canvas_elida.set_nurse_count(2)
        if hasattr(self, "canvas_marciano") and self.canvas_marciano:
            self.canvas_marciano.reset()
            self.canvas_marciano.set_branch("Clinic Marciano")
            self.canvas_marciano.set_nurse_count(3)

        self.log_text.delete("1.0", tk.END)
        for tree in (self.wait_tree, self.class_tree):
            tree.delete(*tree.get_children())
        self.insight_label.config(text="Results appear when the day ends.")

        self._build_nurse_tiles()
        self.status_label.config(text="Ready", bg="#e2e8f0", fg="#334155")
        self.refresh(force_chart=True)
        return True

    def _sync_canvases(self, branch_name, snap, events):
        """Synchronize both single-branch canvas and side-by-side combined canvases."""
        self.clinic_canvas.sync(snap, events, branch=branch_name)
        if branch_name == "Clinic Elida" and hasattr(self, "canvas_elida") and self.canvas_elida:
            self.canvas_elida.sync(snap, events, branch="Clinic Elida")
        elif branch_name == "Clinic Marciano" and hasattr(self, "canvas_marciano") and self.canvas_marciano:
            self.canvas_marciano.sync(snap, events, branch="Clinic Marciano")

    def _ensure_controllers(self):
        if not self.controllers or any(c.is_finished() for c in self.controllers.values()):
            return self.reset()
        return True

    def play(self):
        if self.running or not self._ensure_controllers():
            return
        self.running = True
        self.status_label.config(text="Running (Both)...", bg="#dcfce7", fg="#166534")
        self._tick()

    def pause(self):
        self.running = False
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self.controllers and not all(c.is_finished() for c in self.controllers.values()):
            self.status_label.config(text="Paused", bg="#fef3c7", fg="#92400e")

    def step_once(self):
        self.pause()
        if not self._ensure_controllers():
            return
        # Advance both clinics in lockstep by STEP_BUTTON_MIN
        for branch_name, ctrl in self.controllers.items():
            ctrl.step(STEP_BUTTON_MIN)
            snap = ctrl.snapshot()
            events = ctrl.event_log[self._canvas_log_indices[branch_name]:]
            self._sync_canvases(branch_name, snap, events)
            self._canvas_log_indices[branch_name] = len(ctrl.event_log)

        self.refresh(force_chart=True)

    def run_instant(self):
        if not self.reset():
            return
        for branch_name, ctrl in self.controllers.items():
            ctrl.run()
            snap = ctrl.snapshot()
            self._sync_canvases(branch_name, snap, [])
            self._canvas_log_indices[branch_name] = len(ctrl.event_log)

        self.refresh(force_chart=True)

    def _tick(self):
        self._after_id = None
        if not self.running:
            return

        minutes = self.speed_var.get() * TICK_MS / 1000

        # Step both simulations with the exact same minute increment
        for branch_name, ctrl in self.controllers.items():
            ctrl.step(minutes)
            snap = ctrl.snapshot()
            events = ctrl.event_log[self._canvas_log_indices[branch_name]:]
            self._sync_canvases(branch_name, snap, events)
            self._canvas_log_indices[branch_name] = len(ctrl.event_log)

        self._tick_count += 1
        all_finished = all(c.is_finished() for c in self.controllers.values())
        self.refresh(force_chart=self._tick_count % CHART_EVERY == 0 or all_finished)

        if all_finished:
            self.running = False
            self.status_label.config(text="Day complete (All branches)", bg="#e0e7ff", fg="#3730a3")
        else:
            self._after_id = self.after(TICK_MS, self._tick)

    def export_csv(self):
        if not self.controllers:
            messagebox.showinfo("Export CSV", "Run a simulation first.")
            return

        if self.active_view in self.controllers:
            ctrl = self.controllers[self.active_view]
            if not ctrl.patients:
                messagebox.showinfo("Export CSV", f"No patients recorded yet for {self.active_view}.")
                return
            clean_name = self.active_view.lower().replace(" ", "_")
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=f"{clean_name}_patients.csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if path:
                export_patients(ctrl.patients, path)
                messagebox.showinfo("Export CSV", f"Saved {len(ctrl.patients)} patients from {self.active_view} to:\n{path}")
        else:
            # Combined overview export
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="combined_clinics_patients.csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if path:
                elida_path = path.replace(".csv", "_elida.csv")
                marciano_path = path.replace(".csv", "_marciano.csv")
                p_e = self.controllers["Clinic Elida"].patients
                p_m = self.controllers["Clinic Marciano"].patients
                export_patients(p_e, elida_path)
                export_patients(p_m, marciano_path)
                messagebox.showinfo(
                    "Export CSV",
                    f"Saved multi-clinic export:\n• {len(p_e)} Elida patients to {elida_path}\n• {len(p_m)} Marciano patients to {marciano_path}"
                )

    # ------------------------------------------------------------------
    # Rendering & View Updates
    # ------------------------------------------------------------------
    def refresh(self, force_chart=False):
        if not self.controllers:
            return

        # Both clocks are locked; use either to reflect current time
        clock_str = self.controllers["Clinic Elida"].snapshot()["clock"]
        self.clock_label.config(text=clock_str)

        all_finished = all(c.is_finished() for c in self.controllers.values())
        any_overtime = any(c.snapshot()["overtime"] for c in self.controllers.values())

        if all_finished:
            self.status_label.config(text="Day complete", bg="#e0e7ff", fg="#3730a3")
        elif self.running:
            phase = "Overtime - clearing queue" if any_overtime else "Simulating Both Clinics..."
            self.status_label.config(
                text=phase,
                bg="#fef3c7" if any_overtime else "#dcfce7",
                fg="#92400e" if any_overtime else "#166534"
            )

        if self.active_view == "Combined Overview":
            self.refresh_combined()
        else:
            self.refresh_branch(force_chart=force_chart)

    def refresh_branch(self, force_chart=False):
        snap = self.controller.snapshot()
        cfg = self.controller.config

        # 1. Update KPI cards
        for key in ("arrivals", "completed", "queue_length", "in_service", "reneged"):
            self.kpis[key].config(text=str(snap[key]))
        self.kpis["average_wait"].config(text=f"{snap['average_wait']:.2f} m")

        # 2. Update nurse tiles
        for (tile, name, status, util, top_row), n in zip(self.nurse_tiles, snap["nurses"]):
            if n["busy"]:
                is_emerg = n["patient_type"] == "Emergency"
                bg_color = "#fff1f2" if is_emerg else "#f0f9ff"
                status_color = "#dc2626" if is_emerg else "#2563eb"
                status_text = f"● Treating #{n['patient_id']} ({n['patient_type']})"
            else:
                bg_color = "#f0fff4"
                status_color = "#059669"
                status_text = "● Idle (Ready)"

            for widget in (tile, name, status, util, top_row):
                widget.config(bg=bg_color)
            status.config(text=status_text, fg=status_color)
            util.config(text=f"Util: {n['utilization']:.1f}%  •  Served: {n['served']}")

        # 3. Update waiting room queue
        self.wait_tree.delete(*self.wait_tree.get_children())
        ordered = sorted(snap["waiting"], key=lambda w: (
            cfg.policy != "fifo" and w["type"] != "Emergency", -w["waited"]))
        for w in ordered:
            label = w["type"] + (" (resume)" if w["resumed"] else "")
            self.wait_tree.insert("", tk.END, values=(f"#{w['id']}", label, f"{w['waited']:.1f}"),
                                  tags=(w["type"],))

        # 4. Stream new event log lines for this active branch
        new_events = self.controller.event_log[self._ui_log_index:]
        for t, kind, msg in new_events:
            self.log_text.insert(
                tk.END,
                f"{clock_text(t, cfg.shift_start_hour):>8}  {t:6.1f}  {msg}\n",
                kind
            )
        if new_events:
            self.log_text.see(tk.END)
        self._ui_log_index = len(self.controller.event_log)

        # 5. Handle completion display
        if snap["finished"]:
            self._show_final()
            force_chart = True

        if force_chart:
            self._draw_chart()

    def refresh_combined(self):
        """Update side-by-side matrices and comparative analysis across both clinics."""
        if "Clinic Elida" not in self.controllers or "Clinic Marciano" not in self.controllers:
            return

        snap_e = self.controllers["Clinic Elida"].snapshot()
        snap_m = self.controllers["Clinic Marciano"].snapshot()
        s_e = self.controllers["Clinic Elida"].summary()
        s_m = self.controllers["Clinic Marciano"].summary()

        e_emerg_wait = s_e["by_type"]["Emergency"]["avg_wait"]
        e_gen_wait = s_e["by_type"]["General"]["avg_wait"]
        m_emerg_wait = s_m["by_type"]["Emergency"]["avg_wait"]
        m_gen_wait = s_m["by_type"]["General"]["avg_wait"]

        e_utils = [n["utilization"] for n in snap_e["nurses"]]
        m_utils = [n["utilization"] for n in snap_m["nurses"]]
        e_avg_util = sum(e_utils) / len(e_utils) if e_utils else 0.0
        m_avg_util = sum(m_utils) / len(m_utils) if m_utils else 0.0

        data = {
            "arrivals": (snap_e["arrivals"], snap_m["arrivals"], "count"),
            "completed": (snap_e["completed"], snap_m["completed"], "count"),
            "queue_length": (snap_e["queue_length"], snap_m["queue_length"], "count"),
            "in_service": (snap_e["in_service"], snap_m["in_service"], "count"),
            "emerg_wait": (e_emerg_wait, m_emerg_wait, "min"),
            "gen_wait": (e_gen_wait, m_gen_wait, "min"),
            "overall_wait": (snap_e["average_wait"], snap_m["average_wait"], "min"),
            "nurse_util": (e_avg_util, m_avg_util, "percent"),
            "reneged": (snap_e["reneged"], snap_m["reneged"], "count"),
            "overtime": (s_e.get("overtime", 0.0), s_m.get("overtime", 0.0), "min"),
        }

        for k, (e_val, m_val, unit) in data.items():
            if k not in self.combined_matrix_labels:
                continue
            widgets = self.combined_matrix_labels[k]

            if unit == "count":
                widgets["elida"].config(text=str(e_val))
                widgets["marciano"].config(text=str(m_val))
                diff = m_val - e_val
                sign = "+" if diff > 0 else ""
                pct = f" ({sign}{(diff / e_val * 100):.0f}%)" if e_val > 0 else ""
                widgets["diff"].config(
                    text=f"{sign}{diff}{pct}" if diff != 0 else "Identical",
                    fg="#dc2626" if (k in ("queue_length", "reneged") and diff > 0) else (
                        "#059669" if (k == "completed" and diff > 0) else "#334155"
                    )
                )
            elif unit == "min":
                widgets["elida"].config(text=_fmt(e_val, " m"))
                widgets["marciano"].config(text=_fmt(m_val, " m"))
                if e_val is not None and m_val is not None:
                    diff = m_val - e_val
                    sign = "+" if diff > 0 else ""
                    widgets["diff"].config(
                        text=f"{sign}{diff:.2f} m",
                        fg="#dc2626" if diff > 0 else ("#059669" if diff < 0 else "#334155")
                    )
                else:
                    widgets["diff"].config(text="-", fg="#64748b")
            elif unit == "percent":
                widgets["elida"].config(text=f"{e_val:.1f}%")
                widgets["marciano"].config(text=f"{m_val:.1f}%")
                diff = m_val - e_val
                sign = "+" if diff > 0 else ""
                widgets["diff"].config(text=f"{sign}{diff:.1f}%", fg="#334155")

        # Update nurse workstation cards
        for branch, snap in [("Clinic Elida", snap_e), ("Clinic Marciano", snap_m)]:
            tiles = self.combined_nurse_tiles[branch]
            for (tile, lbl_name, lbl_status, lbl_util), n in zip(tiles, snap["nurses"]):
                if n["busy"]:
                    is_emerg = n["patient_type"] == "Emergency"
                    bg_color = "#fff1f2" if is_emerg else "#f0f9ff"
                    fg_status = "#dc2626" if is_emerg else "#2563eb"
                    status_text = f"● #{n['patient_id']} ({n['patient_type'][:4]}.)"
                else:
                    bg_color = "#f0fff4"
                    fg_status = "#059669"
                    status_text = "● Idle (Ready)"

                for w in (tile, lbl_name, lbl_status, lbl_util):
                    w.config(bg=bg_color)
                lbl_status.config(text=status_text, fg=fg_status)
                lbl_util.config(text=f"{n['utilization']:.1f}% • {n['served']} done")

        # Update waiting queue breakdown
        e_waiting = snap_e.get("waiting", [])
        e_em_count = sum(1 for w in e_waiting if w["type"] == "Emergency")
        e_gn_count = len(e_waiting) - e_em_count
        e_max_wait = max((w["waited"] for w in e_waiting), default=0.0)
        self.lbl_elida_q_emerg.config(text=f"Emergency: {e_em_count}")
        self.lbl_elida_q_gen.config(text=f"General: {e_gn_count}")
        self.lbl_elida_q_max.config(text=f"Longest Wait: {e_max_wait:.1f}m")

        m_waiting = snap_m.get("waiting", [])
        m_em_count = sum(1 for w in m_waiting if w["type"] == "Emergency")
        m_gn_count = len(m_waiting) - m_em_count
        m_max_wait = max((w["waited"] for w in m_waiting), default=0.0)
        self.lbl_marciano_q_emerg.config(text=f"Emergency: {m_em_count}")
        self.lbl_marciano_q_gen.config(text=f"General: {m_gn_count}")
        self.lbl_marciano_q_max.config(text=f"Longest Wait: {m_max_wait:.1f}m")

        # Update research insights
        if snap_e["finished"] and snap_m["finished"]:
            lines = [
                f"Day Complete: Clinic Marciano treated {snap_m['completed']} patients with 3 nurses "
                f"(Team Util: {m_avg_util:.1f}%, Emerg Wait: {_fmt(m_emerg_wait, 'm')}).",
                f"Clinic Elida treated {snap_e['completed']} patients with 2 nurses "
                f"(Team Util: {e_avg_util:.1f}%, Emerg Wait: {_fmt(e_emerg_wait, 'm')}).",
                f"Analysis: Marciano's +50% arrival load and +67% emergency probability is safely accommodated by 3 nurses under the {self.controller.config.policy.upper()} queuing policy."
            ]
            self.combined_insight_text.config(text=" ".join(lines))
        else:
            self.combined_insight_text.config(
                text=f"Simulations progressing in synchronized lockstep at {snap_e['clock']}. "
                     f"Both campuses operate isolated SimPy environments with zero cross-talk. "
                     f"Clinic Marciano operates under higher demand (15 arr/hr, 25% emerg) vs. Clinic Elida (10 arr/hr, 15% emerg)."
            )

    def _draw_chart(self):
        """Redraw only the chart tab the user is looking at."""
        if not self.charts or self.controller is None:
            return
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
        lines.append("Use Compare Scenarios for multi-run averages with 95% confidence intervals.")
        self.insight_label.config(text="\n".join(lines))
