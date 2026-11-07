# Option 1 Implementation Plan: Clinic Preset Profile Selector

This document details the architectural design, data structures, and code implementation steps for adding multi-clinic support (**Clinic Elida**, **Clinic Marciano**, and **Custom / Default**) to the DYCI Clinic Simulator.

---

## 1. Architectural Overview

The goal of Option 1 is to provide a seamless **Clinic Selector Dropdown** in the parameter panel that automatically populates the simulation inputs with branch-specific data.

```
       [ Clinic Selector Dropdown ]
       ├── Clinic Elida
       ├── Clinic Marciano
       └── Custom / Default DYCI
                    │
                    ▼ (On selection)
       [ CLINIC_PRESETS Dictionary ]
                    │
                    ▼ (Auto-populates)
   [ Parameter Panel Input Fields (gui/params.py) ]
   ├── Nurses (e.g., 2 vs. 3)
   ├── Arrival Rate (patients/hr)
   ├── Emergency Probability
   └── Service Times & Peak Profile
```

---

## 2. Configuration & Preset Definitions (`config.py`)

Define the preset profiles in [`config.py`](config.py) using a dictionary mapping branch names to their parameter dictionaries.

### Proposed Code in `config.py`:

```python
# Branch preset profiles for DYCI clinics
CLINIC_PRESETS = {
    "Clinic Elida": {
        "description": "Elida Campus Clinic - Moderate general flow, focused on student consultations.",
        "nurses": 2,
        "arrival_rate": 10.0,
        "emergency_probability": 0.15,
        "general_mean": 10.0,
        "general_sd": 3.0,
        "emergency_mean": 14.0,
        "emergency_sd": 4.0,
        "emergency_target": 5.0,
        "use_peak_hours": True,
        "peak_profile": (0.5, 1.2, 1.6, 1.4, 0.9, 0.7, 1.1, 0.6),
    },
    "Clinic Marciano": {
        "description": "Marciano Campus Clinic - Higher acute case volume and heavier peak influx.",
        "nurses": 3,
        "arrival_rate": 15.0,
        "emergency_probability": 0.25,
        "general_mean": 12.0,
        "general_sd": 4.0,
        "emergency_mean": 16.0,
        "emergency_sd": 5.0,
        "emergency_target": 5.0,
        "use_peak_hours": True,
        "peak_profile": (0.8, 1.5, 1.9, 1.6, 1.0, 0.8, 1.3, 0.7),
    },
    "Custom / Default DYCI": {
        "description": "Baseline DYCI configuration with standard parameters.",
        "nurses": 2,
        "arrival_rate": 12.0,
        "emergency_probability": 0.20,
        "general_mean": 10.0,
        "general_sd": 3.0,
        "emergency_mean": 15.0,
        "emergency_sd": 5.0,
        "emergency_target": 5.0,
        "use_peak_hours": False,
        "peak_profile": DEFAULT_PEAK_PROFILE,
    },
}
```

---

## 3. UI Implementation (`gui/params.py`)

In [`gui/params.py`](gui/params.py), add the clinic selector dropdown and connect it to an update handler that updates the UI entry fields.

### Step-by-Step UI Changes:

1. **Import `CLINIC_PRESETS`**:
   ```python
   from config import SimulationConfig, POLICY_CHOICES, CLINIC_PRESETS
   ```

2. **Add Clinic Dropdown to `ParameterPanel.__init__`**:
   Place a header or a prominent row at the top of the parameter frame:
   ```python
   clinic_row = ttk.Frame(self)
   clinic_row.grid(row=0, column=0, columnspan=12, sticky=tk.W, pady=(0, 6))

   ttk.Label(clinic_row, text="Clinic Location:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
   self.clinic_var = tk.StringVar(value="Custom / Default DYCI")
   self.clinic_combo = ttk.Combobox(
       clinic_row, textvariable=self.clinic_var, state="readonly",
       values=list(CLINIC_PRESETS.keys()), width=24
   )
   self.clinic_combo.pack(side=tk.LEFT)
   self.clinic_combo.bind("<<ComboboxSelected>>", self._on_clinic_changed)

   self.clinic_desc = ttk.Label(clinic_row, text="", foreground="#718096", font=("Segoe UI", 8, "italic"))
   self.clinic_desc.pack(side=tk.LEFT, padx=(10, 0))
   ```

3. **Preset Selection Handler**:
   ```python
   def _on_clinic_changed(self, event=None):
       clinic_name = self.clinic_var.get()
       preset = CLINIC_PRESETS.get(clinic_name)
       if not preset:
           return

       # Update entry fields
       for key in ("nurses", "arrival_rate", "emergency_probability",
                   "general_mean", "general_sd", "emergency_mean",
                   "emergency_sd", "emergency_target"):
           if key in self.vars and key in preset:
               self.vars[key].set(str(preset[key]))

       # Update toggles
       if "use_peak_hours" in preset:
           self.peak_var.set(preset["use_peak_hours"])

       # Update description text
       if "description" in preset:
           self.clinic_desc.config(text=preset["description"])
   ```

4. **Automatic 'Custom' Switching**:
   If a user selects "Clinic Elida" and then manually edits any entry field (like increasing nurses to 4), trace listeners switch the dropdown to `"Custom"` to keep user intent explicit.

---

## 4. Verification & Testing Procedure

Once implemented, the feature can be verified through the following test cases:

1. **Preset Loading Test**:
   * Select **Clinic Elida**: Verify nurses update to `2`, arrival rate to `10.0`, and emergency prob. to `0.15`.
   * Select **Clinic Marciano**: Verify nurses update to `3`, arrival rate to `15.0`, and emergency prob. to `0.25`.
2. **Simulation Run Test**:
   * Click **Play** or **Run Instantly** for Clinic Elida; verify event log and nurse tiles reflect 2 nurses.
   * Switch to Clinic Marciano and click **Reset**; verify 3 nurse tiles appear (Nurse A, Nurse B, Nurse C).
3. **Policy Comparison Test**:
   * Run the **Compare Scenarios** tab under Clinic Elida's volume vs. Clinic Marciano's volume to observe the impact of increased arrivals on emergency wait times.

---

## 5. Future Extensibility

* **Adding New Locations**: Additional DYCI buildings or annex clinics can be added simply by defining new keys in the `CLINIC_PRESETS` dictionary in `config.py` without touching GUI layout logic.
* **Empirical Data Integration**: Once actual empirical visit logs from DYCI's clinics are collected, the placeholder values in `CLINIC_PRESETS` can be updated directly with real-world observed statistics.

