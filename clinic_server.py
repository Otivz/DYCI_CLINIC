
import simpy


class ClinicServer:
    def __init__(self, env, name):
        self.env = env
        self.name = name
        self.resource = simpy.Resource(env, capacity=1)
        self.busy = False
        self.current_patient = None
        self.busy_time = 0.0

    def serve(self, patient):
        self.busy = True
        self.current_patient = patient.patient_id

        patient.assigned_nurse = self.name
        patient.service_start = self.env.now

        yield self.env.timeout(patient.service_time)

        self.busy_time += patient.service_time
        patient.completion_time = self.env.now

        self.busy = False
        self.current_patient = None

    def utilization(self, total_time):
        if total_time <= 0:
            return 0.0

        return (self.busy_time / total_time) * 100
