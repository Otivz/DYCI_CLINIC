"""2D Animated Clinic Floorplan for DYCI Clinic Simulator.

Displays an interactive, real-time animated clinic environment supporting:
- Clinic Elida (2 nurses, 14 chairs)
- Clinic Marciano (3 nurses, 20 chairs)
- Custom / Default DYCI (dynamic)

Includes:
- Clinic entrance (left)
- Triage / Reception check-in desk
- Adaptive waiting room chairs
- Nurse consultation workstations
- Clinic exit (right)
- Moving patient avatars driven strictly by SimPy simulation events.
"""

import math
import tkinter as tk
from tkinter import ttk

# Palette
COLOR_BG = "#f8fafc"
COLOR_FLOOR = "#ffffff"
COLOR_WALL = "#cbd5e1"
COLOR_DOOR = "#64748b"
COLOR_CHAIR = "#e2e8f0"
COLOR_CHAIR_BORDER = "#94a3b8"
COLOR_DESK = "#e2e8f0"
COLOR_DESK_BORDER = "#475569"
COLOR_NURSE = "#059669"
COLOR_NURSE_BORDER = "#047857"

COLOR_PATIENT_GENERAL = "#2563eb"    # Blue
COLOR_PATIENT_EMERGENCY = "#dc2626"  # Red
COLOR_PATIENT_DONE = "#10b981"       # Green
COLOR_PATIENT_RENEGE = "#d97706"     # Amber


class PatientSprite:
    """Represents a visual patient moving through the clinic."""

    def __init__(self, patient_id, patient_type, start_x, start_y):
        self.patient_id = patient_id
        self.patient_type = patient_type
        self.x = float(start_x)
        self.y = float(start_y)
        self.target_x = float(start_x)
        self.target_y = float(start_y)
        self.waypoints = []
        self.color = (
            COLOR_PATIENT_EMERGENCY if patient_type == "Emergency"
            else COLOR_PATIENT_GENERAL
        )
        self.state = "ENTERING"  # ENTERING, WAITING, WALKING_TO_DESK, IN_SERVICE, EXITING, GONE
        self.chair_idx = None
        self.nurse_idx = None
        self.speed = 5.0
        self.radius = 11
        self.pending_complete = False
        self.service_hold_ticks = 0

    def set_target(self, tx, ty, speed=4.0, clear_waypoints=True):
        if self.state == "EXITING":
            # Exiting patients must never be re-targeted backwards towards the entry
            if float(tx) < self.x:
                return
        self.target_x = float(tx)
        self.target_y = float(ty)
        self.speed = speed
        if clear_waypoints:
            self.waypoints.clear()

    def add_waypoint(self, wx, wy, speed=4.0):
        if self.state == "EXITING":
            return  # Exiting patients never accept intermediate waypoints
        self.waypoints.append((float(wx), float(wy), speed))

    def step(self):
        """Move one step toward the target. Follow waypoints sequentially."""
        if self.state == "EXITING":
            self.waypoints.clear()
            if self.target_x < self.x:
                self.target_x = self.x + 30.0

        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist <= self.speed or dist < 1.0:
            self.x = self.target_x
            self.y = self.target_y
            if self.state == "EXITING":
                self.waypoints.clear()
                return True
            if self.waypoints:
                next_x, next_y, next_spd = self.waypoints.pop(0)
                self.set_target(next_x, next_y, next_spd, clear_waypoints=False)
                return False
            return True

        step_x = (dx / dist) * self.speed
        step_y = (dy / dist) * self.speed
        if self.state == "EXITING":
            # Strict unidirectionality: exiting patient can never move west/leftwards
            step_x = max(0.0, step_x)

        self.x += step_x
        self.y += step_y
        return False


