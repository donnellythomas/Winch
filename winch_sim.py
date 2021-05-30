import Tkinter as tk
from math import cos, sin, radians
from time import sleep
import winch as w
import threading
from winch_controller import WinchController


class WinchSim(WinchController):
    def __init__(self):
        WinchController.__init__(self)
        self.direction = tk.StringVar()
        self.direction.set("stopped")
        self.slack_sensor = tk.BooleanVar()
        self.dock_sensor = tk.BooleanVar()
        self.line_sensor = tk.BooleanVar()
        self.rotation_callback = None
        self.slack_callback = None
        self.dock_callback = None
        self.line_callback = None

    def up(self):
        self.direction.set("up")

    def down(self):
        self.direction.set("down")

    def off(self):
        self.direction.set("stopped")

    def has_slack(self):
        return self.slack_sensor.get()

    def is_docked(self):
        return self.dock_sensor.get()

    def is_out_of_line(self):
        return self.line_sensor.get()

    def set_slack_callback(self, callback):
        self.slack_callback = callback

    def set_line_callback(self, callback):
        self.line_callback = callback

    def set_dock_callback(self, callback):
        self.dock_callback = callback

    def set_rotation_callback(self, callback):
        self.rotation_callback = callback


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
        self.winch_graphic = WinchGraphic(self, height=1000, width=1000, bg="white")
        self.winch_sim = WinchSim()
        self.status_panel = StatusPanel(self, orient="vertical", relief=tk.RIDGE)
        self.input_panel = InputPanel(self, orient="vertical", relief=tk.RIDGE)
        self.add(self.input_panel)
        self.add(self.winch_graphic)
        self.add(self.status_panel)
        self.winch_graphic.pack(side=tk.LEFT)
        self.status_panel.pack(side=tk.LEFT)
        self.input_panel.pack(side=tk.LEFT)


class WinchGraphic(tk.Canvas):
    def __init__(self, parent, *args, **kw):
        self.parent = parent
        tk.Canvas.__init__(self, *args, **kw)
        self.drum = Drum(self)

    def change_direction(self, direction):
        self.parent.winch_sim.direction.set(direction)

    def sensor_check(self):
        while True:
            if self.parent.winch_sim.slack_sensor.get():
                if self.parent.winch_sim.slack_callback is not None:
                    self.parent.winch_sim.slack_callback(None)
            if self.parent.winch_sim.dock_sensor.get():
                if self.parent.winch_sim.dock_callback is not None:
                    self.parent.winch_sim.dock_callback(None)
            if self.parent.winch_sim.line_sensor.get():
                if self.parent.winch_sim.line_callback is not None:
                    self.parent.winch_sim.line_callback(None)

    def toggle(self, sensor):
        sensor.set(not sensor)


class InputPanel(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.winch_graphic = parent.winch_graphic
        self.parent = parent
        winch_sim = parent.winch_sim
        up_btn = tk.Button(self, text="force up", command=lambda: self.winch_graphic.change_direction("up"))
        down_btn = tk.Button(self, text="force down", command=lambda: self.winch_graphic.change_direction("down"))
        stop_btn = tk.Button(self, text="force stop", command=lambda: self.winch_graphic.change_direction("stop"))
        slack_toggle_btn = tk.Button(self, text="toggle slack",
                                     command=lambda: (winch_sim.slack_sensor.set(not winch_sim.slack_sensor.get()),
                                                      winch_sim.slack_callback(None)))
        dock_toggle_btn = tk.Button(self, text="toggle dock",
                                    command=lambda: winch_sim.dock_sensor.set(not winch_sim.dock_sensor.get()))
        line_toggle_btn = tk.Button(self, text="toggle line",
                                    command=lambda: winch_sim.line_sensor.set(not winch_sim.line_sensor.get()))

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
        winch_sim = parent.winch_sim
        self.direction_lbl = tk.Label(self, text="Direction:")
        self.direction_value_lbl = tk.Label(self, textvar=winch_sim.direction)
        self.slack_sensor_lbl = tk.Label(self, text="Slack:")
        self.slack_value_lbl = tk.Label(self, textvar=winch_sim.slack_sensor)
        self.dock_sensor_lbl = tk.Label(self, text="Docked:")
        self.dock_value_lbl = tk.Label(self, textvar=winch_sim.dock_sensor)
        self.line_sensor_lbl = tk.Label(self, text="Out of Line:")
        self.line_value_lbl = tk.Label(self, textvar=winch_sim.line_sensor)

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
            if self.parent.parent.winch_sim.direction.get() == "down":
                self.angle += 1
            elif self.parent.parent.winch_sim.direction.get() == "up":
                self.angle -= 1
            if self.angle % 360 == 0:
                self.angle = 1
                if self.parent.parent.winch_sim.rotation_callback is not None:
                    self.parent.parent.winch_sim.rotation_callback(None)

            self.magnet_x = self.x + cos(radians(self.angle)) * self.rotation_radius
            self.magnet_y = self.y + sin(radians(self.angle)) * self.rotation_radius
            self.parent.coords(self.magnet, create_circle(self.magnet_x, self.magnet_y, self.magnet_radius))
            sleep(.005)


def main():
    root = tk.Tk()
    window = Window(root)
    winch = w.Winch("Simulation", controller=window.interface.winch_sim)
    winch_thread = threading.Thread(target=winch.power_on)
    winch_thread.start()

    rotation_thread = threading.Thread(target=window.interface.winch_graphic.drum.rotate)
    window.pack(side="top", fill="both", expand=True)
    rotation_thread.start()
    root.mainloop()


if __name__ == "__main__":
    main()
