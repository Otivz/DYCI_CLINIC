"""Shared simulation parameter inputs."""

import tkinter as tk
from tkinter import ttk, messagebox

from config import SimulationConfig

POLICY_CHOICES = {
    "Priority (non-preemptive)": "priority",
    "FIFO (no priority)": "fifo",
    "Preemptive priority": "preemptive",
}


class ParameterPanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text=" Simulation Parameters ", padding=10)
        d = SimulationConfig()
        self.vars = {}

        row0 = [
            ("duration", "Duration (hrs)", d.duration / 60, 6),
            ("arrival_rate", "Arrivals / hr", d.arrival_rate, 6),
            ("emergency_probability", "Emergency prob.", d.emergency_probability, 6),
            ("nurses", "Nurses", d.nurses, 4),
            ("random_seed", "Seed", d.random_seed, 6),
        ]
        row1 = [
            ("general_mean", "General mean (min)", d.general_mean, 6),
            ("general_sd", "General SD", d.general_sd, 5),
            ("emergency_mean", "Emergency mean (min)", d.emergency_mean, 6),
            ("emergency_sd", "Emergency SD", d.emergency_sd, 5),
            ("emergency_target", "Emerg. target (min)", d.emergency_target, 5),
        ]
        self._add_row(row0, 0)
        self._add_row(row1, 1)

        # Policy selector
        col = len(row0) * 2
        ttk.Label(self, text="Policy").grid(row=0, column=col, padx=(12, 4), sticky=tk.W)
        self.policy_var = tk.StringVar(value="Priority (non-preemptive)")
        ttk.Combobox(
            self, textvariable=self.policy_var, state="readonly", width=24,
            values=list(POLICY_CHOICES),
        ).grid(row=0, column=col + 1, columnspan=3, sticky=tk.W)

        # Dynamic behaviour toggles
        col = len(row1) * 2
        self.peak_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Peak hours", variable=self.peak_var).grid(
            row=1, column=col, padx=(12, 4), sticky=tk.W)
        self.renege_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Reneging, patience (min)",
                        variable=self.renege_var).grid(
            row=1, column=col + 1, columnspan=2, padx=(12, 4), sticky=tk.W)
        self.vars["general_patience"] = tk.StringVar(value=str(d.general_patience))
        ttk.Entry(self, textvariable=self.vars["general_patience"], width=6).grid(
            row=1, column=col + 3, sticky=tk.W)

        ttk.Label(
            self,
            text="Defaults are placeholders - replace with DYCI clinic data.",
            foreground="#a0522d", font=("Segoe UI", 8, "italic"),
        ).grid(row=2, column=0, columnspan=14, sticky=tk.W, pady=(6, 0))

    def _add_row(self, fields, row):
        for i, (key, label, value, width) in enumerate(fields):
            ttk.Label(self, text=label).grid(
                row=row, column=i * 2, padx=(0 if i == 0 else 12, 4), pady=3, sticky=tk.W)
            var = tk.StringVar(value=f"{value:g}" if isinstance(value, float) else str(value))
            ttk.Entry(self, textvariable=var, width=width).grid(
                row=row, column=i * 2 + 1, pady=3, sticky=tk.W)
            self.vars[key] = var

    def get_config(self, show_errors=True):
        """Build a SimulationConfig from the inputs, or None if invalid."""
        try:
            v = {k: var.get().strip() for k, var in self.vars.items()}
            config = SimulationConfig(
                duration=float(v["duration"]) * 60,
                arrival_rate=float(v["arrival_rate"]),
                emergency_probability=float(v["emergency_probability"]),
                nurses=int(v["nurses"]),
                random_seed=int(v["random_seed"]),
                general_mean=float(v["general_mean"]),
                general_sd=float(v["general_sd"]),
                emergency_mean=float(v["emergency_mean"]),
                emergency_sd=float(v["emergency_sd"]),
                general_patience=float(v["general_patience"]),
                emergency_target=float(v["emergency_target"]),
                policy=POLICY_CHOICES[self.policy_var.get()],
                use_peak_hours=self.peak_var.get(),
                reneging=self.renege_var.get(),
            )
        except ValueError:
            if show_errors:
                messagebox.showerror(
                    "Invalid input",
                    "Please enter numbers in every field "
                    "(Nurses and Seed must be whole numbers).")
            return None

        errors = config.validate()
        if errors:
            if show_errors:
                messagebox.showerror("Invalid input", "\n".join(errors))
            return None
        return config

