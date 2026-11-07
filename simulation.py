
import math
import random
import simpy

from config import SimulationConfig
from patient import Patient
from clinic_server import ClinicServer


def clock_text(minutes, start_hour=8.0):
    """Convert simulation minutes to a wall-clock string, e.g. '10:42 AM'."""
    total = int(round(start_hour * 60 + minutes))
    hour, minute = divmod(total, 60)
    hour %= 24
    suffix = "AM" if hour < 12 else "PM"
    display = hour % 12 or 12
    return f"{display}:{minute:02d} {suffix}"


def _group_stats(group):
    """Count and averages for a list of completed patients."""
    if not group:
        return {"count": 0, "avg_wait": None,
                "avg_service": None, "avg_system": None}
    count = len(group)
    return {
        "count": count,
        "avg_wait": sum(p.waiting_time for p in group) / count,
        "avg_service": sum(p.service_time for p in group) / count,
        "avg_system": sum(p.time_in_system for p in group) / count,
    }


class SimulationController:
    def __init__(self, config=None):
        self.config = config or SimulationConfig()
        self.reset()

    def reset(self):
        cfg = self.config
        self.env = simpy.Environment()
        self.rng = random.Random(cfg.random_seed)

        # Shared priority queue for all nurses.
        # A request represents one nurse slot.
        if cfg.policy == "preemptive":
            self.queue = simpy.PreemptiveResource(
                self.env,
                capacity=cfg.nurses
            )
        else:
            self.queue = simpy.PriorityResource(
                self.env,
                capacity=cfg.nurses
            )

        self.nurses = [
            ClinicServer(self.env, f"Nurse {chr(65 + i)}", cfg.duration)
            for i in range(cfg.nurses)
        ]

        self.arrivals = 0
        self.completed = 0
        self.reneged = 0
        self.patients = []
        self.waiting = []           # Patients currently in the waiting room
        self.event_log = []         # (time, kind, message)
        # (time, queue length, busy nurses, emergencies waiting)
        self.timeline = [(0.0, 0, 0, 0)]
        # Completed treatment blocks, for the nurse schedule chart
        self.treatments = []
        self.max_queue = 0

        self.env.process(self.generate_patients())

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    @property
    def events(self):
        """Formatted event strings (kept for backward compatibility)."""
        return [f"{t:.1f}: {msg}" for t, _kind, msg in self.event_log]

    def _log(self, kind, message):
        self.event_log.append((self.env.now, kind, message))

    def _record(self):
        busy = sum(1 for n in self.nurses if n.busy)
        emergencies = sum(1 for p in self.waiting if p.patient_type == "Emergency")
        self.timeline.append((self.env.now, len(self.waiting), busy, emergencies))
        self.max_queue = max(self.max_queue, len(self.waiting))

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------
    def sample_gamma(self, mean, sd):
        shape = (mean / sd) ** 2
        scale = sd ** 2 / mean
        return self.rng.gammavariate(shape, scale)

    def generate_patients(self):
        cfg = self.config
        max_rate = cfg.max_arrival_rate()
        if max_rate <= 0:
            return

        while True:
            # With peak hours, arrivals are generated at the maximum rate and
            # thinned (accepted with probability rate(t) / max_rate). This
            # produces a non-homogeneous Poisson arrival process.
            gap = self.rng.expovariate(
                max_rate / 60
            )

            if self.env.now + gap > cfg.duration:
                break

            yield self.env.timeout(gap)

            if cfg.use_peak_hours:
                accept = cfg.arrival_rate_at(self.env.now) / max_rate
                if self.rng.random() > accept:
                    continue

            self.arrivals += 1

            emergency = (
                self.rng.random()
                < cfg.emergency_probability
            )

            if emergency:
                kind = "Emergency"
                priority = cfg.emergency_priority
                service_time = self.sample_gamma(
                    cfg.emergency_mean,
                    cfg.emergency_sd
                )
            else:
                kind = "General"
                priority = cfg.general_priority
                service_time = self.sample_gamma(
                    cfg.general_mean,
                    cfg.general_sd
                )

            # Only General patients give up; emergencies always stay.
            patience = None
            if cfg.reneging and not emergency:
                patience = self.rng.expovariate(1 / cfg.general_patience)

            patient = Patient(
                patient_id=self.arrivals,
                patient_type=kind,
                priority=priority,
                arrival_time=self.env.now,
                service_time=service_time,
                patience=patience
            )

            self.patients.append(patient)
            self._log(
                "emergency_arrival" if emergency else "arrival",
                f"Patient {patient.patient_id} arrived ({kind})"
            )

            self.env.process(self.handle_patient(patient))

    def handle_patient(self, patient):
        cfg = self.config
        # FIFO: everyone has the same priority, so SimPy serves by arrival.
        queue_priority = 0 if cfg.policy == "fifo" else patient.priority
        remaining = patient.service_time

        # Loops more than once only if treatment is interrupted (preemptive).
        while remaining > 1e-9:
            request_args = {"priority": queue_priority}
            if cfg.policy == "preemptive":
                request_args["preempt"] = patient.patient_type == "Emergency"

            with self.queue.request(**request_args) as request:
                self.waiting.append(patient)
                self._record()

                if patient.patience is not None and patient.service_start is None:
                    time_left = patient.patience - (
                        self.env.now - patient.arrival_time
                    )
                    result = yield request | self.env.timeout(max(time_left, 0))

                    if request not in result:
                        # Waited too long: leave without being treated.
                        self.waiting.remove(patient)
                        patient.reneged = True
                        patient.leave_time = self.env.now
                        self.reneged += 1
                        self._log(
                            "renege",
                            f"Patient {patient.patient_id} left without "
                            f"treatment after waiting "
                            f"{self.env.now - patient.arrival_time:.1f} min"
                        )
                        self._record()
                        return
                else:
                    yield request

                self.waiting.remove(patient)

                # Find the available nurse.
                nurse = next(
                    n for n in self.nurses if not n.busy
                )

                if patient.service_start is None:
                    patient.service_start = self.env.now
                    self._log(
                        "start",
                        f"Patient {patient.patient_id} "
                        f"started with {nurse.name}"
                    )
                else:
                    self._log(
                        "start",
                        f"Patient {patient.patient_id} "
                        f"resumed with {nurse.name}"
                    )

                nurse.start(patient)
                self._record()
                started = self.env.now

                try:
                    yield self.env.timeout(remaining)
                    remaining = 0.0
                    interrupted = False
                    nurse.stop(finished=True)
                except simpy.Interrupt:
                    remaining -= self.env.now - started
                    patient.preemptions += 1
                    interrupted = True
                    nurse.stop(finished=False)
                    self._log(
                        "preempt",
                        f"Patient {patient.patient_id} interrupted by an "
                        f"emergency ({remaining:.1f} min left)"
                    )
                self.treatments.append({
                    "nurse": nurse.name,
                    "patient_id": patient.patient_id,
                    "type": patient.patient_type,
                    "start": started,
                    "end": self.env.now,
                    "interrupted": interrupted,
                })
                self._record()

        patient.completion_time = self.env.now
        self.completed += 1

        self._log(
            "complete",
            f"Patient {patient.patient_id} completed"
        )

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def run(self):
        """Run the whole simulation at once."""
        self.env.run()

    def is_finished(self):
        return self.env.peek() == math.inf

    def step(self, minutes):
        """Advance the simulation by up to `minutes` simulated minutes.

        The clock never moves past the final event, so stepping gives
        exactly the same results as run().
        """
        if self.is_finished():
            return False
        target = self.env.now + minutes
        while self.env.peek() <= target:
            self.env.step()
        if not self.is_finished() and self.env.now < target:
            # No events before target: just move the clock forward.
            self.env.run(until=target)
        return not self.is_finished()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def snapshot(self):
        """Current state of the clinic, for the live dashboard."""
        now = self.env.now
        started = [p for p in self.patients if p.service_start is not None]
        avg_wait = (
            sum(p.waiting_time for p in started) / len(started)
            if started else 0.0
        )
        return {
            "now": now,
            "clock": clock_text(now, self.config.shift_start_hour),
            "finished": self.is_finished(),
            "overtime": now > self.config.duration,
            "arrivals": self.arrivals,
            "completed": self.completed,
            "reneged": self.reneged,
            "queue_length": len(self.waiting),
            "in_service": sum(1 for n in self.nurses if n.busy),
            "average_wait": avg_wait,
            "waiting": [
                {
                    "id": p.patient_id,
                    "type": p.patient_type,
                    "waited": now - p.arrival_time,
                    "resumed": p.service_start is not None,
                }
                for p in self.waiting
            ],
            "nurses": [
                {
                    "name": n.name,
                    "busy": n.busy,
                    "patient_id": (
                        n.current_patient.patient_id
                        if n.current_patient else None
                    ),
                    "patient_type": (
                        n.current_patient.patient_type
                        if n.current_patient else None
                    ),
                    "served": n.patients_served,
                    "utilization": (
                        n.busy_time_so_far() / now * 100 if now > 0 else 0.0
                    ),
                }
                for n in self.nurses
            ],
        }

    def summary(self):
        finished = [
            p for p in self.patients
            if p.completion_time is not None
        ]

        waits = [p.waiting_time for p in finished]
        times = [p.time_in_system for p in finished]

        emergencies = [p for p in finished if p.patient_type == "Emergency"]
        generals = [p for p in finished if p.patient_type == "General"]
        within_target = (
            sum(1 for p in emergencies
                if p.waiting_time <= self.config.emergency_target)
            / len(emergencies) * 100
            if emergencies else None
        )
        shift_utils = [n.shift_utilization() for n in self.nurses]

        return {
            "arrivals": self.arrivals,
            "completed": self.completed,
            "reneged": self.reneged,
            "average_wait": (
                sum(waits) / len(waits) if waits else 0
            ),
            "average_system_time": (
                sum(times) / len(times) if times else 0
            ),
            "by_type": {
                "Emergency": _group_stats(emergencies),
                "General": _group_stats(generals),
            },
            "emergency_within_target_pct": within_target,
            "max_queue": self.max_queue,
            "preemptions": sum(p.preemptions for p in self.patients),
            "end_time": self.env.now,
            "overtime": max(0.0, self.env.now - self.config.duration),
            # Busy share of the whole run (shift + overtime).
            "nurse_utilization": {
                nurse.name: nurse.utilization(self.env.now)
                for nurse in self.nurses
            },
            # Busy share of the scheduled shift only.
            "nurse_shift_utilization": {
                nurse.name: nurse.shift_utilization()
                for nurse in self.nurses
            },
            "average_shift_utilization": (
                sum(shift_utils) / len(shift_utils) if shift_utils else 0.0
            ),
        }
