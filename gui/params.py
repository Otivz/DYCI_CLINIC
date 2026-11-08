"""Shared simulation parameter inputs with modern collapsible drawer and dynamic summaries."""

import tkinter as tk
from tkinter import ttk, messagebox

from config import SimulationConfig, CLINIC_PRESETS, DEFAULT_PEAK_PROFILE

POLICY_CHOICES = {
    "Priority (non-preemptive)": "priority",
    "FIFO (no priority)": "fifo",
    "Preemptive priority": "preemptive",
}


class ParameterPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(
            parent, bg="#ffffff", bd=1, relief=tk.SOLID,
            highlightbackground="#cbd5e1", highlightthickness=1
        )
        d = SimulationConfig()
        self.vars = {}
        self._updating_preset = False
        self.is_collapsed = False

        # --------------------------------------------------------------
        # 1. Header Frame (Compact collapsible toggle & executive summary)
        # --------------------------------------------------------------
        self.header_frame = tk.Frame(self, bg="#f8fafc", cursor="hand2", padx=10, pady=5)
        self.header_frame.pack(fill=tk.X)

        title_box = tk.Frame(self.header_frame, bg="#f8fafc")
        title_box.pack(side=tk.LEFT)

        title_lbl = tk.Label(
            title_box, text="⚙️ Simulation Parameters", font=("Segoe UI", 9, "bold"),
            bg="#f8fafc", fg="#1e293b"
        )
        title_lbl.pack(side=tk.LEFT)

        sep_lbl = tk.Label(
            title_box, text="•", font=("Segoe UI", 9, "bold"),
            bg="#f8fafc", fg="#94a3b8"
        )
        sep_lbl.pack(side=tk.LEFT, padx=6)

        self.summary_badge = tk.Label(
            title_box, text="", font=("Segoe UI", 8),
            bg="#e2e8f0", fg="#334155", padx=8, pady=2, relief=tk.FLAT
        )
        self.summary_badge.pack(side=tk.LEFT)

        self.toggle_btn = tk.Button(
            self.header_frame, text="▲  Hide Parameters", font=("Segoe UI", 8, "bold"),
            bg="#ffffff", fg="#475569", activebackground="#f1f5f9", activeforeground="#1e293b",
            relief=tk.SOLID, bd=1, padx=8, pady=1, cursor="hand2",
            command=self.toggle_collapse
        )
        self.toggle_btn.pack(side=tk.RIGHT)

        for widget in (self.header_frame, title_box, title_lbl, sep_lbl, self.summary_badge):
            widget.bind("<Button-1>", lambda _e: self.toggle_collapse())

        # --------------------------------------------------------------
        # 2. Body Frame (All input fields and controls)
        # --------------------------------------------------------------
        self.body_frame = tk.Frame(self, bg="#ffffff", padx=10, pady=6)
        self.body_frame.pack(fill=tk.X)

        # Row 0: Clinic branch preset selector
        tk.Label(
            self.body_frame, text="Clinic Branch:", font=("Segoe UI", 9, "bold"),
            bg="#ffffff", fg="#1e293b"
        ).grid(row=0, column=0, padx=(0, 4), pady=(0, 6), sticky=tk.W)

        self.clinic_var = tk.StringVar(value="Custom / Default DYCI")
        self.clinic_combo = ttk.Combobox(
            self.body_frame, textvariable=self.clinic_var, state="readonly", width=22,
            values=list(CLINIC_PRESETS.keys())
        )
        self.clinic_combo.grid(row=0, column=1, columnspan=2, pady=(0, 6), sticky=tk.W)
        self.clinic_combo.bind("<<ComboboxSelected>>", self._on_clinic_changed)

        self.clinic_desc = tk.Label(
            self.body_frame, text=CLINIC_PRESETS["Custom / Default DYCI"]["description"],
            fg="#4a5568", bg="#ffffff", font=("Segoe UI", 9, "italic")
        )
        self.clinic_desc.grid(row=0, column=3, columnspan=11, padx=(8, 0), pady=(0, 6), sticky=tk.W)

        # Row 1 & 2: Primary numeric simulation inputs
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
        self._add_row(row0, 1)
        self._add_row(row1, 2)

        # Policy selector (Row 1, end columns)
        col = len(row0) * 2
        tk.Label(
            self.body_frame, text="Policy", font=("Segoe UI", 9),
            bg="#ffffff", fg="#334155"
        ).grid(row=1, column=col, padx=(12, 4), sticky=tk.W)
        self.policy_var = tk.StringVar(value="Priority (non-preemptive)")
        self.policy_combo = ttk.Combobox(
            self.body_frame, textvariable=self.policy_var, state="readonly", width=24,
            values=list(POLICY_CHOICES),
        )
        self.policy_combo.grid(row=1, column=col + 1, columnspan=3, sticky=tk.W)
        self.policy_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_field_edited())

        # Dynamic behaviour toggles (Row 2, end columns)
        col = len(row1) * 2
        self.peak_var = tk.BooleanVar(value=False)
        self.peak_check = ttk.Checkbutton(
            self.body_frame, text="Peak hours", variable=self.peak_var,
            command=self._on_field_edited
        )
        self.peak_check.grid(row=2, column=col, padx=(12, 4), sticky=tk.W)

        self.renege_var = tk.BooleanVar(value=False)
        self.renege_check = ttk.Checkbutton(
            self.body_frame, text="Reneging, patience (min)",
            variable=self.renege_var, command=self._on_field_edited
        )
        self.renege_check.grid(row=2, column=col + 1, columnspan=2, padx=(12, 4), sticky=tk.W)

        self.vars["general_patience"] = tk.StringVar(value=str(d.general_patience))
        ttk.Entry(self.body_frame, textvariable=self.vars["general_patience"], width=6).grid(
            row=2, column=col + 3, sticky=tk.W)

        # Informational footnote
        tk.Label(
            self.body_frame,
            text="ℹ️ Defaults represent calibrated operational profiles for Clinic Elida and Clinic Marciano.",
            fg="#64748b", bg="#ffffff", font=("Segoe UI", 8, "italic"),
        ).grid(row=3, column=0, columnspan=14, sticky=tk.W, pady=(4, 0))

        # Add traces for all text entry variables
        for var in self.vars.values():
            var.trace_add("write", lambda *_: self._on_field_edited())

        self.clinic_var.trace_add("write", lambda *_: self._update_summary())
        self.policy_var.trace_add("write", lambda *_: self._update_summary())

        self._update_summary()

    def _add_row(self, fields, row):
        for i, (key, label, value, width) in enumerate(fields):
            tk.Label(
                self.body_frame, text=label, font=("Segoe UI", 9),
                bg="#ffffff", fg="#334155"
            ).grid(row=row, column=i * 2, padx=(0 if i == 0 else 12, 4), pady=3, sticky=tk.W)
            var = tk.StringVar(value=f"{value:g}" if isinstance(value, float) else str(value))
            entry = ttk.Entry(self.body_frame, textvariable=var, width=width)
            entry.grid(row=row, column=i * 2 + 1, pady=3, sticky=tk.W)
            self.vars[key] = var

    def _on_clinic_changed(self, event=None):
        preset = CLINIC_PRESETS.get(self.clinic_var.get())
        if not preset:
            return
        self._updating_preset = True
        try:
            for key in ("duration", "arrival_rate", "emergency_probability", "nurses",
                        "general_mean", "general_sd", "emergency_mean",
                        "emergency_sd", "emergency_target"):
                if key in self.vars and key in preset:
                    val = preset[key]
                    self.vars[key].set(f"{val:g}" if isinstance(val, float) else str(val))
            if "use_peak_hours" in preset:
                self.peak_var.set(preset["use_peak_hours"])
            if "description" in preset:
                self.clinic_desc.config(text=preset["description"])
        finally:
            self._updating_preset = False
            self._update_summary()

    def _on_field_edited(self):
        if not self._updating_preset and self.clinic_var.get() != "Custom / Default DYCI":
            self.clinic_var.set("Custom / Default DYCI")
            self.clinic_desc.config(text="Custom parameters modified by user.")
        self._update_summary()

    def _update_summary(self):
        """Update the compact executive summary chip visible in both open & collapsed modes."""
        try:
            branch = self.clinic_var.get()
            nurses = self.vars.get("nurses", tk.StringVar(value="2")).get()
            arr = self.vars.get("arrival_rate", tk.StringVar(value="10")).get()
            emerg_prob = self.vars.get("emergency_probability", tk.StringVar(value="0.15")).get()
            try:
                emerg_pct = f"{float(emerg_prob) * 100:.0f}%"
            except Exception:
                emerg_pct = emerg_prob
            dur = self.vars.get("duration", tk.StringVar(value="8")).get()
            pol_raw = self.policy_var.get()
            pol = pol_raw.split()[0] if pol_raw else "Priority"
            peak = " • 📈 Peak" if self.peak_var.get() else ""
            renege = " • ⏳ Reneging" if self.renege_var.get() else ""

            text = f"{branch}:  {nurses} Nurses  •  {arr} arr/hr  •  {emerg_pct} Emerg  •  {pol}  •  {dur}h shift{peak}{renege}"
            self.summary_badge.config(text=text)
        except Exception:
            pass

    def toggle_collapse(self):
        """Toggle accordion collapse to reclaim vertical space for animation and charts."""
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.body_frame.pack_forget()
            self.toggle_btn.config(
                text="▼  Show Parameters",
                bg="#e2e8f0",
                fg="#1e293b"
            )
            self.summary_badge.config(bg="#dbeafe", fg="#1e40af", font=("Segoe UI", 8, "bold"))
        else:
            self.body_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
            self.toggle_btn.config(
                text="▲  Hide Parameters",
                bg="#ffffff",
                fg="#475569"
            )
            self.summary_badge.config(bg="#e2e8f0", fg="#334155", font=("Segoe UI", 8))

    def get_config(self, show_errors=True):
        """Build a SimulationConfig from the inputs, or None if invalid."""
        try:
            v = {k: var.get().strip() for k, var in self.vars.items()}
            preset = CLINIC_PRESETS.get(self.clinic_var.get())
            peak_profile = (
                preset.get("peak_profile", DEFAULT_PEAK_PROFILE)
                if preset else DEFAULT_PEAK_PROFILE
            )
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
                peak_profile=peak_profile,
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
