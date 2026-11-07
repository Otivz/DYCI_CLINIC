"""Main application window."""

import tkinter as tk
from tkinter import ttk

from gui.compare_view import CompareView
from gui.live_view import LiveView
from gui.params import ParameterPanel


class ClinicSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DYCI Clinic: General vs. Emergency Priority")
        self.root.geometry("1280x860")
        self.root.minsize(1100, 720)

        self._setup_styles()

        main = ttk.Frame(root, padding=(14, 10))
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="DYCI Clinic Simulator", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="SimPy Discrete Event Simulation: General vs. Emergency Priority Queuing",
            style="Subtitle.TLabel",
        ).pack(anchor=tk.W)

        self.params = ParameterPanel(main)
        self.params.pack(fill=tk.X, pady=(0, 8))

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.live_view = LiveView(notebook, self.params)
        self.compare_view = CompareView(notebook, self.params)
        notebook.add(self.live_view, text="  Live Simulation  ")
        notebook.add(self.compare_view, text="  Compare Scenarios  ")

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#1a365d")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#4a5568")
        style.configure("CardHeader.TLabel", font=("Segoe UI", 9, "bold"), foreground="#718096")
        style.configure("CardValue.TLabel", font=("Segoe UI", 15, "bold"), foreground="#2b6cb0")
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"))

    def _on_close(self):
        self.live_view.pause()
        self.root.destroy()

