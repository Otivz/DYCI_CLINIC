
class ClinicServer:
    """A nurse. Tracks who is being treated and how long the nurse was busy.

    The simulation controller decides when treatment starts and stops
    (so treatment can be interrupted under the preemptive policy).
    """

    def __init__(self, env, name, shift_end):
        self.env = env
        self.name = name
        self.shift_end = shift_end      # Minutes; time after this is overtime

        self.busy = False
        self.current_patient = None     # Patient object being treated
        self.busy_time = 0.0            # Total busy minutes (incl. overtime)
        self.shift_busy_time = 0.0      # Busy minutes within the shift only
        self.patients_served = 0
        self.started_at = None          # Start of the treatment in progress

    def start(self, patient):
        self.busy = True
        self.current_patient = patient
        self.started_at = self.env.now
        patient.assigned_nurse = self.name

    def stop(self, finished):
        """End the current treatment block (finished or interrupted)."""
        start, now = self.started_at, self.env.now
        self.busy_time += now - start
        self.shift_busy_time += max(
            0.0, min(now, self.shift_end) - min(start, self.shift_end)
        )
        if finished:
            self.patients_served += 1

        self.busy = False
        self.current_patient = None
        self.started_at = None

    def busy_time_so_far(self):
        """Busy time including the treatment currently in progress."""
        extra = self.env.now - self.started_at if self.busy else 0.0
        return self.busy_time + extra

    def utilization(self, total_time):
        if total_time <= 0:
            return 0.0

        return (self.busy_time / total_time) * 100

    def shift_utilization(self):
        """Busy share of the scheduled shift (excludes overtime)."""
        if self.shift_end <= 0:
            return 0.0
        return (self.shift_busy_time / self.shift_end) * 100
