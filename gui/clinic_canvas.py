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
        self.speed = 4.0
        self.radius = 11

    def set_target(self, tx, ty, speed=4.0):
        self.target_x = float(tx)
        self.target_y = float(ty)
        self.speed = speed

    def add_waypoint(self, wx, wy, speed=4.0):
        self.waypoints.append((float(wx), float(wy), speed))

    def step(self):
        """Move one step toward the target. Follow waypoints sequentially."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist <= self.speed or dist < 1.0:
            self.x = self.target_x
            self.y = self.target_y
            if self.waypoints:
                next_x, next_y, next_spd = self.waypoints.pop(0)
                self.set_target(next_x, next_y, next_spd)
                return False
            return True
        self.x += (dx / dist) * self.speed
        self.y += (dy / dist) * self.speed
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
        mid_y = height // 2 + 6
        self.entrance_pos = (36, mid_y)
        self.triage_pos = (96, mid_y)
        self.exit_pos = (width - 36, mid_y)

        # Branch-specific capacity
        if "Marciano" in branch:
            chair_rows, chair_cols, n_nurses = 2, 10, 3
        elif "Elida" in branch:
            chair_rows, chair_cols, n_nurses = 2, 7, 2
        else:
            chair_rows, chair_cols, n_nurses = 2, 8, max(self.nurse_count, 2)

        # Existing patient mappings preserved
        old_chairs = self.branch_chairs.get(branch, [])
        occupied = {i: c.get("patient_id") for i, c in enumerate(old_chairs) if c.get("patient_id")}

        chairs = []
        waiting_start_x = 165
        spacing_x = 24
        spacing_y = 26
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

        # Desks
        desks = []
        desk_area_start = waiting_start_x + chair_cols * spacing_x + 55
        desk_area_width = self.exit_pos[0] - desk_area_start - 45
        n = max(n_nurses, 1)
        step = max(desk_area_width / n, 72)

        for i in range(n):
            dx = desk_area_start + i * step + 35
            dy = mid_y
            nurse_y = dy - 24
            patient_y = dy + 24
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
                "patient_type": None
            })
        self.branch_desks[branch] = desks

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
                sp = sprites[p_id]
                if sp.chair_idx is None:
                    chair_idx = self._find_empty_chair(p_id, chairs)
                    if chair_idx is not None:
                        sp.chair_idx = chair_idx
                        chairs[chair_idx]["patient_id"] = p_id
                        sp.set_target(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=6.0)

        for p_id, (n_idx, p_type) in busy_nurse_patients.items():
            if p_id not in sprites:
                sp = PatientSprite(p_id, p_type, self.entrance_pos[0], self.entrance_pos[1])
                sprites[p_id] = sp
            sp = sprites[p_id]
            if n_idx < len(desks):
                desk = desks[n_idx]
                if sp.state != "IN_SERVICE":
                    if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                        chairs[sp.chair_idx]["patient_id"] = None
                        sp.chair_idx = None
                    sp.nurse_idx = n_idx
                    sp.state = "WALKING_TO_DESK"
                    sp.set_target(desk["patient_x"], desk["patient_y"], speed=6.5)

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
            except Exception:
                pass

        elif kind == "start":
            try:
                parts = msg.split()
                pid = int(parts[1])
                nurse_letter = parts[5].replace("Nurse", "").strip()
                if not nurse_letter and len(parts) >= 6:
                    nurse_letter = parts[5]
                nurse_idx = ord(nurse_letter[-1]) - ord('A') if nurse_letter else 0
                if 0 <= nurse_idx < len(desks):
                    desk = desks[nurse_idx]
                    if pid in sprites:
                        sp = sprites[pid]
                        if sp.chair_idx is not None and sp.chair_idx < len(chairs):
                            chairs[sp.chair_idx]["patient_id"] = None
                            sp.chair_idx = None
                        sp.nurse_idx = nurse_idx
                        sp.state = "WALKING_TO_DESK"
                        sp.set_target(desk["patient_x"], desk["patient_y"], speed=6.0)
            except Exception:
                pass

        elif kind == "complete":
            try:
                parts = msg.split()
                pid = int(parts[1])
                if pid in sprites:
                    sp = sprites[pid]
                    sp.color = COLOR_PATIENT_DONE
                    sp.state = "EXITING"
                    sp.set_target(self.exit_pos[0], self.exit_pos[1], speed=5.5)
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
                    sp.color = COLOR_PATIENT_RENEGE
                    sp.state = "EXITING"
                    sp.set_target(self.exit_pos[0], self.exit_pos[1], speed=5.5)
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
                        sp.set_target(chairs[chair_idx]["x"], chairs[chair_idx]["y"], speed=5.0)
            except Exception:
                pass

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
            for pid, sp in sp_dict.items():
                reached = sp.step()
                if reached:
                    if sp.state == "ENTERING":
                        sp.state = "WAITING"
                    elif sp.state == "WALKING_TO_DESK":
                        sp.state = "IN_SERVICE"
                    elif sp.state == "EXITING":
                        sp.state = "GONE"
                        to_delete.append(pid)
            for pid in to_delete:
                del sp_dict[pid]

        self.redraw()
        if self.anim_running:
            self._anim_job = self.after(35, self._animate)

    def redraw(self):
        """Draw the entire clinic environment, stations, and active sprites."""
        c = self.canvas
        c.delete("all")
        w = c.winfo_width()
        h = self.canvas_height

        # 1. Floor background & boundary walls
        c.create_rectangle(10, 10, w - 10, h - 10, fill=COLOR_FLOOR, outline=COLOR_WALL, width=1.5)

        # Subtle floor grid
        for gy in range(35, h - 15, 30):
            c.create_line(15, gy, w - 15, gy, fill="#f1f5f9", width=1)

        # 2. Branch Banner & Identification (Top Header inside Canvas)
        banner_text = f"📍 DYCI HEALTH SERVICES  •  {self.branch_name.upper()}"
        capacity_text = f"Staffing: {self.nurse_count} Nurses  |  Waiting: {len(self.chairs)} Chairs"
        c.create_rectangle(15, 12, w - 15, 34, fill="#f8fafc", outline="#e2e8f0", width=1)
        c.create_text(26, 23, text=banner_text, font=("Segoe UI", 8, "bold"), fill="#1a365d", anchor=tk.W)
        c.create_text(w - 26, 23, text=capacity_text, font=("Segoe UI", 8), fill="#64748b", anchor=tk.E)

        # 3. Entrance Door (Left)
        ex, ey = self.entrance_pos
        c.create_rectangle(10, ey - 26, 26, ey + 26, fill="#e2e8f0", outline="#94a3b8", width=1)
        c.create_line(26, ey - 24, 26, ey + 24, fill="#2563eb", width=3)
        c.create_text(ex + 8, ey - 34, text="ENTRANCE", font=("Segoe UI", 7, "bold"), fill="#64748b")
        c.create_text(ex + 8, ey, text="🚪", font=("Segoe UI", 12))

        # 4. Triage / Reception Check-in Station
        tx, ty = self.triage_pos
        c.create_rectangle(tx - 22, ty - 28, tx + 22, ty + 28, fill="#f0f9ff", outline="#bae6fd", width=1)
        c.create_rectangle(tx - 16, ty - 6, tx + 16, ty + 6, fill="#ffffff", outline="#64748b", width=1.5)
        c.create_rectangle(tx - 6, ty - 3, tx + 6, ty + 3, fill="#94a3b8")
        # Triage Nurse Avatar
        c.create_oval(tx - 10, ty - 20, tx + 10, ty, fill="#0284c7", outline="#0369a1", width=1.5)
        c.create_text(tx, ty - 10, text="T", font=("Segoe UI", 8, "bold"), fill="#ffffff")
        c.create_text(tx, ty - 28, text="TRIAGE", font=("Segoe UI", 7, "bold"), fill="#0369a1")
        c.create_text(tx, ty + 18, text="Check-In", font=("Segoe UI", 7), fill="#64748b")

        # 5. Exit Door (Right)
        ox, oy = self.exit_pos
        c.create_rectangle(w - 26, oy - 26, w - 10, oy + 26, fill="#e2e8f0", outline="#94a3b8", width=1)
        c.create_line(w - 26, oy - 24, w - 26, oy + 24, fill="#10b981", width=3)
        c.create_text(ox - 8, oy - 34, text="EXIT", font=("Segoe UI", 7, "bold"), fill="#64748b")
        c.create_text(ox - 8, oy, text="🚪", font=("Segoe UI", 12))

        # 6. Waiting Lounge Zone
        c.create_text(200, 42, text="🛋 WAITING ROOM", font=("Segoe UI", 8, "bold"), fill="#1a365d")
        for chair in self.chairs:
            cx, cy = chair["x"], chair["y"]
            c.create_rectangle(cx - 9, cy - 9, cx + 9, cy + 9, fill=COLOR_CHAIR,
                               outline=COLOR_CHAIR_BORDER, width=1)
            c.create_line(cx - 8, cy - 8, cx + 8, cy - 8, fill=COLOR_CHAIR_BORDER, width=2)

        # 7. Nurse Consultation Workstations
        for d in self.desks:
            dx, dy = d["desk_x"], d["desk_y"]
            nx, ny = d["nurse_x"], d["nurse_y"]

            # Workstation booth background
            booth_color = "#fff1f2" if (d["busy"] and d["patient_type"] == "Emergency") else (
                "#f0f9ff" if d["busy"] else "#f8fafc"
            )
            c.create_rectangle(dx - 30, dy - 36, dx + 30, dy + 36, fill=booth_color,
                               outline="#e2e8f0", width=1)

            # Desk surface
            c.create_rectangle(dx - 22, dy - 8, dx + 22, dy + 8, fill="#ffffff",
                               outline=COLOR_DESK_BORDER, width=1.5)
            c.create_rectangle(dx - 8, dy - 4, dx + 8, dy + 4, fill="#94a3b8", outline="#64748b")

            # Nurse avatar (seated at top of desk)
            nurse_color = COLOR_NURSE if not d["busy"] else "#1e40af"
            c.create_oval(nx - 11, ny - 11, nx + 11, ny + 11, fill=nurse_color,
                          outline=COLOR_NURSE_BORDER, width=1.5)
            c.create_text(nx, ny, text="+", font=("Segoe UI", 10, "bold"), fill="#ffffff")
            c.create_text(nx, ny - 16, text=d["name"], font=("Segoe UI", 8, "bold"), fill="#1e293b")

            # Desk status pill
            status_text = "BUSY" if d["busy"] else "READY"
            status_color = "#dc2626" if (d["busy"] and d["patient_type"] == "Emergency") else (
                "#2563eb" if d["busy"] else "#059669"
            )
            c.create_text(dx, dy + 22, text=f"[{status_text}]", font=("Segoe UI", 7, "bold"), fill=status_color)

        # 8. Patient Sprites
        for pid, sp in self.sprites.items():
            if sp.state == "GONE":
                continue
            x, y, r = sp.x, sp.y, sp.radius

            # Emergency subtle red pulse halo
            if sp.patient_type == "Emergency" and sp.state in ("WAITING", "IN_SERVICE", "ENTERING"):
                c.create_oval(x - r - 4, y - r - 4, x + r + 4, y + r + 4,
                              outline="#fca5a5", width=2)

            # Patient Body
            c.create_oval(x - r, y - r, x + r, y + r, fill=sp.color, outline="#ffffff", width=1.5)

            # Patient ID label inside avatar
            c.create_text(x, y, text=f"{pid}", font=("Segoe UI", 7, "bold"), fill="#ffffff")

        # 9. Mini Legend (Bottom right of canvas)
        leg_x = w - 270
        leg_y = h - 20
        c.create_rectangle(leg_x - 10, leg_y - 10, w - 40, leg_y + 10, fill="#ffffff", outline="#e2e8f0")
        for idx, (label, color) in enumerate([
            ("General", COLOR_PATIENT_GENERAL),
            ("Emergency", COLOR_PATIENT_EMERGENCY),
            ("Treated", COLOR_PATIENT_DONE),
        ]):
            lx = leg_x + idx * 76
            c.create_oval(lx, leg_y - 4, lx + 8, leg_y + 4, fill=color, outline="#ffffff")
            c.create_text(lx + 14, leg_y, text=label, font=("Segoe UI", 7), anchor=tk.W, fill="#475569")
