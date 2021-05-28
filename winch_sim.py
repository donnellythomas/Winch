import Tkinter as tk
from math import cos, sin, radians
from time import sleep
from winch import Winch
import threading


class Winch:
    def __init__(self):
        self.direction = tk.StringVar()
        self.direction.set("Stopped")
        self.slack_sensor = tk.BooleanVar()
        self.dock_sensor = tk.BooleanVar()
        self.line_sensor = tk.BooleanVar()


class Window(tk.Frame):
    def __init__(self, parent, *args, **kw):
        self.parent = parent
        tk.Frame.__init__(self, *args, **kw)
        self.interface = Interface(self)
        self.interface.pack(fill="both", expand=True)


class Interface(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.parent = parent
        self.winch = Winch()
        self.winch_sim = WinchSim(self, height=1000, width=1000, bg="white")
        self.status_panel = StatusPanel(self, orient="vertical", relief= tk.RIDGE)
        self.input_panel = InputPanel(self, orient="vertical", relief= tk.RIDGE)
        self.add(self.input_panel)
        self.add(self.winch_sim)
        self.add(self.status_panel)
        self.winch_sim.pack(side=tk.LEFT)
        self.status_panel.pack(side=tk.LEFT)
        self.input_panel.pack(side=tk.LEFT)


class WinchSim(tk.Canvas):
    def __init__(self, parent, *args, **kw):
        self.parent = parent
        tk.Canvas.__init__(self, *args, **kw)
        self.drum = Drum(self)
        self.rotation_callback = None
        self.slack_callback = None
        self.dock_callback = None
        self.line_callback = None
        rotation_thread = threading.Thread(target=self.drum.rotate)
        sensor_thread = threading.Thread(target=self.sensor_check)
        rotation_thread.start()
        sensor_thread.start()

    def change_direction(self, direction):
        self.parent.winch.direction.set(direction)

    def sensor_check(self):
        while True:
            if self.parent.winch.slack_sensor.get():
                if self.slack_callback is not None:
                    self.slack_callback()
            if self.parent.winch.dock_sensor.get():
                if self.dock_callback is not None:
                    self.dock_callback()
            if self.parent.winch.line_sensor.get():
                if self.line_callback is not None:
                    self.line_callback()

    def toggle(self, sensor):
        sensor.set(not sensor)


class InputPanel(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.winch_sim = parent.winch_sim
        self.parent = parent
        winch = parent.winch
        up_btn = tk.Button(self, text="force up", command=lambda: self.winch_sim.change_direction("up"))
        down_btn = tk.Button(self, text="force down", command=lambda: self.winch_sim.change_direction("down"))
        stop_btn = tk.Button(self, text="force stop", command=lambda: self.winch_sim.change_direction("stop"))
        slack_toggle_btn = tk.Button(self, text="toggle slack",
                                     command=lambda : winch.slack_sensor.set(not winch.slack_sensor.get()))
        dock_toggle_btn = tk.Button(self, text="toggle dock",
                                    command=lambda: winch.dock_sensor.set(not winch.dock_sensor.get()))
        line_toggle_btn = tk.Button(self, text="toggle line",
                                    command=lambda: winch.line_sensor.set(not winch.line_sensor.get()))

        self.add(up_btn)
        self.add(down_btn)
        self.add(stop_btn)
        self.add(slack_toggle_btn)
        self.add(dock_toggle_btn)
        self.add(line_toggle_btn)


class StatusPanel(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.parent = parent
        winch = parent.winch
        self.direction_lbl = tk.Label(self, text="Direction:")
        self.direction_value_lbl = tk.Label(self, textvar=winch.direction)
        self.slack_sensor_lbl = tk.Label(self, text="Slack:")
        self.slack_value_lbl = tk.Label(self, textvar=winch.slack_sensor)
        self.dock_sensor_lbl = tk.Label(self, text="Docked:")
        self.dock_value_lbl = tk.Label(self, textvar=winch.dock_sensor)
        self.line_sensor_lbl = tk.Label(self, text="Out of Line:")
        self.line_value_lbl = tk.Label(self, textvar=winch.line_sensor)

        self.add(self.direction_lbl)
        self.add(self.direction_value_lbl)
        self.add(self.slack_sensor_lbl)
        self.add(self.slack_value_lbl)
        self.add(self.dock_sensor_lbl)
        self.add(self.dock_value_lbl)
        self.add(self.line_sensor_lbl)
        self.add(self.line_value_lbl)


def create_circle(x, y, r):  # center coordinates, radius
    x0 = x - r
    y0 = y - r
    x1 = x + r
    y1 = y + r
    return x0, y0, x1, y1


class Drum:
    def __init__(self, parent, *args, **kw):
        self.parent = parent
        self.x = 500
        self.y = 500
        self.magnet_x = 250
        self.magnet_y = 500
        self.rotation_radius = 250
        self.magnet_radius = 50
        self.drum_radius = 350
        self.angle = 0
        self.parent = parent
        self.drum = parent.create_oval(create_circle(self.x, self.y, self.drum_radius), fill="blue")
        self.magnet = parent.create_oval(create_circle(self.magnet_x, self.magnet_y, self.magnet_radius), fill="RED")

    def rotate(self):
        while True:
            if self.parent.parent.winch.direction.get() == "down":
                self.angle += 1
            elif self.parent.parent.winch.direction.get() == "up":
                self.angle -= 1
            if self.angle % 360 == 0:
                if self.parent.rotation_callback is not None:
                    self.parent.rotation_callback()
                self.angle = 0

            self.magnet_x = self.x + cos(radians(self.angle)) * self.rotation_radius
            self.magnet_y = self.y + sin(radians(self.angle)) * self.rotation_radius
            self.parent.coords(self.magnet, create_circle(self.magnet_x, self.magnet_y, self.magnet_radius))
            sleep(.01)


def main():
    root = tk.Tk()
    window = Window(root).pack(side="top", fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
