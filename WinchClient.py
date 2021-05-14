import socket
import threading
import tkinter as tk

from time import sleep

UDP_IP = "127.0.0.1"
UDP_PORT = 5008
print("UDP target IP: %s" % UDP_IP)
print("UDP target port: %s" % UDP_PORT)

sock = socket.socket(socket.AF_INET,  # Internet
                     socket.SOCK_DGRAM)  # UDP

master = tk.Tk()
master.title("CTD Winch Interface")

current_command = ""


def set_command(command):
    global current_command
    current_command = command


def send_command():
    global current_command
    while True:
        if current_command in {"MANIN", "MANOUT"}:
            print("Current Command:", current_command)
            sock.sendto(str.encode(current_command), (UDP_IP, UDP_PORT))
            sleep(.10)
        elif current_command != "":
            print("Current Command:", current_command)
            sock.sendto(str.encode(current_command), (UDP_IP, UDP_PORT))
            current_command = ""


t = threading.Thread(target=send_command)
t.start()
tk.Button(master, text='MANIN', command=lambda *args: set_command("MANIN")).pack()
tk.Button(master, text='MANOUT', command=lambda *args: set_command("MANOUT")).pack()
tk.Button(master, text='STOP', command=lambda *args: set_command("STOP")).pack()
tk.Label(master, text="CAST TO").pack()
entry = tk.Entry(master)
entry.pack()
tk.Button(master, text='CAST', command=lambda *args: set_command("CAST " + entry.get())).pack()
tk.Button(master, text='READDATA', command=lambda *args: set_command("READDATA")).pack()

master.mainloop()
