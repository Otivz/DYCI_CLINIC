
from simulation import SimulationController

simulation = SimulationController()

print("Starting DYCI Clinic Simulation...")

simulation.run()

print("\nSIMULATION RESULTS")
print("-" * 40)

results = simulation.summary()

print("Total Arrivals:", results["arrivals"])
print("Completed:", results["completed"])

print(
    "Average Waiting Time:",
    round(results["average_wait"], 2),
    "minutes"
)

print(
    "Average Time in System:",
    round(results["average_system_time"], 2),
    "minutes"
)

print("\nNurse Utilization:")

for nurse, utilization in results["nurse_utilization"].items():
    print(f"{nurse}: {utilization:.2f}%")

print("\nRecent Events:")

for event in simulation.events[-10:]:
    print(event)
