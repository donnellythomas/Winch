from time import sleep
import threading
import traceback
import socket

# If winch is in simulation RPi cannot be imported
try:
    import RPi.GPIO as GPIO
except:
    pass
import numpy as np
import json


class State:
    """State base class"""

    def __init__(self, name):
        self.__name = name

    def __str__(self):
        return self.__name

    def get_name(self):
        """Get the name of the current state"""
        return self.__name

    def on_entry_behavior(self, winch, *args):
        """
        Entry behavior of the state
        Arguments:
            winch -- context for the state
        """
        pass


class InitState(State):
    """
    Initialization state
    This is where configuration of winches parameters takes place, including setting pins,
    setting up GPIO, checking state of sensors, and reading configuration and calibration files
    """

    def on_entry_behavior(self, winch, *args):

        # Read configuration file and set all parameters
        with open(winch.config_file) as config:
            config = json.load(config)
        winch.UDP_IP = config["UDP_IP"]
        winch.UDP_PORT = config["UDP_PORT"]
        winch.default_soak_depth = config["default_soak_depth"]
        winch.default_soak_time = config["default_soak_time"]
        winch.client_period = config["client_period"]
        winch.main_loop_period = config["main_loop_period"]
        winch.slack_timeout = config["slack_timeout"]
        winch.illegal_speed_fast = config["illegal_speed_fast"]
        winch.illegal_speed_slow = config["illegal_speed_slow"]
        winch.calibration_tolerance = config["calibration_tolerance"]
        winch.maximum_depth = config["maximum_depth"]
        winch.cal_file = config["cal_file"]

        # UDP socket setup
        winch.sock = socket.socket(socket.AF_INET,  # Internet
                                   socket.SOCK_DGRAM)  # UDP
        winch.sock.bind((winch.UDP_IP, winch.UDP_PORT))

        # UDP needs to be nonblocking so we know when client disconnects
        winch.sock.setblocking(False)

        # Set all callbacks of controller
        winch.controller.set_slack_callback(winch.slack_callback)
        winch.controller.set_dock_callback(winch.dock_callback)
        winch.controller.set_line_callback(winch.line_callback)
        winch.controller.set_rotation_callback(winch.rotation_callback)

        # Enable all sensors
        winch.dock_sensor_enable = True
        winch.line_sensor_enable = True
        winch.slack_sensor_enable = True

        # Read configuration file for meter to rotation interpolation
        with open(winch.cal_file) as f:
            while True:
                try:
                    rot, m = f.readline().split()
                    winch.cal_data['rotations'].append(float(rot))
                    winch.cal_data['meters'].append(float(m))
                except:  # end of file
                    print("Finished reading data.")
                    print("Read %d values." % len(winch.cal_data["rotations"]))
                    break

        # Start the thread for receiving commands
        command_thread = threading.Thread(target=winch.receive_commands)
        # Shuts down thread when main thread is shut down
        command_thread.daemon = True
        command_thread.start()

        # Start the main loop
        winch.main_loop()


class StdbyState(State):
    """Get commands that receive commands provides, interprets and runs them"""

    def on_entry_behavior(self, winch, *args):
        # Set the command locally, commands were changing withing the middle
        # of this loop and raising exceptions
        command = winch.command
        if command is not None:
            # When state sequence is empty then winch is officially in standby
            try:
                # Cast is the only command with multiple arguments and always has 4 parts
                if len(command.split()) == 4:
                    meters = float(command.split()[1])
                    soak_depth = float(command.split()[2])
                    soak_time = float(command.split()[3])

                    # Ignore command if depth is negative or too deep
                    if meters < 0 or meters > winch.maximum_depth or soak_depth < 0:
                        raise Exception
                    # If negative default to 1.1 meters
                    # TODO: Add to config
                    if soak_depth < 0:
                        soak_depth = winch.meters_to_rotations(winch.default_soak_depth)
                    else:
                        soak_depth = winch.meters_to_rotations(soak_depth)
                    # If negative default to 60 seconds
                    if soak_time < 0:
                        soak_time = winch.default_soak_time
                    else:
                        soak_time = soak_time

                    command = command.split()[0]

                    target_depth = winch.meters_to_rotations(meters)
                    winch.queue_command(command, target_depth, soak_depth, soak_time)
                else:
                    # Add command to queue for execution on next cycle
                    winch.queue_command(command)
            except:
                # Print exception and ignore commands
                traceback.print_exc()
                print("Command not valid")
                winch.command = None
        else:
            # Do not turn the motor off unless the command is none
            # States will take control of the motor but if MANIN or MANOUT disconnect
            # the motor needs to stop
            # if it stops every time then the motor will be stopping and starting over and over
            winch.motor_off()


