try:
    import RPi.GPIO as GPIO

    sim = False
except:
    sim = True

from time import sleep

from context import Context
from states import *


class Winch(Context):
    sim = None;
    payout_rate = 0
    state_sequence = []
    target_depth = 0
    depth = 0
    conductivity = 0
    temp = 0
    pins = None
    error_message = ""
    command = None
    slack_pin = None
    dock_pin = None
    up_pin = None
    down_pin = None

    def __init__(self, context_name, cal_file = 'cal_data.txt'):
        Context.__init__(self, context_name)
        # add all the states to the winch
        self.cal_file = cal_file
        self.cal_data = {"rotations":[], "meters":[]}
        self.add_state(InitState("INIT"))
        self.add_state(StdbyState("STDBY"))
        self.add_state(CastState("CAST"))
        self.add_state(StopState("STOP"))
        self.add_state(DownCastState("DOWNCAST"))
        self.add_state(UpCastState("UPCAST"))
        self.add_state(ReadDataState("READDATA"))
        self.add_state(ErrorState("ERROR"))
        self.add_state(ManualWinchInState("MANIN"))
        self.add_state(ManualWinchOutState("MANOUT"))

    def power_on(self):
        """
        Power on winch
        :return:
        """
        print("Power is ON!")
        self.set_state("INIT")
        print("Automatically entering State_Initialization!")
        self.entry_behavior(self.get_state())

    def power_off(self):
        """Power off winch"""
        # cleanup GPIO
        print("Calling Power Off!")

    def queue_command(self, command):
        """
        Queue a transition command to the execution stack
        :param command: Map<String,String>
        :return:
        """
        self.state_sequence.append(command)
        print("COMMAND QUEUE:", self.state_sequence)

    def execute_state_stack(self):
        """
        Pop off and run the commands in the command stack on at a time
        :return:
        """
        while self.state_sequence:
            winch.do_transition(self.state_sequence.pop(0))
        winch.do_transition({"from": self.get_state().get_name(), "to": "STDBY"})

    def down(self):
        """
        Winch out
        :return:
        """
        if not self.sim:
            if not (winch.has_slack() or winch.is_out_of_line()):  # slack
                GPIO.output(24, GPIO.LOW)
                GPIO.output(23, GPIO.HIGH)
            else: self.motors_off()

        else:
            winch.depth += 1
            sleep(1)

    def up(self):
        """
        Winch in
        :return:
        """
        if not self.sim:
            if not (winch.has_slack() or winch.is_docked()):
                GPIO.output(23, GPIO.LOW)
                GPIO.output(24, GPIO.HIGH)
            else: self.motors_off()
        else:
            winch.depth -= 1
            sleep(1)

    def motors_off(self):
        if not self.sim:
            GPIO.output(23, GPIO.LOW)
            GPIO.output(24, GPIO.LOW)
            
    def stop(self):
        self.do_transition({"from": self.get_state().get_name(), "to": "STOP"})


    def report_position(self):
        """
        Report the current position of the winch
        :return:
        """
        print("Current Depth: ", self.depth)

    def error(self, message):
        """
        Set the error status and transition into error state
        :param message:
        :return:
        """
        self.error_message = message
        self.do_transition({"from": self.get_state().get_name(), "to": "ERROR"})


    def receive_commands(self):
        print("Starting command thread")
        UDP_IP = "127.0.0.1"
        UDP_PORT = 5008
        sock = socket.socket(socket.AF_INET,  # Internet
                             socket.SOCK_DGRAM)  # UDP
        sock.bind((UDP_IP, UDP_PORT))
        sock.settimeout(1)

        while True:
            try:
                command, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
                self.command = command.decode()
                # print("received command: %s" % self.command)

            except socket.timeout:
                self.command = None
                # print("Command timeout")

    def has_slack(self):
        if not winch.sim:
            slack = GPIO.input(self.slack_pin) == GPIO.HIGH
        else:
            slack = False
        # print("Has Slack:", slack)
        return slack

    def is_docked(self):
        if not winch.sim:
            docked = GPIO.input(self.dock_pin) == GPIO.LOW
            if docked: winch.stop()
        else:
            docked = False
        # print("Is docked:", docked)
        return docked

    def is_out_of_line(self):
        if not winch.sim:
            out_of_line = GPIO.input(self.dock_pin) == GPIO.LOW
            if out_of_line: winch.stop()

        else:
            out_of_line = False
        # print("Is out_of_line:", out_of_line)
        return out_of_line


if __name__ == "__main__":
    winch = Winch("my_winch")
    if sim: Winch.sim = True
    winch.power_on()
