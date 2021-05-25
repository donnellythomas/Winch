import socket
import threading
import Tkinter as tk
from time import sleep

# IP and port for UDP current values are what I was using for testing
UDP_IP = "127.0.0.1"
UDP_PORT = 5008
print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)

sock = socket.socket(socket.AF_INET,  # Internet
                     socket.SOCK_DGRAM)  # UDP

# Tkinter GUI
master = tk.Tk()
master.title("CTD Winch Interface")

# Command that will be sent over UDP
current_command = ""


# soak depth 1.1 meters
# soak time 1 minute
def set_command(command):
    """
    Change the current command
    :param command:String
    """
    global current_command
    current_command = command


def send_command():
    """
    Sends the command over UDP, This method is constantly running in a separate thread
    """
    global current_command
    while True:
        # MANIN and MANOUT constantly provide input to winch
        if current_command in ("MANIN", "MANOUT"):
            print("Current Command:", current_command)
            sock.sendto(str.encode(current_command), (UDP_IP, UDP_PORT))
        # All other commands only need to be sent once
        elif current_command != "":
            print("Current Command:", current_command)
            sock.sendto(str.encode(current_command), (UDP_IP, UDP_PORT))
            current_command = ""
        sleep(.3)


def slack_toggle(tog=[0]):
    '''
    a list default argument has a fixed address
    '''
    tog[0] = not tog[0]
    if tog[0]:
        set_command("SLACKOFF")
        slack_btn.config(text='off')
    else:
        set_command("SLACKON")
        slack_btn.config(text='on')


def dock_toggle(tog=[0]):
    '''
    a list default argument has a fixed address
    '''
    tog[0] = not tog[0]
    if tog[0]:
        set_command("DOCKOFF")
        dock_btn.config(text='off')
    else:
        set_command("DOCKON")
        dock_btn.config(text='on')


def line_toggle(tog=[0]):
    '''
    a list default argument has a fixed address
    '''
    tog[0] = not tog[0]
    if tog[0]:
        set_command("LINEOFF")
        line_btn.config(text='off')
    else:
        set_command("LINEON")
        line_btn.config(text='on')


# Buttons for each command
tk.Button(master, text='Manual In', command=lambda *args: set_command("MANIN")).grid(row=0, column=0)
tk.Button(master, text='Manual Out', command=lambda *args: set_command("MANOUT")).grid(row=1, column=0)
tk.Label(master, text="Slack Sensor:").grid(row=0, column=1)
tk.Label(master, text="Dock Sensor:").grid(row=0, column=2)
tk.Label(master, text="Line Sensor:").grid(row=0, column=3)
slack_btn = tk.Button(text="on", width=12, command=slack_toggle)
slack_btn.grid(row=1, column=1)
dock_btn = tk.Button(text="on", width=12, command=dock_toggle)
dock_btn.grid(row=1, column=2)
line_btn = tk.Button(text="on", width=12, command=line_toggle)
line_btn.grid(row=1, column=3)

tk.Button(master, text='Stop', command=lambda *args: set_command("STOP")).grid(row=2, column=0)
# Label and input for
tk.Label(master, text="Cast To:").grid(row=3, column=0)
cast_depth = tk.Entry(master)
cast_depth.grid(row=3, column=1)
tk.Label(master, text="meters").grid(row=3, column=2)

tk.Label(master, text="Soak Depth:").grid(row=4, column=0)
soak_depth = tk.Entry(master)
soak_depth.insert(0, "1.1")
soak_depth.grid(row=4, column=1)
tk.Label(master, text="meters").grid(row=4, column=2)

tk.Label(master, text="Soak Time:").grid(row=5, column=0)
soak_time = tk.Entry(master)
soak_time.insert(0, "60")
soak_time.grid(row=5, column=1)
tk.Label(master, text="seconds").grid(row=5, column=2)

tk.Button(master, text='Cast', command=lambda *args: set_command(
    "CAST " + cast_depth.get() + " " + soak_depth.get() + " " + soak_time.get())).grid(row=6, column=1)
tk.Button(master, text='Read Data', command=lambda *args: set_command("READDATA")).grid(row=7, column=0)
t = threading.Thread(target=send_command)
t.start()
master.mainloop()
