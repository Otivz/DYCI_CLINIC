
import random
import simpy

from config import SimulationConfig
from patient import Patient
from clinic_server import ClinicServer


class SimulationController:
    def __init__(self):
        self.config = SimulationConfig()
        self.reset()

    def reset(self):
        self.env = simpy.Environment()
        self.rng = random.Random(self.config.random_seed)

        # Shared priority queue for both nurses.
        # A request represents one nurse slot.
        self.queue = simpy.PriorityResource(
            self.env,
            capacity=self.config.nurses
        )

        self.nurses = [
            ClinicServer(self.env, f"Nurse {chr(65 + i)}")
            for i in range(self.config.nurses)
        ]

        self.arrivals = 0
        self.completed = 0
        self.patients = []
        self.events = []

        self.env.process(self.generate_patients())

    def sample_gamma(self, mean, sd):
        shape = (mean / sd) ** 2
        scale = sd ** 2 / mean
        return self.rng.gammavariate(shape, scale)

    def generate_patients(self):
        while True:
            gap = self.rng.expovariate(
                self.config.arrival_rate / 60
            )

            if self.env.now + gap > self.config.duration:
                break

            yield self.env.timeout(gap)

            self.arrivals += 1

            emergency = (
                self.rng.random()
                < self.config.emergency_probability
            )

            if emergency:
                kind = "Emergency"
                priority = self.config.emergency_priority
                service_time = self.sample_gamma(
                    self.config.emergency_mean,
                    self.config.emergency_sd
                )
            else:
                kind = "General"
                priority = self.config.general_priority
                service_time = self.sample_gamma(
                    self.config.general_mean,
                    self.config.general_sd
                )

            patient = Patient(
                patient_id=self.arrivals,
                patient_type=kind,
                priority=priority,
                arrival_time=self.env.now,
                service_time=service_time
            )

            self.patients.append(patient)
            self.events.append(
                f"{self.env.now:.1f}: "
                f"Patient {patient.patient_id} arrived ({kind})"
            )

            self.env.process(self.handle_patient(patient))

    def handle_patient(self, patient):
        with self.queue.request(
            priority=patient.priority
        ) as request:

            yield request

            # Find the available nurse.
            nurse = next(
                n for n in self.nurses if not n.busy
            )

            self.events.append(
                f"{self.env.now:.1f}: "
                f"Patient {patient.patient_id} "
                f"started with {nurse.name}"
            )

            yield self.env.process(nurse.serve(patient))

            self.completed += 1

            self.events.append(
                f"{self.env.now:.1f}: "
                f"Patient {patient.patient_id} completed"
            )

    def run(self):
        self.env.run()

    def summary(self):
        finished = [
            p for p in self.patients
            if p.completion_time is not None
        ]

        waits = [p.waiting_time for p in finished]
        times = [p.time_in_system for p in finished]

        return {
            "arrivals": self.arrivals,
            "completed": self.completed,
            "average_wait": (
                sum(waits) / len(waits) if waits else 0
            ),
            "average_system_time": (
                sum(times) / len(times) if times else 0
            ),
            "nurse_utilization": {
                nurse.name: nurse.utilization(self.env.now)
                for nurse in self.nurses
            }
        }
