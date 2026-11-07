from dataclasses import dataclass


@dataclass
class SimulationConfig:
    duration: float = 480.0             # 8-hour shift in minutes
    nurses: int = 2                     # Number of nurses
    arrival_rate: float = 12.0          # Patients per hour
    emergency_probability: float = 0.20  # 20% emergency cases
    emergency_priority: int = 0         # SimPy PriorityResource: lower is higher priority
    general_priority: int = 1           # Regular priority
    emergency_mean: float = 15.0        # Mean service time in minutes
    emergency_sd: float = 5.0           # Standard deviation
    general_mean: float = 10.0          # Mean service time in minutes
    general_sd: float = 3.0             # Standard deviation
    random_seed: int = 42               # Seed for reproducible results
