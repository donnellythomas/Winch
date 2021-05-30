# Allow for program to be run outside of a raspberry pi
try:
    import RPi.GPIO as GPIO

    sim = False
except:
    sim = True

from context import Context
from states import *
from timer import Timer
from winch_controller import PiController


class Winch(Context):
    def __init__(self, context_name, controller, cal_file='cal_data.txt'):
        """
        Initialization for Winch parameters (not to be confused with initialization state)
        Arguments:
            context_name -- name of the winch
            cal_file -- drum rotation calibration file for interpolation
        """
        Context.__init__(self, context_name)

        # Controller for winch (PiController for raspberry pi or SimController for sim
        self.controller = controller
        # set callbacks for controller
        self.controller.set_slack_callback(self.slack_callback)
        self.controller.set_dock_callback(self.dock_callback)
        self.controller.set_line_callback(self.line_callback)
        self.controller.set_rotation_callback(self.rotation_callback)

        # Sequence of states that are to be executed
        self.state_sequence = []

        # Depth is measure in rotations NOT METERS
        self.depth = 0

        # Target depth that the winch is currently paying out to
        self.target_depth = 0

        # Current command that has been received by the client
        self.command = None

        # Current direction winch is moving, can be UP or DOWN or empty string
        self.direction = ""

        # Current state of the winch
        self.is_stopped = False
        self.has_error = False
        self.error_message = ""

        # Flags for enabling and disabling sensors for manual operation
        self.slack_sensor_on = True
        self.dock_sensor_on = True
        self.line_sensor_on = True

        # Timers used for error checking
        self.slack_timer = Timer()
        self.rotation_timer = Timer()

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
        self.add_state(ErrorState("ERROR"))
        self.add_state(ManualWinchInState("MANIN"))
        self.add_state(ManualWinchOutState("MANOUT"))
        self.add_state(SoakState("SOAK"))
        self.add_state(MonitorState("MONITOR"))

        # Setup for UDP
        # TODO: pull into config file
        self.UDP_IP = ""
        self.UDP_PORT = 5008
        self.return_address = None
        # UDP socket setup
        self.sock = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.bind((self.UDP_IP, self.UDP_PORT))
        # Commands received via UDP are set to timeout after a given amount of time
        # UDP commands are set to timeout to avoid from them going stale
        # self.sock.settimeout(.1)
        self.sock.setblocking(0)

    def power_on(self):
        """Start the winch - put into initialization state"""
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
        if self.direction != "down":
            self.send_response("Going down...")
        self.direction = "down"
        self.controller.down()

    def up(self):
        """
        Set motors to pay in
        No state checking happens here such as dock, line, or slack sensors because actions need to be overridable.
        """
        # print("Going up...")

        if self.direction != "up":
            self.send_response("Going up...")
        # Note this cannot go in that if statement becuase if winch goes slack
        # it is not moving with a current direction. It needs to be able to get going again
        self.direction = "up"
        self.controller.up()

    def motor_off(self):
        """Turn winch motor off"""
        if self.direction != "":
            self.send_response("Motors off...")
        # Remove current direction
        self.direction = ""

        # Timer for rotation checking can be turned off because motor is off
        self.rotation_timer.stop()
        self.controller.off()

    def stop(self):
        """
        Put the winch into stop state.si
        STOP command is added to the front of the state_sequence so it is the next state to execute
        Within StopState state_sequence is cleared

        State is inserted into state sequence instead of tradition to because this method can be called from
        receive_command which is called in a different thread causing winch to be in multiple states at once in
        different threads
        """
        self.send_response("Stopping...")
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
        command_timer = Timer()
        client_period = 0.5

        while True:
            # Run continuously
            try:
                # Receive command in bytes
                command, self.return_address = self.sock.recvfrom(1024)  # buffer size is 1024 bytes
                command_timer.reset()
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
                if command_timer.check_time() > client_period:
                    self.command = None
                # print("Command timeout")

    def change_depth(self, new_depth):
        self.depth = new_depth
        # self.send_response(str(self.depth))

    def slack_callback(self, channel):
        """Callback for slack sensor for notifying when there is slack in the line
            channel is needed for raspi callback"""
        if self.controller.has_slack():
            # Has slack - restart slack timer and turn motor off
            self.motor_off()
            self.slack_timer.reset()
        else:
            # Released slack - stop slack timer
            # ignore if there is already no slack
            self.slack_timer.stop()

    def dock_callback(self, channel):
        """Docked callback notifying when winch is in its docked state"""
        if self.controller.is_docked():
            # In docked position - set depth to 0, put winch into stopped state
            # TODO: Error when reaching docked position when depth is greater than a meter out
            self.send_response("Docked")
            self.change_depth(0)
            self.stop()

    def line_callback(self, channel):
        """
        Out of line callback notifying when the end of the line had been reached
        This callback should never be reached unless in manual operation
        """
        if self.controller.is_out_of_line():
            # Out of line - put winch into stopped state
            # TODO: Set Depth to Maximum?
            self.send_response("Out of line")
            self.stop()

    def rotation_callback(self, channel):
        """Rotational callback for drum of winch - called every rotation"""
        # TODO: Add into config file
        # Check rotation timer and check when the drum is rotating too fast
        # if 0 < self.rotation_timer.check_time() < 0.5:
        #     self.rotation_timer.stop()
        #     self.error("Drum rotating too fast")

        # Reset timer on each rotation
        self.rotation_timer.reset()

        # Use direction flag to tell which way winch is moving, change depth accordingly
        if self.direction == "up":
            self.change_depth(self.depth - 1)
        elif self.direction == "down":
            self.change_depth(self.depth + 1)
        else:
            # TODO: Error state here. Winch should never be moving unless up or down is called setting direction
            print("ERROR: Winch moving without known direction")
        self.send_response(("Depth: " + str(self.depth) + ", Target: " + str(self.target_depth)))

    def meters_to_rotations(self, meters):
        return np.interp(meters, self.cal_data["meters"], winch.cal_data["rotations"])

    def rotations_to_meters(self, rotations):
        return np.interp(rotations, self.cal_data["rotations"], winch.cal_data["meters"])

    def send_response(self, message):
        print(message)
        if self.return_address is not None:
            self.sock.sendto(str.encode(message), self.return_address)

    def main_loop(self):
        while True:
            # if the has an error, transition to error state
            if self.has_error:
                self.do_transition("ERROR")
            else:
                # if winch is not in error state, monitors winches state to ensure it does not run away
                self.do_transition("MONITOR")

                # if the state_sequence is empty then put the winch into standby and accept commands
                if not self.state_sequence:
                    self.do_transition("STDBY")

                # if there is a state on the winch, transition to that state. States are to pop themselves
                else:
                    self.do_transition(self.state_sequence[0])

            # The idea behind this sleep is to timeout the last command
            # TODO: This could cause problems of missing commands, change on buffer research (maybe close and open socket
            sleep(.1)


if __name__ == "__main__":
    winch = Winch("my_winch", PiController())
    winch.power_on()