class ClinicCanvas(ttk.Frame):
    """Tkinter Canvas-based clinic environment supporting multiple simultaneous branches."""

    def __init__(self, parent, height=170):
        super().__init__(parent)
        self.canvas_height = height
        self.branch_name = "Clinic Elida"
        self.nurse_count = 2

        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=COLOR_BG,
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            relief=tk.FLAT
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        # Independent sprite pools and floorplans per clinic
        self.branch_sprites = {
            "Clinic Elida": {},
            "Clinic Marciano": {},
            "Custom / Default DYCI": {}
        }
        self.branch_chairs = {
            "Clinic Elida": [],
            "Clinic Marciano": [],
            "Custom / Default DYCI": []
        }
        self.branch_desks = {
            "Clinic Elida": [],
            "Clinic Marciano": [],
            "Custom / Default DYCI": []
        }

        self.entrance_pos = (36, height // 2)
        self.triage_pos = (92, height // 2)
        self.exit_pos = (600, height // 2)
        self.anim_running = True
        self._anim_job = None

        self._init_all_branches(700, height)
        self._animate()

    @property
    def sprites(self):
        return self.branch_sprites.setdefault(self.branch_name, {})

    @property
    def chairs(self):
        return self.branch_chairs.setdefault(self.branch_name, [])

    @property
    def desks(self):
        return self.branch_desks.setdefault(self.branch_name, [])

    def set_branch(self, branch_name):
        """Switch displayed branch location without resetting or disrupting simulation."""
        if branch_name not in self.branch_sprites:
            self.branch_sprites[branch_name] = {}
        self.branch_name = branch_name
        if "Marciano" in branch_name:
            self.nurse_count = 3
        elif "Elida" in branch_name:
            self.nurse_count = 2
        w = max(self.canvas.winfo_width(), 700)
        self._init_layout_for_branch(branch_name, w, self.canvas_height)
        self.redraw()

    def set_nurse_count(self, count):
        """Update active nurse desks for the current branch."""
        count = max(1, min(count, 12))
        self.nurse_count = count
        w = max(self.canvas.winfo_width(), 700)
        self._init_layout_for_branch(self.branch_name, w, self.canvas_height)
        self.redraw()

    def _init_all_branches(self, width, height):
        for b in ("Clinic Elida", "Clinic Marciano", "Custom / Default DYCI"):
            self._init_layout_for_branch(b, width, height)

    def _init_layout_for_branch(self, branch, width, height):
        self.canvas_height = height
        mid_y = height // 2 + 5
        is_narrow = width < 680

        ex_pad = 24 if is_narrow else 36
        self.entrance_pos = (ex_pad, mid_y)
        self.triage_pos = (ex_pad + (46 if is_narrow else 60), mid_y)
        self.exit_pos = (width - ex_pad, mid_y)

        # Branch-specific capacity and adaptive layout
        if "Marciano" in branch:
            n_nurses = getattr(self, "nurse_count", 3)
            if is_narrow:
                chair_rows, chair_cols = 4, 5  # 20 chairs in 4x5 compact grid
            else:
                chair_rows, chair_cols = 2, 10 # 20 chairs in 2x10 grid
        elif "Elida" in branch:
            n_nurses = getattr(self, "nurse_count", 2)
            chair_rows, chair_cols = 2, 7  # 14 chairs in 2x7 grid
        else:
            n_nurses = max(getattr(self, "nurse_count", 2), 1)
            chair_rows, chair_cols = 2, 8

        # Existing patient mappings preserved
        old_chairs = self.branch_chairs.get(branch, [])
        occupied = {i: c.get("patient_id") for i, c in enumerate(old_chairs) if c.get("patient_id")}

        chairs = []
        spacing_x = 19 if is_narrow else 24
        spacing_y = 17 if (is_narrow and chair_rows > 2) else 26
        waiting_start_x = self.triage_pos[0] + (34 if is_narrow else 50)
        start_y = mid_y - ((chair_rows - 1) * spacing_y) // 2

        idx = 0
        for r in range(chair_rows):
            for c in range(chair_cols):
                cx = waiting_start_x + c * spacing_x
                cy = start_y + r * spacing_y
                chairs.append({
                    "x": cx,
                    "y": cy,
                    "patient_id": occupied.get(idx)
                })
                idx += 1
        self.branch_chairs[branch] = chairs

        # Desks layout calculation (Adaptive 2-Tier Clinical Pods)
        desks = []
        waiting_end_x = waiting_start_x + (chair_cols - 1) * spacing_x
        desk_area_start = waiting_end_x + (26 if is_narrow else 40)
        desk_area_width = self.exit_pos[0] - desk_area_start - (20 if is_narrow else 32)
        n = max(n_nurses, 1)

        # Decide whether to use 2-tier clinical pods:
        # Activated when n >= 4, or when desks would be cramped in 1 row (< 56px per desk)
        use_two_tier = (n >= 4) or (desk_area_width / n < 56 and n > 2)

        if not use_two_tier:
            # Single-tier linear suites (1 to 3 nurses)
            step = max(desk_area_width / n, 50 if is_narrow else 70)
            booth_hw = 24 if is_narrow else 32
            booth_hh = 36 if is_narrow else 38
            for i in range(n):
                dx = desk_area_start + i * step + (step / 2)
                dy = mid_y
                nurse_y = dy - (13 if is_narrow else 14)
                patient_y = dy + (17 if is_narrow else 18)
                desks.append({
                    "desk_x": dx,
                    "desk_y": dy,
                    "nurse_x": dx,
                    "nurse_y": nurse_y,
                    "patient_x": dx,
                    "patient_y": patient_y,
                    "name": f"Nurse {chr(65 + i)}",
                    "busy": False,
                    "patient_id": None,
                    "patient_type": None,
                    "patient_at_desk": False,
                    "tier": "single",
                    "booth_hw": booth_hw,
                    "booth_hh": booth_hh
                })
        else:
            # 2-Tier Adaptive Clinical Pods (4+ nurses or narrow clinic bay)
            # Upper Bay (Row 0) and Lower Bay (Row 1) facing a central corridor
            n_cols = (n + 1) // 2
            step = max(desk_area_width / n_cols, 44 if is_narrow else 60)
            tier_offset_y = 25 if is_narrow else 33
            booth_hw = min(int(step / 2) - 3, 22 if is_narrow else 28)
            booth_hh = 21 if is_narrow else 27

            for i in range(n):
                col_idx = i % n_cols
                row_idx = i // n_cols  # 0 = upper tier, 1 = lower tier
                dx = desk_area_start + col_idx * step + (step / 2)
                if row_idx == 0:
                    dy = mid_y - tier_offset_y
                    nurse_y = dy - (9 if is_narrow else 11)
                    patient_y = dy + (10 if is_narrow else 12)
                    tier = "upper"
                else:
                    dy = mid_y + tier_offset_y
                    nurse_y = dy + (9 if is_narrow else 11)
                    patient_y = dy - (10 if is_narrow else 12)
                    tier = "lower"

                desks.append({
                    "desk_x": dx,
                    "desk_y": dy,
                    "nurse_x": dx,
                    "nurse_y": nurse_y,
                    "patient_x": dx,
                    "patient_y": patient_y,
                    "name": f"Nurse {chr(65 + i)}",
                    "busy": False,
                    "patient_id": None,
                    "patient_type": None,
                    "patient_at_desk": False,
                    "tier": tier,
                    "booth_hw": booth_hw,
                    "booth_hh": booth_hh
                })
        self.branch_desks[branch] = desks

        # Synchronize all active patient sprites with the new floorplan coordinates
        sprites = self.branch_sprites.get(branch, {})
        for pid, sp in sprites.items():
            if sp.state in ("WAITING", "ENTERING"):
                if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                    ch = chairs[sp.chair_idx]
                    ch["patient_id"] = pid
                    if sp.state == "WAITING":
                        sp.x = float(ch["x"])
                        sp.y = float(ch["y"])
                        sp.set_target(sp.x, sp.y, clear_waypoints=True)
                    elif sp.state == "ENTERING":
                        sp.waypoints = [(float(ch["x"]), float(ch["y"]), sp.speed)]
                else:
                    # Chair index invalid or out of range: reassign to an available chair
                    assigned = False
                    for ci, ch in enumerate(chairs):
                        if ch["patient_id"] is None:
                            sp.chair_idx = ci
                            ch["patient_id"] = pid
                            if sp.state == "WAITING":
                                sp.x = float(ch["x"])
                                sp.y = float(ch["y"])
                                sp.set_target(sp.x, sp.y, clear_waypoints=True)
                            elif sp.state == "ENTERING":
                                sp.waypoints = [(float(ch["x"]), float(ch["y"]), sp.speed)]
                            assigned = True
                            break
                    if not assigned:
                        sp.chair_idx = None

            elif sp.state in ("IN_SERVICE", "WALKING_TO_DESK"):
                if sp.nurse_idx is not None and sp.nurse_idx < len(desks):
                    d = desks[sp.nurse_idx]
                    if sp.state == "IN_SERVICE":
                        sp.x = float(d["patient_x"])
                        sp.y = float(d["patient_y"])
                        sp.set_target(sp.x, sp.y, clear_waypoints=True)
                    elif sp.state == "WALKING_TO_DESK":
                        sp.set_target(d["patient_x"], d["patient_y"], speed=sp.speed, clear_waypoints=True)

            elif sp.state == "EXITING":
                exit_target_x = max(self.exit_pos[0] + 15, sp.x + 25)
                sp.set_target(exit_target_x, self.exit_pos[1], speed=sp.speed, clear_waypoints=True)

    def _on_resize(self, event):
        if event.width > 100:
            self._init_all_branches(event.width, event.height)
            self.redraw()

    def reset(self):
        """Clear all active patient sprites and reset clinic floorplans for all branches."""
        for b in self.branch_sprites:
            self.branch_sprites[b].clear()
        for b in self.branch_chairs:
            for c in self.branch_chairs[b]:
                c["patient_id"] = None
        for b in self.branch_desks:
            for d in self.branch_desks[b]:
                d["busy"] = False
                d["patient_id"] = None
                d["patient_type"] = None
        self.redraw()

    def sync(self, snapshot, new_events=None, branch="Clinic Elida"):
        """Synchronize animation state for the designated branch."""
        if branch not in self.branch_sprites:
            self.branch_sprites[branch] = {}
        if branch not in self.branch_desks or not self.branch_desks[branch]:
            self._init_layout_for_branch(branch, max(self.canvas.winfo_width(), 700), self.canvas_height)

        desks = self.branch_desks[branch]
        chairs = self.branch_chairs[branch]
        sprites = self.branch_sprites[branch]

        # 1. Update nurse desks from snapshot
        nurses_snap = snapshot.get("nurses", [])
        for i, n_info in enumerate(nurses_snap):
            if i < len(desks):
                d = desks[i]
                d["busy"] = n_info.get("busy", False)
                d["patient_id"] = n_info.get("patient_id")
                d["patient_type"] = n_info.get("patient_type")

        # 2. Process events
        if new_events:
            for _time, kind, msg in new_events:
                self._handle_event_for_branch(kind, msg, branch)

        # 3. Reconcile with waiting room in snapshot
        waiting_ids = {w["id"]: w["type"] for w in snapshot.get("waiting", [])}
        busy_nurse_patients = {
            d["patient_id"]: (i, d["patient_type"])
            for i, d in enumerate(desks)
            if d["busy"] and d["patient_id"] is not None
        }

        for p_id, p_type in waiting_ids.items():
            if p_id not in sprites:
                sp = PatientSprite(p_id, p_type, self.entrance_pos[0], self.entrance_pos[1])
                sprites[p_id] = sp
                chair_idx = self._find_empty_chair(p_id, chairs)
                if chair_idx is not None:
                    sp.chair_idx = chair_idx
                    chairs[chair_idx]["patient_id"] = p_id
                    sp.set_target(self.triage_pos[0], self.triage_pos[1], speed=5.5)
                    sp.add_waypoint(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=5.0)
                    sp.state = "ENTERING"
                else:
                    sp.chair_idx = None
                    unseated = sum(1 for s in sprites.values() if s.state in ("WAITING", "ENTERING") and s.chair_idx is None)
                    ox, oy = self._get_overflow_pos(unseated, chairs)
                    sp.set_target(self.triage_pos[0], self.triage_pos[1], speed=5.5)
                    sp.add_waypoint(ox, oy, speed=5.0)
                    sp.state = "ENTERING"
            else:
                sp = sprites[p_id]
                if sp.state in ("EXITING", "GONE"):
                    continue
                if sp.chair_idx is None:
                    chair_idx = self._find_empty_chair(p_id, chairs)
                    if chair_idx is not None:
                        sp.chair_idx = chair_idx
                        chairs[chair_idx]["patient_id"] = p_id
                        sp.set_target(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=6.0, clear_waypoints=True)

        for p_id, (n_idx, p_type) in busy_nurse_patients.items():
            if p_id not in sprites:
                sp = PatientSprite(p_id, p_type, self.entrance_pos[0], self.entrance_pos[1])
                sprites[p_id] = sp
            sp = sprites[p_id]
            if sp.state in ("EXITING", "GONE"):
                continue
            if n_idx < len(desks):
                desk = desks[n_idx]
                if sp.state not in ("IN_SERVICE", "WALKING_TO_DESK"):
                    if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                        chairs[sp.chair_idx]["patient_id"] = None
                        sp.chair_idx = None
                    sp.nurse_idx = n_idx
                    sp.state = "WALKING_TO_DESK"
                    dist = math.hypot(desk["patient_x"] - sp.x, desk["patient_y"] - sp.y)
                    speed = max(7.5, min(16.0, dist / 28.0))
                    sp.set_target(desk["patient_x"], desk["patient_y"], speed=speed, clear_waypoints=True)

    def _handle_event_for_branch(self, kind, msg, branch):
        sprites = self.branch_sprites[branch]
        chairs = self.branch_chairs[branch]
        desks = self.branch_desks[branch]

        if kind in ("arrival", "emergency_arrival"):
            try:
                parts = msg.split()
                pid = int(parts[1])
                ptype = "Emergency" if "Emergency" in msg else "General"
                if pid not in sprites:
                    sp = PatientSprite(pid, ptype, self.entrance_pos[0], self.entrance_pos[1])
                    sprites[pid] = sp
                    chair_idx = self._find_empty_chair(pid, chairs)
                    if chair_idx is not None:
                        sp.chair_idx = chair_idx
                        chairs[chair_idx]["patient_id"] = pid
                        sp.set_target(self.triage_pos[0], self.triage_pos[1], speed=5.5)
                        sp.add_waypoint(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=5.0)
                        sp.state = "ENTERING"
                    else:
                        sp.chair_idx = None
                        unseated = sum(1 for s in sprites.values() if s.state in ("WAITING", "ENTERING") and s.chair_idx is None)
                        ox, oy = self._get_overflow_pos(unseated, chairs)
                        sp.set_target(self.triage_pos[0], self.triage_pos[1], speed=5.5)
                        sp.add_waypoint(ox, oy, speed=5.0)
                        sp.state = "ENTERING"
            except Exception:
                pass

        elif kind == "start":
            try:
                parts = msg.split()
                pid = int(parts[1])
                nurse_idx = 0
                for i_p, token in enumerate(parts):
                    if token == "Nurse" and i_p + 1 < len(parts):
                        letter = parts[i_p + 1].strip(".,:;!?")
                        if letter and 'A' <= letter[0].upper() <= 'Z':
                            nurse_idx = ord(letter[0].upper()) - ord('A')
                        break
                    elif token.startswith("Nurse") and len(token) > 5:
                        letter = token[5:].strip(".,:;!?")
                        if letter and 'A' <= letter[0].upper() <= 'Z':
                            nurse_idx = ord(letter[0].upper()) - ord('A')
                        break
                if 0 <= nurse_idx < len(desks):
                    desk = desks[nurse_idx]
                    if pid in sprites:
                        sp = sprites[pid]
                        if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                            chairs[sp.chair_idx]["patient_id"] = None
                            sp.chair_idx = None
                        sp.nurse_idx = nurse_idx
                        sp.state = "WALKING_TO_DESK"
                        dist = math.hypot(desk["patient_x"] - sp.x, desk["patient_y"] - sp.y)
                        speed = max(7.5, min(16.0, dist / 28.0))
                        sp.set_target(desk["patient_x"], desk["patient_y"], speed=speed, clear_waypoints=True)
            except Exception:
                pass

        elif kind == "complete":
            try:
                parts = msg.split()
                pid = int(parts[1])
                if pid in sprites:
                    sp = sprites[pid]
                    if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                        chairs[sp.chair_idx]["patient_id"] = None
                        sp.chair_idx = None

                    # If patient is ALREADY at the desk receiving service:
                    if sp.state == "IN_SERVICE":
                        sp.waypoints.clear()
                        sp.color = COLOR_PATIENT_DONE
                        sp.state = "EXITING"
                        if sp.nurse_idx is not None and sp.nurse_idx < len(desks):
                            desks[sp.nurse_idx]["patient_at_desk"] = False
                        exit_target_x = max(self.exit_pos[0] + 15, sp.x + 25)
                        sp.set_target(exit_target_x, self.exit_pos[1], speed=sp.speed, clear_waypoints=True)
                    else:
                        # Patient has not yet reached the nurse desk!
                        # Keep walking to the nurse; complete once physically arrived.
                        sp.pending_complete = True
            except Exception:
                pass

        elif kind == "renege":
            try:
                parts = msg.split()
                pid = int(parts[1])
                if pid in sprites:
                    sp = sprites[pid]
                    if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                        chairs[sp.chair_idx]["patient_id"] = None
                        sp.chair_idx = None
                    sp.waypoints.clear()
                    sp.color = COLOR_PATIENT_RENEGE
                    sp.state = "EXITING"
                    exit_target_x = max(self.exit_pos[0] + 15, sp.x + 25)
                    sp.set_target(exit_target_x, self.exit_pos[1], speed=5.5, clear_waypoints=True)
            except Exception:
                pass

        elif kind == "preempt":
            try:
                parts = msg.split()
                pid = int(parts[1])
                if pid in sprites:
                    sp = sprites[pid]
                    chair_idx = self._find_empty_chair(pid, chairs)
                    if chair_idx is not None:
                        sp.chair_idx = chair_idx
                        chairs[chair_idx]["patient_id"] = pid
                        sp.state = "ENTERING"
                        sp.set_target(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=5.0, clear_waypoints=True)
            except Exception:
                pass

    def _get_overflow_pos(self, overflow_idx, chairs):
        """Calculate designated overflow waiting positions within the waiting lounge."""
        if not chairs:
            return (self.triage_pos[0] + 30, self.triage_pos[1])
        max_cx = max(ch["x"] for ch in chairs)
        min_cy = min(ch["y"] for ch in chairs)
        max_cy = max(ch["y"] for ch in chairs)

        col = overflow_idx % 2
        row = overflow_idx // 2
        ox = max_cx + 16 + col * 15
        oy = min_cy + (row * 16)
        return (ox, min(oy, max_cy + 10))

    def _find_empty_chair(self, patient_id, chairs=None):
        chair_list = chairs if chairs is not None else self.chairs
        for i, c in enumerate(chair_list):
            if c["patient_id"] is None or c["patient_id"] == patient_id:
                return i
        return None

    def _animate(self):
        """Frame step loop: advances sprites for all branches seamlessly."""
        for branch, sp_dict in self.branch_sprites.items():
            to_delete = []
            desks = self.branch_desks.get(branch, [])
            chairs = self.branch_chairs.get(branch, [])
            for pid, sp in sp_dict.items():
                reached = sp.step()
                if reached:
                    if sp.state == "ENTERING":
                        sp.state = "WAITING"
                        if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                            ch = chairs[sp.chair_idx]
                            sp.x = float(ch["x"])
                            sp.y = float(ch["y"])
                    elif sp.state == "WALKING_TO_DESK":
                        sp.state = "IN_SERVICE"
                        if sp.nurse_idx is not None and sp.nurse_idx < len(desks):
                            desks[sp.nurse_idx]["patient_at_desk"] = True
                            d = desks[sp.nurse_idx]
                            sp.x = float(d["patient_x"])
                            sp.y = float(d["patient_y"])
                        if sp.pending_complete:
                            # Patient just reached the desk; hold briefly to visually observe treatment
                            sp.service_hold_ticks = 8
                    elif sp.state == "IN_SERVICE":
                        pass
                    elif sp.state == "EXITING":
                        sp.state = "GONE"
                        to_delete.append(pid)

                # Keep waiting patients centered in their chairs
                if sp.state == "WAITING":
                    if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                        ch = chairs[sp.chair_idx]
                        sp.x = float(ch["x"])
                        sp.y = float(ch["y"])
                        ch["patient_id"] = pid
                    else:
                        # Attempt to seat unassigned waiting patient in an empty chair
                        empty_idx = self._find_empty_chair(pid, chairs)
                        if empty_idx is not None:
                            sp.chair_idx = empty_idx
                            chairs[empty_idx]["patient_id"] = pid
                            ch = chairs[empty_idx]
                            sp.set_target(ch["x"], ch["y"], speed=5.5, clear_waypoints=True)

                # If seated at desk and pending completion, hold briefly then exit
                if sp.state == "IN_SERVICE" and sp.pending_complete:
                    if sp.service_hold_ticks > 0:
                        sp.service_hold_ticks -= 1
                    else:
                        sp.pending_complete = False
                        sp.color = COLOR_PATIENT_DONE
                        sp.state = "EXITING"
                        if sp.nurse_idx is not None and sp.nurse_idx < len(desks):
                            desks[sp.nurse_idx]["patient_at_desk"] = False
                        exit_target_x = max(self.exit_pos[0] + 15, sp.x + 25)
                        sp.set_target(exit_target_x, self.exit_pos[1], speed=sp.speed, clear_waypoints=True)

            for pid in to_delete:
                del sp_dict[pid]

        self.redraw()
        if self.anim_running:
            self._anim_job = self.after(35, self._animate)

    def _draw_nurse_avatar(self, c, nx, ny, is_busy=False, patient_type="General", is_triage=False):
        """Draw an unmistakable clinical practitioner seated in an ergonomic swivel office chair."""
        # 1. Swivel office chair backrest & armrests (dark slate)
        c.create_rectangle(nx - 13, ny - 13, nx + 13, ny - 7, fill="#334155", outline="#1e293b", width=1)
        c.create_rectangle(nx - 14, ny - 9, nx - 11, ny + 3, fill="#475569", outline="#1e293b", width=1)
        c.create_rectangle(nx + 11, ny - 9, nx + 14, ny + 3, fill="#475569", outline="#1e293b", width=1)

        # 2. Scrubs color determination
        if is_triage:
            scrub_fill = "#0284c7"
            scrub_bd = "#0369a1"
        elif is_busy and patient_type == "Emergency":
            scrub_fill = "#dc2626"
            scrub_bd = "#991b1b"
        elif is_busy:
            scrub_fill = "#2563eb"
            scrub_bd = "#1d4ed8"
        else:
            scrub_fill = "#059669"
            scrub_bd = "#047857"

        # 3. Medical scrubs tunic & shoulders (distinct polygon, NOT a circle)
        c.create_polygon([
            nx - 11, ny + 5,
            nx - 11, ny - 4,
            nx + 11, ny - 4,
            nx + 11, ny + 5,
            nx + 8, ny + 6,
            nx - 8, ny + 6
        ], fill=scrub_fill, outline=scrub_bd, width=1.5)

        # 4. White clinical nurse cap with red medical cross
        c.create_rectangle(nx - 7, ny - 11, nx + 7, ny - 3, fill="#ffffff", outline="#0f172a", width=1.2)
        c.create_text(nx, ny - 7, text="✚", font=("Segoe UI", 6, "bold"), fill="#dc2626")

    def redraw(self):
        """Draw the entire clinic environment, stations, and active sprites."""
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = self.canvas_height

        # 1. Floor background & boundary walls
        c.create_rectangle(8, 8, w - 8, h - 8, fill=COLOR_FLOOR, outline=COLOR_WALL, width=1.5)

        # Subtle floor grid
        for gy in range(35, h - 15, 30):
            c.create_line(12, gy, w - 12, gy, fill="#f1f5f9", width=1)

        is_narrow = w < 680

        # 2. Branch Banner & Identification (Top Header inside Canvas)
        if is_narrow:
            banner_text = f"📍 {self.branch_name.upper()}"
            capacity_text = f"{self.nurse_count} Nurses | {len(self.chairs)} Chairs"
        else:
            banner_text = f"📍 DYCI HEALTH SERVICES  •  {self.branch_name.upper()}"
            capacity_text = f"Staffing: {self.nurse_count} Nurses  |  Waiting: {len(self.chairs)} Chairs"

        c.create_rectangle(12, 10, w - 12, 28, fill="#f8fafc", outline="#e2e8f0", width=1)
        c.create_text(18, 19, text=banner_text, font=("Segoe UI", 8, "bold"), fill="#1a365d", anchor=tk.W)
        c.create_text(w - 18, 19, text=capacity_text, font=("Segoe UI", 7 if is_narrow else 8), fill="#64748b", anchor=tk.E)

        # 3. Entrance Door & Welcome Runner Mat (Left)
        ex, ey = self.entrance_pos
        # Welcome floor rug
        c.create_rectangle(ex - 12, ey - 28, ex + 22, ey + 28, fill="#eff6ff", outline="#bfdbfe", width=1)
        for rx in (ex - 4, ex + 4, ex + 12):
            c.create_line(rx, ey - 20, rx, ey + 20, fill="#dbeafe", width=1)
        # Metallic sill threshold and sliding entrance door
        c.create_rectangle(8, ey - 25, 22, ey + 25, fill="#f1f5f9", outline="#94a3b8", width=1)
        c.create_line(22, ey - 23, 22, ey + 23, fill="#2563eb", width=3.5)
        c.create_text(ex + 6, ey - 32, text="➡ ENTRY", font=("Segoe UI", 6 if is_narrow else 7, "bold"), fill="#2563eb")
        c.create_text(ex + 6, ey, text="🚪", font=("Segoe UI", 10 if is_narrow else 12))
        c.create_text(ex + 27, ey + 22, text="➔ ➔", font=("Segoe UI", 7, "bold"), fill="#93c5fd")

        # 4. Triage / Reception Check-in Station
        tx, ty = self.triage_pos
        # Triage consultation zone mat
        c.create_rectangle(tx - 22, ty - 28, tx + 22, ty + 28, fill="#f0f9ff", outline="#bae6fd", width=1.5)
        # Reception desk counter with glossy trim
        c.create_rectangle(tx - 16, ty - 6, tx + 16, ty + 6, fill="#ffffff", outline="#0284c7", width=1.5)
        c.create_line(tx - 16, ty - 6, tx + 16, ty - 6, fill="#0369a1", width=2.5)
        # Triage digital check-in terminal
        c.create_rectangle(tx - 6, ty - 3, tx + 6, ty + 3, fill="#cbd5e1", outline="#64748b")
        # Triage Nurse Practitioner Avatar (seated in swivel chair)
        self._draw_nurse_avatar(c, tx, ty - 14, is_triage=True)
        c.create_text(tx, ty - 29, text="TRIAGE", font=("Segoe UI", 6 if is_narrow else 7, "bold"), fill="#0369a1")
        c.create_text(tx, ty + 16, text="[CHECK-IN]", font=("Segoe UI", 6, "bold"), fill="#0284c7")

        # 5. Exit Door & Discharge Threshold Mat (Right)
        ox, oy = self.exit_pos
        # Soft emerald discharge carpet mat
        c.create_rectangle(ox - 24, oy - 28, ox + 10, oy + 28, fill="#ecfdf5", outline="#a7f3d0", width=1)
        c.create_line(ox - 16, oy - 20, ox - 16, oy + 20, fill="#d1fae5", width=1)
        c.create_line(ox - 8, oy - 20, ox - 8, oy + 20, fill="#d1fae5", width=1)
        # Exit threshold door frame
        c.create_rectangle(w - 22, oy - 25, w - 8, oy + 25, fill="#f1f5f9", outline="#94a3b8", width=1)
        c.create_line(w - 22, oy - 23, w - 22, oy + 23, fill="#10b981", width=3.5)
        c.create_text(ox - 6, oy - 32, text="EXIT ➡", font=("Segoe UI", 6 if is_narrow else 7, "bold"), fill="#059669")
        c.create_text(ox - 6, oy, text="🚪", font=("Segoe UI", 10 if is_narrow else 12))
        c.create_text(ox - 14, oy + 22, text="➔ ➔", font=("Segoe UI", 7, "bold"), fill="#10b981")

        # 6. Waiting Lounge Zone & Ergonomic Armchairs
        if self.chairs:
            min_cx = min(ch["x"] for ch in self.chairs)
            max_cx = max(ch["x"] for ch in self.chairs)
            min_cy = min(ch["y"] for ch in self.chairs)
            max_cy = max(ch["y"] for ch in self.chairs)

            # Lounge carpet flooring runner
            c.create_rectangle(
                min_cx - 10, min_cy - 8, max_cx + 10, max_cy + 9,
                fill="#f8fafc", outline="#e2e8f0", width=1
            )
            wl_label_y = min(min_cy - 12, 33) if is_narrow else (min_cy - 16)
            c.create_text(
                min_cx - 4, wl_label_y,
                text="🛋 WAITING" if is_narrow else "🛋 PATIENT WAITING LOUNGE",
                font=("Segoe UI", 6 if is_narrow else 7, "bold"),
                fill="#1e3a8a", anchor=tk.W
            )

            # Render each ergonomic armchair
            for chair in self.chairs:
                cx, cy = chair["x"], chair["y"]
                is_occ = chair.get("patient_id") is not None

                # Cushion seat
                cushion_bg = "#eff6ff" if is_occ else "#ffffff"
                cushion_bd = "#60a5fa" if is_occ else "#94a3b8"
                c.create_rectangle(cx - 6, cy - 4, cx + 6, cy + 6, fill=cushion_bg, outline=cushion_bd, width=1)
                # Curved cushioned backrest
                c.create_rectangle(cx - 6, cy - 8, cx + 6, cy - 4, fill="#cbd5e1", outline="#64748b", width=1)
                # Left and right padded armrests
                c.create_rectangle(cx - 8, cy - 6, cx - 6, cy + 5, fill="#e2e8f0", outline="#94a3b8", width=1)
                c.create_rectangle(cx + 6, cy - 6, cx + 8, cy + 5, fill="#e2e8f0", outline="#94a3b8", width=1)

        # 7. Nurse Consultation Workstations & Clinical Privacy Suites
        mid_y = self.entrance_pos[1]
        is_two_tier = any(d.get("tier") in ("upper", "lower") for d in self.desks)
        if is_two_tier and self.desks:
            # Subtle central corridor floor guidance dashes
            corridor_start = min(d["desk_x"] - d.get("booth_hw", 20) for d in self.desks) - 6
            corridor_end = max(d["desk_x"] + d.get("booth_hw", 20) for d in self.desks) + 6
            c.create_line(corridor_start, mid_y, corridor_end, mid_y, fill="#e2e8f0", dash=(3, 3), width=1)

        for i, d in enumerate(self.desks):
            dx, dy = d["desk_x"], d["desk_y"]
            nx, ny = d["nurse_x"], d["nurse_y"]
            py = d["patient_y"]
            tier = d.get("tier", "single")
            booth_hw = d.get("booth_hw", 24 if is_narrow else 32)
            booth_hh = d.get("booth_hh", 36 if is_narrow else 38)
            booth_top = dy - booth_hh
            booth_bot = dy + booth_hh

            # Check whether the assigned patient is physically seated at the desk
            patient_at_desk = False
            patient_en_route = False
            pid = d.get("patient_id")
            if pid is not None and pid in self.sprites:
                sp = self.sprites[pid]
                if sp.state == "IN_SERVICE":
                    patient_at_desk = True
                elif sp.state == "WALKING_TO_DESK":
                    patient_en_route = True

            # Suite floor tint and state styling
            if d["busy"] and patient_at_desk:
                if d["patient_type"] == "Emergency":
                    booth_color = "#fff1f2"
                    booth_border = "#fecdd3"
                    status_color = "#dc2626"
                    status_text = "EMERGENCY"
                else:
                    booth_color = "#f0f9ff"
                    booth_border = "#bae6fd"
                    status_color = "#2563eb"
                    status_text = "CONSULTATION"
            elif d["busy"] and patient_en_route:
                booth_color = "#fffbeb"
                booth_border = "#fde68a"
                status_color = "#b45309"
                pfx = "E" if "Elida" in self.branch_name else ("M" if "Marciano" in self.branch_name else "")
                disp_pid = f"{pfx}{pid}" if pfx else f"{pid}"
                status_text = f"CALLING {disp_pid}"
            elif d["busy"]:
                booth_color = "#f0f9ff"
                booth_border = "#bae6fd"
                status_color = "#2563eb"
                status_text = "BUSY"
            else:
                booth_color = "#f0fdf4"
                booth_border = "#bbf7d0"
                status_color = "#059669"
                status_text = "READY"

            # Clinical suite floor footprint
            c.create_rectangle(
                dx - booth_hw, booth_top, dx + booth_hw, booth_bot,
                fill=booth_color, outline=booth_border, width=1
            )

            # Architectural privacy partition walls
            c.create_line(dx - booth_hw, booth_top, dx - booth_hw, booth_bot, fill="#94a3b8", width=1.5)
            c.create_line(dx + booth_hw, booth_top, dx + booth_hw, booth_bot, fill="#94a3b8", width=1.5)
            if tier != "lower":
                c.create_line(dx - booth_hw, booth_top, dx - booth_hw + 3, booth_top, fill="#64748b", width=1.5)
                c.create_line(dx + booth_hw, booth_top, dx + booth_hw - 3, booth_top, fill="#64748b", width=1.5)
            if tier != "upper":
                c.create_line(dx - booth_hw, booth_bot, dx - booth_hw + 3, booth_bot, fill="#64748b", width=1.5)
                c.create_line(dx + booth_hw, booth_bot, dx + booth_hw - 3, booth_bot, fill="#64748b", width=1.5)

            # Suite header badge & status pill
            short_status = "CALL" if (d["busy"] and patient_en_route) else (
                "EMERG." if (d["busy"] and d["patient_type"] == "Emergency") else (
                    "BUSY" if d["busy"] else "READY"
                )
            )
            disp_status = short_status if (is_narrow or tier != "single") else status_text

            if tier == "lower":
                c.create_text(dx, booth_bot - 6, text=d["name"].upper(), font=("Segoe UI", 6, "bold"), fill="#1e293b")
                c.create_text(dx, booth_top + 6, text=f"[{disp_status}]", font=("Segoe UI", 5 if is_narrow else 6, "bold"), fill=status_color)
            elif tier == "upper":
                c.create_text(dx, booth_top + 6, text=d["name"].upper(), font=("Segoe UI", 6, "bold"), fill="#1e293b")
                c.create_text(dx, booth_bot - 6, text=f"[{disp_status}]", font=("Segoe UI", 5 if is_narrow else 6, "bold"), fill=status_color)
            else:
                c.create_rectangle(dx - 22, booth_top + 2, dx + 22, booth_top + 13, fill="#ffffff", outline="#cbd5e1", width=1)
                c.create_text(dx, booth_top + 7, text=d["name"].upper(), font=("Segoe UI", 6 if is_narrow else 7, "bold"), fill="#1e293b")
                c.create_text(dx, booth_bot - 8, text=f"[{disp_status}]", font=("Segoe UI", 6 if is_narrow else 7, "bold"), fill=status_color)

            # Consultation desk surface
            desk_hw = min(booth_hw - 3, 16 if (is_narrow or tier != "single") else 18)
            desk_hh = 4 if tier != "single" else 6
            c.create_rectangle(dx - desk_hw, dy - desk_hh, dx + desk_hw, dy + desk_hh, fill="#ffffff", outline="#475569", width=1.5)
            # Electronic medical records screen / laptop
            screen_fill = "#3b82f6" if (d["busy"] and patient_at_desk) else "#cbd5e1"
            screen_bd = "#1d4ed8" if (d["busy"] and patient_at_desk) else "#94a3b8"
            c.create_rectangle(dx - 5, dy - 2, dx + 5, dy + 2, fill=screen_fill, outline=screen_bd)

            # Patient consultation visitor chair (aligned with py)
            c.create_rectangle(dx - 5, py - 3, dx + 5, py + 4, fill="#f8fafc", outline="#94a3b8", width=1)
            c.create_line(dx - 4, py + 4 if tier != "lower" else py - 4, dx + 4, py + 4 if tier != "lower" else py - 4, fill="#64748b", width=1.5)

            # Nurse Practitioner Avatar (seated in swivel chair with nurse cap)
            self._draw_nurse_avatar(
                c, nx, ny,
                is_busy=(d["busy"] and patient_at_desk),
                patient_type=d["patient_type"]
            )

        # 8. Patient Sprites
        pfx = "E" if "Elida" in self.branch_name else ("M" if "Marciano" in self.branch_name else "")
        for pid, sp in self.sprites.items():
            if sp.state == "GONE":
                continue
            x, y, r = sp.x, sp.y, sp.radius

            # Emergency subtle red pulse halo
            if sp.patient_type == "Emergency" and sp.state in ("WAITING", "IN_SERVICE", "ENTERING"):
                c.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3,
                              outline="#fca5a5", width=2)

            # Patient Body
            c.create_oval(x - r, y - r, x + r, y + r, fill=sp.color, outline="#ffffff", width=1.5)

            # Branch-specific Patient ID label inside avatar (e.g. E1, M1)
            disp_id = f"{pfx}{pid}" if pfx else f"{pid}"
            font_size = 6 if len(disp_id) >= 3 else 7
            c.create_text(x, y, text=disp_id, font=("Segoe UI", font_size, "bold"), fill="#ffffff")

            # Status tag for exiting / completed patients
            if sp.state == "EXITING":
                c.create_text(x, y - r - 5, text="✓ Treated", font=("Segoe UI", 6, "bold"), fill="#059669")

        # 9. Mini Legend (Bottom right of canvas)
        if is_narrow:
            leg_x = w - 225
            leg_y = h - 14
            c.create_rectangle(leg_x - 6, leg_y - 7, w - 12, leg_y + 7, fill="#ffffff", outline="#e2e8f0")
            c.create_text(leg_x, leg_y, text="✚ Nurse", font=("Segoe UI", 7, "bold"), fill="#047857", anchor=tk.W)
            for idx, (label, color) in enumerate([
                ("Gen", COLOR_PATIENT_GENERAL),
                ("Emerg", COLOR_PATIENT_EMERGENCY),
                ("Done", COLOR_PATIENT_DONE),
            ]):
                lx = leg_x + 52 + idx * 52
                c.create_oval(lx, leg_y - 3, lx + 6, leg_y + 3, fill=color, outline="#ffffff")
                c.create_text(lx + 9, leg_y, text=label, font=("Segoe UI", 7), anchor=tk.W, fill="#475569")
        else:
            leg_x = w - 340
            leg_y = h - 18
            c.create_rectangle(leg_x - 10, leg_y - 9, w - 24, leg_y + 9, fill="#ffffff", outline="#e2e8f0")
            c.create_text(leg_x - 2, leg_y, text="✚ Nurse", font=("Segoe UI", 7, "bold"), fill="#047857", anchor=tk.W)
            for idx, (label, color) in enumerate([
                ("General", COLOR_PATIENT_GENERAL),
                ("Emergency", COLOR_PATIENT_EMERGENCY),
                ("Treated", COLOR_PATIENT_DONE),
            ]):
                lx = leg_x + 64 + idx * 76
                c.create_oval(lx, leg_y - 4, lx + 8, leg_y + 4, fill=color, outline="#ffffff")
                c.create_text(lx + 14, leg_y, text=label, font=("Segoe UI", 7), anchor=tk.W, fill="#475569")
