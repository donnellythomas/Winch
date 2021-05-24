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


# Buttons for each command
tk.Button(master, text='MANIN', command=lambda *args: set_command("MANIN")).pack()
tk.Button(master, text='MANOUT', command=lambda *args: set_command("MANOUT")).pack()
tk.Button(master, text='STOP', command=lambda *args: set_command("STOP")).pack()
# Label and input for
tk.Label(master, text="CAST TO").pack()
entry = tk.Entry(master)
entry.pack()
tk.Button(master, text='CAST', command=lambda *args: set_command("CAST " + entry.get())).pack()
tk.Button(master, text='READDATA', command=lambda *args: set_command("READDATA")).pack()
t = threading.Thread(target=send_command)
t.start()
master.mainloop()
