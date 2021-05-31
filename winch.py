from context import Context
from states import *
from timer import Timer
from controller import PiController


class Winch(Context):
    def __init__(self, context_name, controller, cal_file='cal_data.txt', config_file='config.json'):
        """
        Initialization for Winch parameters (not to be confused with initialization state)
        Arguments:
            controller -- hardware controller (can be PiController for raspberry pi or WinchSim for simulation
            context_name -- name of the winch
            cal_file -- drum rotation calibration file for interpolation
            config_file -- configuration file for all parameters of winch
        """
        Context.__init__(self, context_name)

        # Controller for winch hardware or simulation
        self.controller = controller

        # set callbacks for controller
        self.controller.set_slack_callback(self.slack_callback)
        self.controller.set_dock_callback(self.dock_callback)
        self.controller.set_line_callback(self.line_callback)
        self.controller.set_rotation_callback(self.rotation_callback)

        # Sequence of states that are to be executed
        self.state_sequence = []

        # Current command that has been received by the client
        self.command = None

        # Depth is measure in rotations NOT METERS
        self.depth = 0

        # Current direction winch is moving, can be "up" or "down" or empty string ""
        self.direction = ""

        # Current state of the winch
        self.is_stopped = False
        self.has_error = False
        self.error_enable = False

        # Flags for enabling and disabling sensors for manual operation
        self.slack_sensor_enable = True
        self.dock_sensor_enable = True
        self.line_sensor_enable = True

        # Timers for errors and waits
        self.slack_timer = Timer()
        self.rotation_timer = Timer()
        self.soak_timer = Timer()

        # Setup for configuration and calibration
        self.config_file = config_file
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

        # Declaration of variables set in InitState
        # UDP parameters
        self.UDP_IP = None
        self.UDP_PORT = None
        self.return_address = None
        self.sock = None

        self.default_soak_depth = None  # Meters
        self.default_soak_time = None  # Seconds
        self.client_period = None  # Period that client sends commands - Seconds
        self.main_loop_period = None  # Period of the main event loop - Seconds
        self.slack_timeout = None  # Time until error - Seconds
        self.illegal_speed_fast = None  # time for drum spinning too fast - Seconds
        self.illegal_speed_slow = None  # time for drum spinning too slow - Seconds
        self.calibration_tolerance = None  # acceptable distance from dock when docked - Meters
        self.maximum_depth = None  # Meters

    def power_on(self):
        """Start the winch - put into initialization state"""
        # Set state of winch to initialization start
        self.set_state("INIT")
        # Execute entry behavior of the current state
        self.entry_behavior(self.get_state(), [])

    def queue_command(self, command, *args):
        """Add command for state change into state sequence queue"""
        self.state_sequence.append((command, args))

    def down(self):
        """
        Set motors to pay out
        No state checking happens here such as dock, line, or slack sensors because actions need to be overridable.
        """
        if self.direction != "down":
            self.send_response("Going down...")
            self.error_enable = False  # Don't throw speed error when switching directions

        self.direction = "down"
        self.controller.down()

    def up(self):
        """
        Set motors to pay in
        No state checking happens here such as dock, line, or slack sensors because actions need to be overridable.
        """
        # print("Going up...")

        if self.direction != "up":
            self.error_enable = False  # Don't throw speed error when switching directions
            self.send_response("Going up...")
        # Note this cannot go in that if statement because if winch goes slack
        # it is not moving with a current direction. It needs to be able to get going again
        self.direction = "up"
        self.controller.up()

    def motor_off(self):
        """Turn winch motor off"""
        if self.direction != "":
            self.send_response("Motors off...")
            self.error_enable = False

        # Remove current direction
        self.direction = ""

        # Timer for rotation checking can be turned off because motor is off
        self.rotation_timer.stop()
        self.controller.off()

    def stop(self):
        """
        Put the winch into stop state.
        STOP command is added to the front of the state_sequence so it is the next state to execute
        Within StopState state_sequence is cleared

        State is inserted into state sequence instead of tradition to because this method can be called from
        receive_command which is called in a different thread causing winch to be in multiple states at once in
        different threads
        """
        self.send_response("Stopping...")
        self.state_sequence.insert(0, ("STOP", []))

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
        # Error state is looped into until the error is cleared, only handle following once
        self.send_response("ERROR:" + message)
        self.send_response("Waiting for error to be cleared...")
        # Clear state_sequence of all remaining states
        self.state_sequence = []
        self.state_sequence.insert(0, ("ERROR", []))
        self.has_error = True

    def receive_commands(self):
        """
        Command receiver that is run in a separate thread so that no command is missed
        Difficulties of receiving commands:
        The socket recvfrom method is usually blocking, this means that there was no way to tell if the client had
        disconnected in the middle of sending MANIN or MANOUT commands.
        First attempt at fixing this used socket.settimeout to set a timeout for the socket but this caused issues
        with potientially missing commands if the eventloop had not looped all the way around before the command
        timed out.
        The current solution uses the known period that the client should be sending commands. The socket is set to
        nonblocking, and each loop of this method checks how long it has been since the last command. If it is
        longer than the client period then that command has timed out.
        """
        command_timer = Timer()

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
                    self.slack_sensor_enable = False
                    self.command = None
                if self.command == "SLACKON":
                    self.slack_sensor_enable = True
                    self.command = None
                if self.command == "DOCKOFF":
                    self.dock_sensor_enable = False
                    self.command = None
                if self.command == "DOCKON":
                    self.dock_sensor_enable = True
                    self.command = None
                if self.command == "LINEOFF":
                    self.line_sensor_enable = False
                    self.command = None
                if self.command == "LINEON":
                    self.line_sensor_enable = True
                    self.command = None
                if self.command == "CLEARERROR":
                    self.send_response("Error Cleared")
                    self.has_error = False
                    self.command = None
            # recvfrom throws error when blocking is off and there is nothing to receive
            except:
                # If there has not been a command within the period the client is sending them, set to null
                if command_timer.check_time() > self.client_period:
                    self.command = None

    def change_depth(self, new_depth):
        """Change the current depth"""
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
            self.send_response("Docked")

            # Error if the winch thinks it is further than a specified distance out
            if self.depth > self.meters_to_rotations(self.calibration_tolerance):
                self.error("Winch Calibration off (was not within a meter of actual depth)")

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
        # Check rotation timer and check when the drum is rotating too fast
        if 0 < self.rotation_timer.check_time() < self.illegal_speed_fast:
            if self.error_enable:
                self.rotation_timer.stop()
                self.error("Drum rotating too fast")
            else:
                self.error_enable = True
        # Reset timer on each rotation
        self.rotation_timer.reset()

        # Use direction flag to tell which way winch is moving, change depth accordingly
        if self.direction == "up":
            self.change_depth(self.depth - 1)
        elif self.direction == "down":
            self.change_depth(self.depth + 1)
        else:
            self.error("Winch moving without known direction")
        self.send_response("Rotations: " + str(self.depth) + ", Depth: " + str(self.rotations_to_meters(self.depth)))

    def meters_to_rotations(self, meters):
        return np.interp(meters, self.cal_data["meters"], self.cal_data["rotations"])

    def rotations_to_meters(self, rotations):
        return np.interp(rotations, self.cal_data["rotations"], self.cal_data["meters"])

    def send_response(self, message):
        """Send message back to client. Only sends to last client it received commands from"""
        print(message)
        if self.return_address is not None:
            self.sock.sendto(str.encode(message), self.return_address)

    def main_loop(self):

        while True:
            # if the has an error, transition to error state
            if self.has_error:
                self.do_transition(("ERROR", []))
            else:
                # if winch is not in error state, monitors winches state to ensure it does not run away
                self.do_transition(("MONITOR", []))

                # if the state_sequence is empty then put the winch into standby and accept commands
                if not self.state_sequence:
                    self.do_transition(("STDBY", []))

                # if there is a state on the winch, transition to that state. States are to pop themselves
                else:
                    self.do_transition(self.state_sequence[0])

            sleep(self.main_loop_period)


if __name__ == "__main__":
    winch = Winch("my_winch", PiController())
    winch.power_on()
