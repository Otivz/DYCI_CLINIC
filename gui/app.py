"""Main application window with modernized healthcare dashboard styling."""

import tkinter as tk
from tkinter import ttk

from gui.compare_view import CompareView
from gui.live_view import LiveView
from gui.params import ParameterPanel


class ClinicSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.app = self
        self.root.title("DYCI Clinic Simulator • General vs. Emergency Priority Queuing")
        self.root.geometry("1300x880")
        self.root.minsize(1120, 740)
        self.root.configure(bg="#f1f5f9")

        self._setup_styles()

        main = ttk.Frame(root, padding=(16, 12), style="App.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        # Modern Header Banner
        header = ttk.Frame(main, style="Header.TFrame")
        header.pack(fill=tk.X, pady=(0, 10))

        # Title & Subtitle (Left)
        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        title_row = ttk.Frame(title_box, style="Header.TFrame")
        title_row.pack(anchor=tk.W)

        ttk.Label(
            title_row, text="🏥 DYCI Clinic Simulator",
            style="Title.TLabel"
        ).pack(side=tk.LEFT)

        ttk.Label(
            title_box,
            text="SimPy Discrete-Event Simulation • General vs. Emergency Priority Queuing Analysis",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))

        # System & Branch Badges (Right)
        badge_box = ttk.Frame(header, style="Header.TFrame")
        badge_box.pack(side=tk.RIGHT, fill=tk.Y)

        self.branch_badge = tk.Label(
            badge_box, text="Branch: Custom / Default DYCI",
            font=("Segoe UI", 9, "bold"), bg="#e2e8f0", fg="#1e293b",
            padx=10, pady=4, relief=tk.FLAT
        )
        self.branch_badge.pack(side=tk.RIGHT, padx=(8, 0))

        engine_badge = tk.Label(
            badge_box, text="● SimPy Engine Active",
            font=("Segoe UI", 8, "bold"), bg="#ecfdf5", fg="#047857",
            padx=8, pady=4, relief=tk.FLAT
        )
        engine_badge.pack(side=tk.RIGHT)

        # Simulation Parameters Panel
        self.params = ParameterPanel(main)
        self.params.pack(fill=tk.X, pady=(0, 10))

        # Keep branch badge in sync with selected clinic
        self.params.clinic_var.trace_add(
            "write", lambda *_: self._update_branch_badge()
        )
        self._update_branch_badge()

        # Primary Tabs
        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.live_view = LiveView(notebook, self.params)
        self.compare_view = CompareView(notebook, self.params)
        notebook.add(self.live_view, text="  Live Simulation & Clinic View  ")
        notebook.add(self.compare_view, text="  Compare Scenarios & Branches  ")

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _update_branch_badge(self):
        branch = self.params.clinic_var.get()
        self.branch_badge.config(text=f"Campus: {branch}")
        if hasattr(self, "live_view") and self.live_view:
            self.live_view.on_branch_changed(branch)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Background palette
        bg_app = "#f1f5f9"
        card_bg = "#ffffff"
        primary_navy = "#1a365d"
        text_dark = "#1e293b"
        border_light = "#cbd5e1"

        style.configure("App.TFrame", background=bg_app)
        style.configure("Header.TFrame", background=bg_app)
        style.configure("Card.TFrame", background=card_bg, relief="solid", borderwidth=1)

        # Header Typography
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"),
                        foreground=primary_navy, background=bg_app)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10),
                        foreground="#475569", background=bg_app)

        # KPI Typography
        style.configure("CardHeader.TLabel", font=("Segoe UI", 8, "bold"),
                        foreground="#64748b", background=card_bg)
        style.configure("CardValue.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground=primary_navy, background=card_bg)

        # Notebook Tabs
        style.configure(
            "TNotebook",
            background=bg_app,
            borderwidth=0
        )
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 6),
            background="#e2e8f0",
            foreground="#334155"
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff"), ("active", "#cbd5e1")],
            foreground=[("selected", primary_navy), ("active", "#0f172a")]
        )

        # Buttons
        style.configure(
            "TButton",
            font=("Segoe UI", 9),
            padding=(8, 4),
            borderwidth=1,
            background="#ffffff"
        )
        style.map(
            "TButton",
            background=[("pressed", "#e2e8f0"), ("active", "#f8fafc")],
            foreground=[("active", primary_navy)]
        )

        # Primary Action Button
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 9, "bold"),
            background="#2563eb",
            foreground="#ffffff",
            padding=(10, 4)
        )
        style.map(
            "Primary.TButton",
            background=[("pressed", "#1d4ed8"), ("active", "#1e40af")],
            foreground=[("active", "#ffffff")]
        )

        # Treeview
        style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            rowheight=24,
            background="#ffffff",
            fieldbackground="#ffffff",
            bordercolor=border_light,
            borderwidth=1
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#e2e8f0",
            foreground="#1e293b",
            relief="flat",
            padding=(4, 4)
        )
        style.map("Treeview.Heading", background=[("active", "#cbd5e1")])

    def _on_close(self):
        self.live_view.pause()
        self.root.destroy()

