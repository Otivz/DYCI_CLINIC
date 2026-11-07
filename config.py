from dataclasses import dataclass

# Queue policies supported by the simulation engine.
#   priority   - Emergency first, but a nurse always finishes the current patient.
#   fifo       - First come, first served (no triage). Baseline for comparison.
#   preemptive - Emergency may interrupt a nurse treating a General patient.
POLICIES = ("priority", "fifo", "preemptive")

# PLACEHOLDER hourly multipliers applied to arrival_rate when use_peak_hours
# is enabled. Index 0 = first hour of the shift (e.g. 8-9 AM). The profile
# repeats if the shift is longer than the list.
# Replace with observed DYCI clinic visit counts per hour.
DEFAULT_PEAK_PROFILE = (0.6, 1.0, 1.5, 1.8, 1.0, 0.8, 1.2, 0.6)

# Preset profiles for DYCI clinic branches
CLINIC_PRESETS = {
    "Clinic Elida": {
        "description": "Elida Campus Clinic - Moderate general student flow.",
        "duration": 8.0,
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
        "description": "Marciano Campus Clinic - Higher volume and acute cases.",
        "duration": 8.0,
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
        "duration": 8.0,
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


def get_clinic_config(clinic_name, policy="priority", random_seed=42):
    """Return a SimulationConfig initialized with the parameters of a named clinic preset."""
    preset = CLINIC_PRESETS.get(clinic_name, CLINIC_PRESETS["Custom / Default DYCI"])
    return SimulationConfig(
        duration=preset["duration"] * 60,
        nurses=preset["nurses"],
        arrival_rate=preset["arrival_rate"],
        emergency_probability=preset["emergency_probability"],
        general_mean=preset["general_mean"],
        general_sd=preset["general_sd"],
        emergency_mean=preset["emergency_mean"],
        emergency_sd=preset["emergency_sd"],
        emergency_target=preset["emergency_target"],
        use_peak_hours=preset["use_peak_hours"],
        peak_profile=preset["peak_profile"],
        policy=policy,
        random_seed=random_seed,
    )


@dataclass
class SimulationConfig:
    # NOTE: the numeric defaults below are PLACEHOLDERS, not real DYCI data.
    # Replace them with values from the proposal or clinic records.
    duration: float = 480.0             # Shift length in minutes (8 hours)
    nurses: int = 2                     # Number of nurses on duty
    arrival_rate: float = 12.0          # Average patients per hour
    emergency_probability: float = 0.20  # Share of emergency cases
    emergency_priority: int = 0         # SimPy priority: lower = served first
    general_priority: int = 1           # Regular priority
    emergency_mean: float = 15.0        # Emergency service time mean (min)
    emergency_sd: float = 5.0           # Emergency service time SD (min)
    general_mean: float = 10.0          # General service time mean (min)
    general_sd: float = 3.0             # General service time SD (min)
    random_seed: int = 42               # Seed for reproducible results

    # Dynamic behaviour
    policy: str = "priority"            # One of POLICIES
    use_peak_hours: bool = False        # Time-varying arrival rate
    peak_profile: tuple = DEFAULT_PEAK_PROFILE
    reneging: bool = False              # General patients may leave the queue
    general_patience: float = 30.0      # Mean minutes before a General patient leaves
    shift_start_hour: float = 8.0       # Clock display only (8.0 = 8:00 AM)
    emergency_target: float = 5.0       # PLACEHOLDER: max minutes an emergency should wait

    def arrival_rate_at(self, t):
        """Arrival rate (patients/hour) at simulation minute t."""
        if not self.use_peak_hours or not self.peak_profile:
            return self.arrival_rate
        hour = int(t // 60) % len(self.peak_profile)
        return self.arrival_rate * self.peak_profile[hour]

    def max_arrival_rate(self):
        """Highest arrival rate during the shift (used for thinning)."""
        if not self.use_peak_hours or not self.peak_profile:
            return self.arrival_rate
        return self.arrival_rate * max(self.peak_profile)

    def validate(self):
        """Return a list of human-readable problems (empty if valid)."""
        errors = []
        if self.duration <= 0:
            errors.append("Duration must be greater than 0.")
        if self.nurses < 1:
            errors.append("There must be at least 1 nurse.")
        if self.nurses > 26:
            errors.append("At most 26 nurses are supported (Nurse A-Z).")
        if self.arrival_rate <= 0:
            errors.append("Arrival rate must be greater than 0.")
        if not 0 <= self.emergency_probability <= 1:
            errors.append("Emergency probability must be between 0 and 1.")
        for label, mean, sd in (
            ("General", self.general_mean, self.general_sd),
            ("Emergency", self.emergency_mean, self.emergency_sd),
        ):
            if mean <= 0 or sd <= 0:
                errors.append(f"{label} service mean and SD must be greater than 0.")
        if self.policy not in POLICIES:
            errors.append(f"Policy must be one of {', '.join(POLICIES)}.")
        if self.emergency_target <= 0:
            errors.append("Emergency target must be greater than 0.")
        if self.reneging and self.general_patience <= 0:
            errors.append("Patience must be greater than 0.")
        if self.use_peak_hours and (
            not self.peak_profile or min(self.peak_profile) < 0
        ):
            errors.append("Peak profile multipliers must be non-negative.")
        return errors
