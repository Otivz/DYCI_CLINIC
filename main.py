"""Entry point: python main.py"""

import tkinter as tk

from gui.app import ClinicSimulatorApp


def main():
    root = tk.Tk()
    ClinicSimulatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
