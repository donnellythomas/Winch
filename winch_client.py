import socket
import threading
import Tkinter as tk
from time import sleep
import sys


class WinchClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CTD Winch Interface")
        self.current_command = ""
        self.interface = Interface(self, bd=15, sashpad=5)

        self.interface.pack(expand=1, fill="both")

        # UDP Config
        self.UDP_IP = "127.0.0.1"
        if len(sys.argv) > 1:
            self.UDP_IP = sys.argv[1]
        self.UDP_PORT = 5008
        print("UDP target IP: %s" % self.UDP_IP)
        print("UDP target port: %s" % self.UDP_PORT)
        self.sock = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
        t = threading.Thread(target=self.send_command)
        t.start()
        self.root.mainloop()

    def send_command(self):
        """Sends the command over UDP, This method is constantly running in a separate thread"""
        while True:
            # MANIN and MANOUT constantly provide input to winch
            if self.current_command in ("MANIN", "MANOUT"):
                print("Current Command:", self.current_command)
                self.sock.sendto(str.encode(self.current_command), (self.UDP_IP, self.UDP_PORT))
            # All other commands only need to be sent once
            elif self.current_command != "":
                print("Current Command:", self.current_command)
                self.sock.sendto(str.encode(self.current_command), (self.UDP_IP, self.UDP_PORT))
                self.current_command = ""
            sleep(.3)

    def set_command(self, command):
        """Change the current command"""
        self.current_command = command


class Interface(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.parent = parent
        self.controls = Controls(self, orient=tk.VERTICAL, relief=tk.RAISED, bd=5)
        self.sensors = Sensors(self, orient=tk.VERTICAL, relief=tk.RAISED, bd=5)
        self.debug_output = DebugOutput(self, orient=tk.VERTICAL, relief=tk.RAISED, width=500, bd=5)
        self.add(self.controls, stretch="always")
        self.add(self.sensors, stretch="always")
        self.add(self.debug_output, stretch="always")


class Controls(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.winch_client = parent.parent
        self.parent = parent
        manin_btn = tk.Button(self, text='Manual In', command=lambda: self.winch_client.set_command("MANIN"))
        manout_btn = tk.Button(self, text='Manual Out', command=lambda: self.winch_client.set_command("MANOUT"))
        stop_btn = tk.Button(self, text='Stop', command=lambda: self.winch_client.set_command("STOP"))
        error_btn = tk.Button(self, text='Clear Error', command=lambda: self.winch_client.set_command("CLEARERROR"))
        cast_input = CastInput(self)
        self.add(manin_btn, stretch="always")
        self.add(manout_btn, stretch="always")
        self.add(stop_btn, stretch="always")
        self.add(cast_input, stretch="always")
        self.add(error_btn, stretch="always")


class Sensors(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.parent = parent
        self.winch_client = parent.parent
        self.add(tk.Label(self, text="Slack Sensor:"))
        self.add(ToggleButton(self, "SLACK", text="on", width=12), stretch="always")
        self.add(tk.Label(self, text="Dock Sensor:"))
        self.add(ToggleButton(self, "DOCK", text="on", width=12), stretch="always")
        self.add(tk.Label(self, text="Line Sensor:"))
        self.add(ToggleButton(self, "LINE", text="on", width=12), stretch="always")
        self.add(tk.Label(self, text="Slack Sensor:"))
        self.add(ToggleButton(self, "ROTATION", text="on", width=12), stretch="always")


class CastInput(tk.Frame):
    def __init__(self, parent, *args, **kw):
        tk.Frame.__init__(self, *args, **kw)
        self.parent = parent
        # Casting with Soak depth and time
        tk.Label(self, text="Cast To:").grid(row=0, column=0)
        cast_depth = tk.Entry(self)
        cast_depth.grid(row=0, column=1)
        tk.Label(self, text="meters").grid(row=0, column=2)
        tk.Label(self, text="Soak Depth:").grid(row=1, column=0)
        soak_depth = tk.Entry(self)
        soak_depth.insert(0, "1.1")
        soak_depth.grid(row=1, column=1)
        tk.Label(self, text="meters").grid(row=1, column=2)
        tk.Label(self, text="Soak Time:").grid(row=2, column=0)
        soak_time = tk.Entry(self)
        soak_time.insert(0, "60")
        soak_time.grid(row=2, column=1)
        tk.Label(self, text="seconds").grid(row=2, column=2)
        tk.Button(self, text='Cast', command=lambda: self.parent.winch_client.set_command(
            "CAST " + cast_depth.get() + " " + soak_depth.get() + " " + soak_time.get())).grid(row=3, column=1)


class DebugOutput(tk.PanedWindow):
    def __init__(self, parent, *args, **kw):
        tk.PanedWindow.__init__(self, *args, **kw)
        self.parent = parent
        # self.frame = tk.Frame(self)
        self.textbox = tk.Text(self, state=tk.DISABLED)
        self.add(self.textbox)

    def insert_text(self, text):
        self.textbox.config(state=tk.NORMAL)
        self.textbox.insert(tk.INSERT, "\n"+text)
        self.textbox.config(state=tk.DISABLED)
        self.textbox.see("end")



""""
UDP Instructions 
Current commands: 
MANIN, MANOUT, SLACKON, SLACKOFF, DOCKON, DOCKOFF, LINEON, LINEOFF, STOP, CLEARERROR, READDATA

MANIN and MANOUT are the only commands that require continuous UDP output. This is so winch does not run wild if client
disconnects

All other commands only need to be sent once
"""


class ToggleButton(tk.Button):
    def __init__(self, parent, command, **kw):
        tk.Button.__init__(self, command=self.toggle, **kw)
        self.parent = parent
        self.command = command
        self.state = "on"
        self.config(text='on', bg="green", activebackground="green")

    def toggle(self):
        if self.state == "on":
            self.parent.winch_client.set_command(self.command + "OFF")
            self.config(text='off')
            self.config(text='off', bg="firebrick3", activebackground="firebrick3")

            self.state = "off"

        else:
            self.parent.winch_client.set_command(self.command + "ON")
            self.config(text='on', bg="green", activebackground="green")
            self.state = "on"


if __name__ == "__main__":
    WinchClient()
