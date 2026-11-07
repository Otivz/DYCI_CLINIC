
from dataclasses import dataclass
from typing import Optional

@dataclass
class Patient:
    patient_id: int
    patient_type: str
    priority: int
    arrival_time: float
    service_time: float

    service_start: Optional[float] = None
    completion_time: Optional[float] = None
    assigned_nurse: Optional[str] = None

    @property
    def waiting_time(self):
        if self.service_start is None:
            return None
        return self.service_start - self.arrival_time

    @property
    def time_in_system(self):
        if self.completion_time is None:
            return None
        return self.completion_time - self.arrival_time
