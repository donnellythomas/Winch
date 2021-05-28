# Allow for program to be run outside of a raspberry pi
try:
    import RPi.GPIO as GPIO

    sim = False
except:
    sim = True

from context import Context
from states import *
from timer import Timer


class Winch(Context):
    # Simulation flag
    sim = None

    # Sequence of states that are to be executed
    state_sequence = []

    # CTD Data - Depth is only one currently being used
    # This data may instead be gathered externally
    conductivity = 0
    temp = 0
    # Depth is measure in rotations NOT METERS
    depth = 0

    # soak params
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

    # Current direction winch is moving, can be UP or DOWN or empty string
    direction = ""

    # Current state of the winch
    has_slack = False
    is_docked = False
    is_out_of_line = False
    is_stopped = False
    has_error = False
    error_message = ""

    # Flags for enabling and disabling sensors for manual operation
    slack_sensor_on = True
    dock_sensor_on = True
    line_sensor_on = True

    # Timers used for error checking
    slack_timer = Timer()
    rotation_timer = Timer()

    def __init__(self, context_name, cal_file='cal_data.txt'):
        """
        Initialization for Winch parameters (not to be confused with initialization state)
        Arguments:
            context_name -- name of the winch
            cal_file -- drum rotation calibration file for interpolation
        """
        Context.__init__(self, context_name)

        # Setup for distance interpolation - rotations of drum to meters
        self.cal_file = cal_file
        self.cal_data = {"rotations": [], "meters": []}

        # add all the states to the winch
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
        """Start the winch - put into initialization state"""
        print("Power is ON!")
        print("Automatically entering State_Initialization!")
        # Set state of winch to initialization start
        self.set_state("INIT")
        # Execute entry behavior of the current state
        self.entry_behavior(self.get_state())

    def queue_command(self, command):
        """Add command for state change into state sequence queue"""
        self.state_sequence.append(command)

    def down(self):
        """
        Set motors to pay out
        No state checking happens here such as dock, line, or slack sensors because actions need to be overridable.
        """

        # print("Going down...")

        self.direction = "down"
        if not self.sim:
            # Activate motor
            GPIO.output(self.down_pin, GPIO.LOW)
            GPIO.output(self.up_pin, GPIO.HIGH)
        else:
            # Simulate winch descending
            winch.depth += 1
            self.report_position()
            sleep(1)

    def up(self):
        """
        Set motors to pay in
        No state checking happens here such as dock, line, or slack sensors because actions need to be overridable.
        """
        # print("Going up...")

        self.direction = "up"
        if not self.sim:
            # Activate motor
            GPIO.output(self.down_pin, GPIO.HIGH)
            GPIO.output(self.up_pin, GPIO.LOW)
        else:
            # Simulate winch ascending
            winch.depth -= 1
            self.report_position()
            sleep(1)

    def motor_off(self):
        """Turn winch motor off"""
        print("Motors off...")
        # Remove current direction
        self.direction = ""

        # Timer for rotation checking can be turned off because motor is off
        self.rotation_timer.stop()

        if not self.sim:
            # Deactivate motor
            GPIO.output(self.down_pin, GPIO.LOW)
            GPIO.output(self.up_pin, GPIO.LOW)

    def stop(self):
        """
        Put the winch into stop state
        STOP command is added to the front of the state_sequence so it is the next state to execute
        Within StopState state_sequence is cleared

        State is inserted into state sequence instead of tradition to because this method can be called from
        receive_command which is called in a different thread causing winch to be in multiple states at once in
        different threads
        """
        self.state_sequence.insert(0, "STOP")

    def report_position(self):
        """Print the current position of the winch"""
        print("Current Depth: ", self.depth)

    def error(self, message):
        """
        Set the error message for the error and transition into error state
        ERROR command is added to the front of state_sequence so it is the next state to execute
        Within ErrorState state_sequence is cleared

        State is inserted into state sequence instead of tradition to because this method can be called from
        receive_command which is called in a different thread causing winch to be in multiple states at once in
        different threads
        """
        self.error_message = message
        self.state_sequence.insert(0, "ERROR")

    def receive_commands(self):
        """Command receiver that is run in a separate thread so that no command is missed"""
        print("Starting command thread...")

        # TODO: pull into config file
        UDP_IP = ""
        UDP_PORT = 5008

        # UDP socket setup
        sock = socket.socket(socket.AF_INET,  # Internet
                             socket.SOCK_DGRAM)  # UDP
        sock.bind((UDP_IP, UDP_PORT))
        # Commands received via UDP are set to timeout after a given amount of time
        # UDP commands are set to timeout to avoid from them going stale
        # TODO: Add this into config file
        # TODO: Investigate better way to clear UDP buffer
        sock.settimeout(.1)

        while True:
            # Run continuously
            try:
                # Receive command in bytes
                command, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
                # Decode command into string
                self.command = command.decode()

                # Following commands require immediate action and cannot be missed
                if self.command == "STOP":
                    self.stop()
                if self.command == "SLACKOFF":
                    self.slack_sensor_on = False
                    self.command = None
                if self.command == "SLACKON":
                    self.slack_sensor_on = True
                    self.command = None
                if self.command == "DOCKOFF":
                    self.dock_sensor_on = False
                    self.command = None
                if self.command == "DOCKON":
                    self.dock_sensor_on = True
                    self.command = None
                if self.command == "LINEOFF":
                    self.line_sensor_on = False
                    self.command = None
                if self.command == "LINEON":
                    self.line_sensor_on = True
                    self.command = None
                if self.command == "CLEARERROR":
                    self.has_error = False
                    self.command = None
            # socket timeout raises exception - in that case set command to none
            except:
                self.command = None
                # print("Command timeout")

    def slack_callback(self, channel):
        """Callback for slack sensor for notifying when there is slack in the line"""
        if GPIO.input(channel) == GPIO.HIGH:
            # Has slack - restart slack timer and turn motor off
            self.slack_timer.reset()
            self.has_slack = True
            self.motor_off()
        elif self.has_slack:
            # Released slack - stop slack timer
            self.slack_timer.stop()
            self.has_slack = False

    def docked_callback(self, channel):
        """Docked callback notifying when winch is in its docked state"""
        if GPIO.input(channel) == GPIO.LOW:
            # In docked position - set depth to 0, put winch into stopped state
            # TODO: Error when reaching docked position when depth is greater than a meter out
            print("Docked")
            self.is_docked = True
            self.depth = 0
            self.stop()
        else:
            # Released from docked position
            self.is_docked = False

    def out_of_line_callback(self, channel):
        """
        Out of line callback notifying when the end of the line had been reached
        This callback should never be reached unless in manual operation
        """
        if GPIO.input(channel) == GPIO.LOW:
            # Out of line - put winch into stopped state
            # TODO: Set Depth to Maximum?
            self.is_out_of_line = True
            print("Out of line")
            self.stop()
        else:
            # Line pulled back in
            self.is_out_of_line = False

    def depth_callback(self, channel):
        """Rotational callback for drum of winch - called every rotation"""
        # TODO: Add into config file
        # Check rotation timer and check when the drum is rotating too fast
        if 0 < self.rotation_timer.check_time() < 0.5:
            self.rotation_timer.stop()
            self.error("Drum rotating too fast")

        # Reset timer on each rotation
        self.rotation_timer.reset()

        # Use direction flag to tell which way winch is moving, change depth accordingly
        if self.direction == "up":
            self.depth -= 1
        elif self.direction == "down":
            self.depth += 1
        else:
            # TODO: Error state here. Winch should never be moving unless up or down is called setting direction
            print("ERROR: Winch moving without known direction")
        print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))


if __name__ == "__main__":
    winch = Winch("my_winch")
    if sim:
        winch.sim = True
    winch.power_on()