class MonitorState(State):
    def on_entry_behavior(self, winch, *args):
        # Error monitoring
        if winch.slack_timer.check_time() > winch.slack_timeout:
            winch.error("Winch has been slack for too long")
        if winch.direction != "" and winch.rotation_timer.check_time() > winch.illegal_speed_slow:
            winch.error("Drum is not rotating")


class CastState(State):
    """Automatically soak, downcast, and upcast to a specific depth"""

    def on_entry_behavior(self, winch, *args):
        winch.send_response("Casting to " + str(args[0]) + "...")
        winch.queue_command("SOAK", args[1], args[2])
        winch.queue_command("DOWNCAST", args[0])
        winch.queue_command("UPCAST")
        winch.queue_command("STOP")
        # Pop off the Cast state allowing soak to begin
        winch.state_sequence.pop(0)


class ManualWinchOutState(State):
    """Manually winch in - state requires continuous command input so is popped every time"""

    def on_entry_behavior(self, winch, *args):
        # If the current command is None that means MANOUT timed out winch should stop
        # This should only be occurring when connection to client is lost

        # Do not winch out if winch has slack and slack sensor is on
        if not winch.controller.has_slack() or not winch.slack_sensor_enable:
            # Do not winch down if winch is out of line, depth is > 50, and line sensor is on
            if not winch.line_sensor_enable or (
                    not winch.controller.is_out_of_line() and (
                    winch.depth < winch.meters_to_rotations(winch.maximum_depth))):
                winch.down()
            else:
                # Turns off motor when maximum depth is reached
                winch.motor_off()
        winch.state_sequence.pop(0)


class ManualWinchInState(State):
    """Manually winch out - state requires continuous command input so is popped every time"""

    def on_entry_behavior(self, winch, *args):
        # If the current command is None that means MANIN timed out winch should stop
        # This should only be occurring when connection to client is lost

        # Do not winch in if winch has slack and slack sensor is on
        if not winch.controller.has_slack() or not winch.slack_sensor_enable:
            # Do not winch down if winch is docked, depth is > 0, and dock sensor is on
            if not winch.dock_sensor_enable or (not winch.controller.is_docked() and winch.depth > 0):
                winch.up()
            else:
                # Turns off motor when depth is < 0
                winch.motor_off()
        winch.state_sequence.pop(0)


class DownCastState(State):
    """ Downcast while depth is less than target depth """

    def on_entry_behavior(self, winch, *args):
        # Target depth reached
        target_depth = args[0]
        if winch.depth >= target_depth:
            winch.motor_off()
            winch.state_sequence.pop(0)
            return
        if not winch.controller.has_slack() and not winch.controller.is_out_of_line():
            winch.down()
        else:
            winch.motor_off()


class SoakState(State):
    """ Soak CTD at specified soak depth for specified soak time """

    def on_entry_behavior(self, winch, *args):
        # Target soak depth reached
        soak_depth = args[0]
        soak_time = args[1]
        if winch.depth >= soak_depth:
            winch.motor_off()
            if winch.soak_timer.check_time() == 0:  # timer hasn't started yet
                winch.send_response("Soaking...")
            winch.soak_timer.start()
            # Soak
            if soak_time < winch.soak_timer.check_time():
                winch.soak_timer.stop()
                winch.state_sequence.pop(0)
            return

        if not winch.controller.has_slack() and not winch.controller.is_out_of_line():
            winch.down()
        else:
            winch.motor_off()


class UpCastState(State):
    """ Upcast while depth is greater than 0 """

    def on_entry_behavior(self, winch, *args):

        # Dock reached
        if winch.depth <= 0:
            winch.state_sequence.pop(0)
        if not winch.controller.has_slack():
            winch.up()
        else:
            winch.motor_off()


class ErrorState(State):
    """
    Error state of winch
    Error message is printed and winch is kept in error state until error is cleared by client
    """

    def on_entry_behavior(self, winch, *args):
        # Motors are turned off, error is flagged, state_sequence is cleared
        winch.motor_off()
        # If the error has been removed release from error state
        if not winch.has_error:
            winch.rotation_timer.stop()
            winch.slack_timer.stop()
            winch.state_sequence.pop(0)


class StopState(State):
    """
    Stop state of winch
    Stops motor, clears state_sequence
    """

    def on_entry_behavior(self, winch, *args):
        print("Stopping...")
        winch.motor_off()
        winch.state_sequence = []
        winch.command = None
