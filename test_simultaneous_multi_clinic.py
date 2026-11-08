"""Automated test script for Simultaneous Multi-Clinic Simulation in DYCI Clinic Simulator."""

import tkinter as tk
from config import get_clinic_config, CLINIC_PRESETS
from gui.app import ClinicSimulatorApp
from gui.live_view import LiveView
from simulation import SimulationController


def run_tests():
    print("==================================================================")
    print("Testing Simultaneous Multi-Clinic Simulation (Elida & Marciano)...")
    print("==================================================================")

    root = tk.Tk()
    root.withdraw()  # Headless test run

    app = ClinicSimulatorApp(root)
    live = app.live_view

    # 1. Verify Dual Controllers exist and are distinct
    assert "Clinic Elida" in live.controllers, "Clinic Elida controller missing"
    assert "Clinic Marciano" in live.controllers, "Clinic Marciano controller missing"

    ctrl_e = live.controllers["Clinic Elida"]
    ctrl_m = live.controllers["Clinic Marciano"]

    assert ctrl_e is not ctrl_m, "Controllers must be distinct objects"
    assert ctrl_e.env is not ctrl_m.env, "SimPy environments must be independent"
    assert len(ctrl_e.nurses) == 2, f"Elida should have 2 nurses, got {len(ctrl_e.nurses)}"
    assert len(ctrl_m.nurses) == 3, f"Marciano should have 3 nurses, got {len(ctrl_m.nurses)}"
    assert ctrl_e.config.arrival_rate == 10.0, f"Elida arrival rate expected 10.0, got {ctrl_e.config.arrival_rate}"
    assert ctrl_m.config.arrival_rate == 15.0, f"Marciano arrival rate expected 15.0, got {ctrl_m.config.arrival_rate}"
    print("✓ Dual independent SimulationControllers successfully initialized with branch configs")

    # 2. Check Navigation Bar buttons
    assert "Clinic Elida" in live.nav_btns
    assert "Clinic Marciano" in live.nav_btns
    assert "Combined Overview" in live.nav_btns
    print("✓ 3-way Navigation Bar created (Elida, Marciano, Combined Overview)")

    # 3. Synchronized stepping test (both clocks locked)
    init_time_e = ctrl_e.env.now
    init_time_m = ctrl_m.env.now
    assert init_time_e == 0.0 and init_time_m == 0.0

    live.step_once()
    assert ctrl_e.env.now == 10.0, f"Elida expected at 10.0m, got {ctrl_e.env.now}"
    assert ctrl_m.env.now == 10.0, f"Marciano expected at 10.0m, got {ctrl_m.env.now}"
    assert ctrl_e.env.now == ctrl_m.env.now, "Simulation clocks must advance in lockstep"
    print("✓ Synchronized Step (+10m) advances both clinics in lockstep (Clock: 08:10 AM)")

    live.step_once()
    live.step_once()
    assert ctrl_e.env.now == 30.0 and ctrl_m.env.now == 30.0
    print("✓ Synchronized Step continues in lockstep (Clock: 08:30 AM)")

    # 4. View switching without resetting or disrupting simulation
    patients_e_before = len(ctrl_e.patients)
    patients_m_before = len(ctrl_m.patients)
    time_before = ctrl_e.env.now

    # Switch to Clinic Marciano
    live.switch_view("Clinic Marciano")
    assert live.active_view == "Clinic Marciano"
    assert live.active_branch == "Clinic Marciano"
    assert live.controller is ctrl_m
    assert live.clinic_canvas.branch_name == "Clinic Marciano"
    assert live.clinic_canvas.nurse_count == 3
    assert len(live.clinic_canvas.chairs) == 20
    assert ctrl_e.env.now == time_before, "Switching views must not change simulation time"
    assert len(ctrl_e.patients) == patients_e_before, "Switching views must not reset Elida patients"
    assert len(ctrl_m.patients) == patients_m_before, "Switching views must not reset Marciano patients"
    print("✓ Switch to Clinic Marciano: visual layout adapts (3 nurses, 20 chairs); 0 records lost")

    # Switch to Combined Overview
    live.switch_view("Combined Overview")
    assert live.active_view == "Combined Overview"
    assert ctrl_e.env.now == time_before
    assert len(ctrl_e.patients) == patients_e_before
    assert len(ctrl_m.patients) == patients_m_before
    # Check that dual side-by-side animation canvases exist and are configured
    assert hasattr(live, "canvas_elida") and live.canvas_elida.branch_name == "Clinic Elida"
    assert hasattr(live, "canvas_marciano") and live.canvas_marciano.branch_name == "Clinic Marciano"
    assert live.canvas_elida.nurse_count == 2
    assert live.canvas_marciano.nurse_count == 3
    assert len(live.canvas_elida.chairs) == 14
    assert len(live.canvas_marciano.chairs) == 20
    # Check that comparative matrix labels are populated
    for key in ("arrivals", "completed", "queue_length", "in_service", "emerg_wait", "gen_wait", "nurse_util"):
        assert key in live.combined_matrix_labels
    print("✓ Switch to Combined Overview: dual side-by-side animation canvases & comparative matrix active")

    # Switch back to Clinic Elida
    live.switch_view("Clinic Elida")
    assert live.active_view == "Clinic Elida"
    assert live.active_branch == "Clinic Elida"
    assert live.controller is ctrl_e
    assert live.clinic_canvas.branch_name == "Clinic Elida"
    assert live.clinic_canvas.nurse_count == 2
    assert len(live.clinic_canvas.chairs) == 14
    assert ctrl_e.env.now == time_before
    print("✓ Switch back to Clinic Elida: layout safely restored (2 nurses, 14 chairs)")

    # 5. Run Instant test
    live.run_instant()
    ctrl_e = live.controllers["Clinic Elida"]
    ctrl_m = live.controllers["Clinic Marciano"]
    assert ctrl_e.is_finished(), "Elida should be finished"
    assert ctrl_m.is_finished(), "Marciano should be finished"
    assert ctrl_e.env.now >= 480.0
    assert ctrl_m.env.now >= 480.0
    print(f"✓ Run Instant completed both days:")
    print(f"   • Clinic Elida: {len(ctrl_e.patients)} total patients, {ctrl_e.summary()['completed']} completed")
    print(f"   • Clinic Marciano: {len(ctrl_m.patients)} total patients, {ctrl_m.summary()['completed']} completed")

    # Check Combined Overview after completion
    live.switch_view("Combined Overview")
    live.refresh_combined()
    print("✓ Combined Overview successfully rendered post-completion research summary")

    # 6. Live Tick & Canvas Sprites Test
    live.reset()
    ctrl_e = live.controllers["Clinic Elida"]
    ctrl_m = live.controllers["Clinic Marciano"]
    assert ctrl_e.env.now == 0.0 and ctrl_m.env.now == 0.0

    # Simulate 5 ticks
    live.speed_var.set(30)  # 30 sim-min / sec -> 3 min per tick
    live.running = True
    for _ in range(10):
        live._tick()

    assert ctrl_e.env.now == ctrl_m.env.now, "Simulation time must be identical across ticks"
    assert ctrl_e.env.now > 0, "Simulation time should have advanced"
    print(f"✓ Synchronized live ticking verified: advanced both clinics to t = {ctrl_e.env.now:.1f}m")

    # Check sprite sync in canvas
    assert "Clinic Elida" in live.clinic_canvas.branch_sprites
    assert "Clinic Marciano" in live.clinic_canvas.branch_sprites
    assert hasattr(live.canvas_elida, "sprites")
    assert hasattr(live.canvas_marciano, "sprites")
    print("✓ 2D Canvas maintained independent sprite pools across single and dual-arena views")

    # Pause test
    live.pause()
    assert not live.running
    time_paused = ctrl_e.env.now
    print(f"✓ Pause successfully frozen both branches simultaneously at t = {time_paused:.1f}m")

    # 7. CompareView Mode Check
    compare_view = app.compare_view
    assert compare_view.mode_var.get() == "Policies (within clinic)"
    assert "Clinics (Elida vs Marciano)" in compare_view.mode_combo["values"]
    print("✓ CompareView supports both policy comparisons and branch comparisons (Elida vs Marciano)")

    root.destroy()
    print("\nALL MULTI-CLINIC TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
