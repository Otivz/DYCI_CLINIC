"""Engine checks. Run with:  python tests/test_engine.py   (or pytest)."""

import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SimulationConfig  # noqa: E402
from experiments import run_replications  # noqa: E402
from simulation import SimulationController  # noqa: E402


def _run(config):
    controller = SimulationController(config)
    controller.run()
    return controller


def test_baseline_unchanged():
    """Refactor must reproduce the original seed-42 results."""
    s = _run(SimulationConfig()).summary()
    assert s["arrivals"] == 80
    assert s["completed"] == 80
    assert round(s["average_wait"], 2) == 14.25
    assert round(s["average_system_time"], 2) == 24.51


def test_live_stepping_matches_instant_run():
    for policy in ("priority", "fifo", "preemptive"):
        cfg = SimulationConfig(policy=policy, reneging=True, use_peak_hours=True)
        instant = _run(cfg)

        live = SimulationController(cfg)
        while live.step(7.3):
            pass

        assert live.env.now == instant.env.now, policy
        assert live.summary() == instant.summary(), policy


def test_priority_reduces_emergency_wait():
    stats = run_replications(SimulationConfig(), n=30)["stats"]
    emergency, _, _ = stats["emergency_wait"]
    general, _, _ = stats["general_wait"]
    assert emergency < general


def test_fifo_treats_classes_alike():
    """Under FIFO the class gap should be much smaller than under priority."""
    fifo = run_replications(SimulationConfig(policy="fifo"), n=30)["stats"]
    prio = run_replications(SimulationConfig(policy="priority"), n=30)["stats"]
    fifo_gap = abs(fifo["general_wait"][0] - fifo["emergency_wait"][0])
    prio_gap = prio["general_wait"][0] - prio["emergency_wait"][0]
    assert fifo_gap < prio_gap


def test_same_patients_across_policies():
    """Common random numbers: every policy sees identical arrivals."""
    runs = [_run(SimulationConfig(policy=p)) for p in ("fifo", "priority", "preemptive")]
    first = [(p.arrival_time, p.patient_type, p.service_time) for p in runs[0].patients]
    for other in runs[1:]:
        assert first == [
            (p.arrival_time, p.patient_type, p.service_time) for p in other.patients
        ]


def test_reneging_and_conservation():
    cfg = SimulationConfig(arrival_rate=20, reneging=True, general_patience=5)
    c = _run(cfg)
    s = c.summary()
    assert s["reneged"] > 0
    assert s["arrivals"] == s["completed"] + s["reneged"]
    assert all(p.patient_type == "General" for p in c.patients if p.reneged)


def test_conservation_all_policies():
    for policy in ("priority", "fifo", "preemptive"):
        for seed in range(10):
            cfg = SimulationConfig(policy=policy, random_seed=seed,
                                   reneging=True, use_peak_hours=True)
            s = _run(cfg).summary()
            assert s["arrivals"] == s["completed"] + s["reneged"], (policy, seed)


def test_preemption_happens_and_completes_service():
    total_preemptions = 0
    for seed in range(20):
        c = _run(SimulationConfig(policy="preemptive", arrival_rate=16, random_seed=seed))
        total_preemptions += c.summary()["preemptions"]
        for p in c.patients:
            if p.preemptions:
                assert p.patient_type == "General"
            # Time in system covers waiting + full service time.
            assert p.time_in_system >= p.service_time - 1e-6
    assert total_preemptions > 0


def test_peak_hours_shape_arrivals():
    cfg = SimulationConfig(use_peak_hours=True)
    first_hour = lunch_hour = 0
    for seed in range(20):
        c = _run(replace(cfg, random_seed=seed))
        first_hour += sum(1 for p in c.patients if p.arrival_time < 60)
        lunch_hour += sum(1 for p in c.patients if 180 <= p.arrival_time < 240)
    # Profile: hour 0 = 0.6x, hour 3 = 1.8x
    assert lunch_hour > 2 * first_hour


def test_any_number_of_nurses():
    s = _run(SimulationConfig(nurses=3)).summary()
    assert list(s["nurse_utilization"]) == ["Nurse A", "Nurse B", "Nurse C"]


def test_validation():
    assert SimulationConfig().validate() == []
    assert SimulationConfig(nurses=0, emergency_probability=2).validate()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, func in tests:
        try:
            func()
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

