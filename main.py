import tkinter as tk
from tkinter import ttk, messagebox

from config import SimulationConfig
from simulation import SimulationController


class ClinicSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DYCI Clinic: General vs. Emergency Priority")
        self.root.geometry("1100x750")
        self.root.minsize(950, 650)

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configure colors and styles
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#1a365d")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#4a5568")
        style.configure("CardHeader.TLabel", font=("Segoe UI", 9, "bold"), foreground="#718096")
        style.configure("CardValue.TLabel", font=("Segoe UI", 16, "bold"), foreground="#2b6cb0")
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 11, "bold"), foreground="#2d3748")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=8)

    def build_ui(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            header_frame,
            text="DYCI Clinic Simulator",
            style="Title.TLabel"
        ).pack(anchor=tk.W)

        ttk.Label(
            header_frame,
            text="SimPy Discrete Event Simulation: General vs. Emergency Priority Queuing",
            style="Subtitle.TLabel"
        ).pack(anchor=tk.W, pady=(2, 0))

        # Control & Config Bar
        control_frame = ttk.LabelFrame(main_frame, text=" Simulation Parameters ", padding=12)
        control_frame.pack(fill=tk.X, pady=(0, 15))

        # Config inputs grid
        ttk.Label(control_frame, text="Duration (hrs):").grid(row=0, column=0, padx=5, pady=4, sticky=tk.W)
        self.duration_var = tk.StringVar(value="8.0")
        ttk.Entry(control_frame, textvariable=self.duration_var, width=8).grid(row=0, column=1, padx=5, pady=4)

        ttk.Label(control_frame, text="Arrival Rate (pts/hr):").grid(row=0, column=2, padx=10, pady=4, sticky=tk.W)
        self.arrival_rate_var = tk.StringVar(value="12.0")
        ttk.Entry(control_frame, textvariable=self.arrival_rate_var, width=8).grid(row=0, column=3, padx=5, pady=4)

        ttk.Label(control_frame, text="Emergency Probability:").grid(row=0, column=4, padx=10, pady=4, sticky=tk.W)
        self.emerg_prob_var = tk.StringVar(value="0.20")
        ttk.Entry(control_frame, textvariable=self.emerg_prob_var, width=8).grid(row=0, column=5, padx=5, pady=4)

        ttk.Label(control_frame, text="Nurses:").grid(row=0, column=6, padx=10, pady=4, sticky=tk.W)
        self.nurses_var = tk.StringVar(value="2")
        ttk.Entry(control_frame, textvariable=self.nurses_var, width=6).grid(row=0, column=7, padx=5, pady=4)

        self.btn_run = ttk.Button(
            control_frame,
            text="▶ Start Simulation",
            style="Primary.TButton",
            command=self.run_simulation
        )
        self.btn_run.grid(row=0, column=8, padx=20, pady=4)

        # Results KPI Cards Frame
        kpi_frame = ttk.Frame(main_frame)
        kpi_frame.pack(fill=tk.X, pady=(0, 15))

        self.card_arrivals = self.create_kpi_card(kpi_frame, "Total Arrivals", "-", 0)
        self.card_completed = self.create_kpi_card(kpi_frame, "Completed", "-", 1)
        self.card_avg_wait = self.create_kpi_card(kpi_frame, "Avg Wait Time", "-", 2)
        self.card_avg_system = self.create_kpi_card(kpi_frame, "Avg System Time", "-", 3)
        self.card_nurse_a = self.create_kpi_card(kpi_frame, "Nurse A Utilization", "-", 4)
        self.card_nurse_b = self.create_kpi_card(kpi_frame, "Nurse B Utilization", "-", 5)

        for col in range(6):
            kpi_frame.columnconfigure(col, weight=1)

        # Middle Section: Priority Breakdown & Event Logs
        content_paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        content_paned.pack(fill=tk.BOTH, expand=True)

        # Priority Breakdown Table Frame
        breakdown_frame = ttk.LabelFrame(content_paned, text=" Priority Class Comparison ", padding=10)
        content_paned.add(breakdown_frame, weight=1)

        columns = ("type", "count", "avg_wait", "avg_service", "avg_system")
        self.tree = ttk.Treeview(breakdown_frame, columns=columns, show="headings", height=4)
        self.tree.heading("type", text="Category")
        self.tree.heading("count", text="Count")
        self.tree.heading("avg_wait", text="Avg Wait (min)")
        self.tree.heading("avg_service", text="Avg Service (min)")
        self.tree.heading("avg_system", text="Avg System (min)")

        self.tree.column("type", width=120, anchor=tk.W)
        self.tree.column("count", width=60, anchor=tk.CENTER)
        self.tree.column("avg_wait", width=95, anchor=tk.CENTER)
        self.tree.column("avg_service", width=105, anchor=tk.CENTER)
        self.tree.column("avg_system", width=105, anchor=tk.CENTER)

        self.tree.pack(fill=tk.X, expand=False, pady=(0, 10))

        # Insights Label
        self.lbl_insight = ttk.Label(
            breakdown_frame,
            text="Click 'Start Simulation' to analyze waiting times.",
            font=("Segoe UI", 9, "italic"),
            foreground="#4a5568",
            wraplength=380
        )
        self.lbl_insight.pack(fill=tk.BOTH, expand=True, pady=5)

        # Event Log Frame
        logs_frame = ttk.LabelFrame(content_paned, text=" Simulation Event Logs ", padding=10)
        content_paned.add(logs_frame, weight=2)

        self.log_text = tk.Text(logs_frame, wrap=tk.NONE, font=("Consolas", 9), height=15)
        log_scroll_y = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll_x = ttk.Scrollbar(logs_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll_y.grid(row=0, column=1, sticky="ns")
        log_scroll_x.grid(row=1, column=0, sticky="ew")

        logs_frame.rowconfigure(0, weight=1)
        logs_frame.columnconfigure(0, weight=1)

        # Event log styling tags
        self.log_text.tag_config("emergency", foreground="#c53030", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("completed", foreground="#2f855a")
        self.log_text.tag_config("started", foreground="#2b6cb0")

    def create_kpi_card(self, parent, title, initial_val, col):
        card = ttk.Frame(parent, relief=tk.SOLID, borderwidth=1, padding=10)
        card.grid(row=0, column=col, padx=4, sticky="nsew")

        ttk.Label(card, text=title, style="CardHeader.TLabel").pack(anchor=tk.W)
        val_label = ttk.Label(card, text=initial_val, style="CardValue.TLabel")
        val_label.pack(anchor=tk.W, pady=(4, 0))
        return val_label

    def run_simulation(self):
        try:
            duration_hours = float(self.duration_var.get())
            arrival_rate = float(self.arrival_rate_var.get())
            emerg_prob = float(self.emerg_prob_var.get())
            nurses = int(self.nurses_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric parameters.")
            return

        # Prepare configuration
        config = SimulationConfig(
            duration=duration_hours * 60,
            arrival_rate=arrival_rate,
            emergency_probability=emerg_prob,
            nurses=nurses
        )

        controller = SimulationController()
        controller.config = config
        controller.reset()
        controller.run()

        summary = controller.summary()

        # Update KPI cards
        self.card_arrivals.config(text=str(summary["arrivals"]))
        self.card_completed.config(text=str(summary["completed"]))
        self.card_avg_wait.config(text=f"{summary['average_wait']:.2f} m")
        self.card_avg_system.config(text=f"{summary['average_system_time']:.2f} m")

        nurse_utils = summary["nurse_utilization"]
        self.card_nurse_a.config(text=f"{nurse_utils.get('Nurse A', 0.0):.1f}%")
        self.card_nurse_b.config(text=f"{nurse_utils.get('Nurse B', 0.0):.1f}%")

        # Calculate Priority Class Breakdown
        completed_pts = [p for p in controller.patients if p.completion_time is not None]
        emerg_pts = [p for p in completed_pts if p.patient_type == "Emergency"]
        gen_pts = [p for p in completed_pts if p.patient_type == "General"]

        def stats(group):
            if not group:
                return 0, 0.0, 0.0, 0.0
            cnt = len(group)
            avg_w = sum(p.waiting_time for p in group) / cnt
            avg_s = sum(p.service_time for p in group) / cnt
            avg_sys = sum(p.time_in_system for p in group) / cnt
            return cnt, avg_w, avg_s, avg_sys

        e_cnt, e_w, e_s, e_sys = stats(emerg_pts)
        g_cnt, g_w, g_s, g_sys = stats(gen_pts)

        # Clear and repopulate table
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree.insert("", tk.END, values=("Emergency (High)", e_cnt, f"{e_w:.2f}", f"{e_s:.2f}", f"{e_sys:.2f}"))
        self.tree.insert("", tk.END, values=("General (Normal)", g_cnt, f"{g_w:.2f}", f"{g_s:.2f}", f"{g_sys:.2f}"))

        diff = g_w - e_w
        if e_cnt > 0 and g_cnt > 0:
            self.lbl_insight.config(
                text=f"Priority Queuing Impact:\nEmergency patients waited on average {e_w:.2f} min, "
                     f"which is {diff:.2f} min faster than general patients ({g_w:.2f} min)."
            )
        else:
            self.lbl_insight.config(text="Simulation completed.")

        # Update Event Logs
        self.log_text.delete("1.0", tk.END)
        for event in controller.events:
            line = event + "\n"
            if "Emergency" in event:
                self.log_text.insert(tk.END, line, "emergency")
            elif "completed" in event:
                self.log_text.insert(tk.END, line, "completed")
            elif "started" in event:
                self.log_text.insert(tk.END, line, "started")
            else:
                self.log_text.insert(tk.END, line)

        self.log_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = ClinicSimulatorApp(root)
    root.mainloop()
