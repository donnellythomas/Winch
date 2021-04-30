try:
    import RPi.GPIO as GPIO

    sim = False
except:
    sim = True

from time import sleep

from context import Context
from states import *


class Winch(Context):
    sim = None # for running when not on raspberry pi
    
    # Sequence of states for commands that require multiple state changes
    # for example CAST
    state_sequence = []
    
    # CTD Data
    conductivity = 0
    temp = 0
    depth = 0
    
    #soak params
    soak_depth = 0
    soak_time = 0
    
    # Target depth that the winch is currently paying out to
    target_depth = 0

    # Current command that has been received by the client
    command = None

    # Raspberry Pi hardware pins for GPIO
    slack_pin = None
    dock_pin = None
    up_pin = None
    out_of_line_pin = None
    down_pin = None
    depth_pin = None
    
    # Current direction winch is moving, can be UP or DOWN
    direction = ""
    
    # Flags for current state of the winch
    has_slack = False
    is_docked = False
    is_out_of_line = False
    is_stopped = False

    def __init__(self, context_name, cal_file='cal_data.txt'):
        Context.__init__(self, context_name)
        # add all the states to the winch
        self.cal_file = cal_file
        self.cal_data = {"rotations": [], "meters": []}
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
        self.add_state(SoakState("SOAK"))
        

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

    def execute_state_stack(self):
        """
        Pop off and run the commands in the command stack on at a time
        :return:
        """
        while self.state_sequence:
            winch.do_transition(self.state_sequence.pop(0))

    def down(self):
        """
        Winch out
        :return:
        """
        self.direction = "down"
    #    print("Going down...")

        if not self.sim:
            GPIO.output(24, GPIO.LOW)
            GPIO.output(23, GPIO.HIGH)

        else:
            winch.depth += 1
            sleep(1)

    def up(self):
        """
        Winch in
        :return:
        """
        self.direction = "up"
#         print("Going up...")
        if not self.sim:
            GPIO.output(23, GPIO.LOW)
            GPIO.output(24, GPIO.HIGH)

        else:
            winch.depth -= 1
            sleep(1)

    def motors_off(self):
        print("Motors off")
        if not self.sim:
            GPIO.output(23, GPIO.LOW)
            GPIO.output(24, GPIO.LOW)

    def slack_callback(self, channel):
        if GPIO.input(channel) == GPIO.HIGH:
            self.has_slack = True
            self.motors_off()
        elif self.has_slack:
#            print("slack released")
            self.has_slack = False


    def stop(self):
        self.direction = ""
        self.do_transition("STOP")

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
        self.do_transition("ERROR")

    def receive_commands(self):
        print("Starting command thread")
        UDP_IP = "127.0.0.1"
        UDP_PORT = 5008
        sock = socket.socket(socket.AF_INET,  # Internet
                             socket.SOCK_DGRAM)  # UDP
        sock.bind((UDP_IP, UDP_PORT))
        sock.settimeout(.1)

        while True:
            try:
                if self.is_docked or self.is_out_of_line:
                    raise Exception
                command, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
                self.command = command.decode()
                if self.command == "STOP":
                    self.stop()
                # print("received command: %s" % self.command)

            except:
                self.command = None
                # print("Command timeout")

    def docked_callback(self, channel):
        if GPIO.input(channel) == GPIO.LOW:
            print("Docked")
            self.is_docked = True
            self.depth = 0
            self.stop()
        else:
            self.is_docked = False

    def out_of_line_callback(self, channel):
        if GPIO.input(channel) == GPIO.LOW:
            self.is_out_of_line = True
            print("Out of line")
            self.stop()
        else:
            self.is_out_of_line = False


    def depth_callback(self, channel):
        if self.direction == "up":
            self.depth -= 1
        elif self.direction == "down":
            self.depth += 1
        else:
            print("ERROR: Winch moving without known direction")
        print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))



if __name__ == "__main__":
    winch = Winch("my_winch")
    if sim: winch.sim = True
    winch.power_on()
