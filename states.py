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


class State:
    """State base class"""

    def __init__(self, name):
        self.__name = name

    def __str__(self):
        return self.__name

    def get_name(self):
        """
        Get the name of the current state
        :return: String
        """
        return self.__name

    def on_entry_behavior(self, winch):
        """
        Entry behavior of the state
        :param winch: Context
        :return:
        """
        pass


class InitState(State):
    """
    Initialization state
    This is where configuration of winches parameters takes place, including setting pins,
    setting up GPIO, checking state of sensors, and reading configuration files
    """

    def on_entry_behavior(self, winch):
        # Set pin numbers of hardware
        winch.slack_pin = 6
        winch.dock_pin = 12
        winch.out_of_line_pin = 17
        winch.depth_pin = 21
        winch.up_pin = 23
        winch.down_pin = 24

        if not winch.sim:
            # GPIO pin setup
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(winch.up_pin, GPIO.OUT)
            GPIO.output(winch.up_pin, GPIO.LOW)
            GPIO.setup(winch.down_pin, GPIO.OUT)
            GPIO.output(winch.down_pin, GPIO.LOW)
            GPIO.setup(winch.slack_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(winch.dock_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(winch.out_of_line_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Setup for callbacks
            GPIO.add_event_detect(winch.slack_pin, GPIO.BOTH, callback=winch.slack_callback)
            GPIO.add_event_detect(winch.dock_pin, GPIO.BOTH, callback=winch.docked_callback)
            GPIO.add_event_detect(winch.out_of_line_pin, GPIO.BOTH, callback=winch.out_of_line_callback)
            GPIO.add_event_detect(21, GPIO.FALLING, callback=winch.depth_callback, bouncetime=100)

            # Determine current state of sensors (slack, dock, and line)
            if GPIO.input(winch.slack_pin) == GPIO.HIGH:
                winch.has_slack = True
                winch.slack_timer.start()
            if GPIO.input(winch.dock_pin) == GPIO.LOW:
                winch.is_docked = True
            if GPIO.input(winch.out_of_line_pin) == GPIO.LOW:
                winch.is_out_of_line = True

        # Activate all sensors
        winch.dock_sensor_on = True
        winch.line_sensor_on = True
        winch.slack_sensor_on = True

        # Read configuration file for meter to rotation interpolation
        with file(winch.cal_file) as f:
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
        command_thread.start()

        # Put winch into standby state
        winch.queue_command("STDBY")
        winch.do_transition(winch.state_sequence.pop(0))


class StdbyState(State):
    """
    Standby State
    Currently this state serves two purposes which can (maybe should) be separated into two
    The first purpose is to read the the current command from the client and transition into the
    given state.
    The second purpose is to monitor error timers and put the winch into an error state

    This state is deviated from the original model. The original model has each state check the current command
    and set the state accordingly, this required a lot of repetition and problems when small things were changed.
    It also required errors to be checked for in multiple places as there were holding patterns within some states
    such as downcast and upcast.

    Instead, I chose to create the event loop so that no state is in a holding pattern, and used standby as a state
    that is passed through every cycle (this is the part that could be pulled into its own state). This uses the
    state_sequence to check what the current state is, and when a state is finished, it pops itself off the stack.
    As Standby is passed through continuously, errors can be checked for frequently, and states that interrupt the
    current state_sequence can be easily added to the stack and executed (Before being this, I had trouble putting
    the winch into a stop or error state from anywhere in the cycle as it could not just be transitioned to when
    called within the receive_command thread). Also, before this change I was running into recursion issues as I
    would be transitioning into other states from within the middle of different state, this was more of an
    implementation problem on my end though I believe.
    """

    def on_entry_behavior(self, winch):
        # Run continuously
        while True:

            # Error monitoring
            # TODO: Pull into own state?
            if winch.slack_timer.check_time() > 20:
                winch.error("Winch has been slack for too long")
            if winch.direction != "" and winch.rotation_timer.check_time() > 3:
                winch.error("Drum is not rotating")

            # if command sequence is empty
            if not winch.state_sequence:
                # Set the command locally, commands were timing out withing the middle
                # of this loop and raising exceptions
                # TODO: This can possibly be changed if UDP buffer can be cleared
                command = winch.command
                # When state sequence is empty then winch is officially in standby
                winch.set_state("STDBY")

                if command is not None:
                    # print(command)
                    try:
                        # Cast is the only command with multiple arguments and always has 4 parts
                        if len(command.split()) == 4:
                            meters = float(command.split()[1])
                            soak_depth = float(command.split()[2])
                            soak_time = float(command.split()[3])

                            # Ignore command if depth is negative or too deep
                            if meters < 0 or meters > 50 or soak_depth > 50:
                                raise Exception
                            # If soak depth is 0 or negative default to 1.1 meters
                            # TODO: Add to config
                            if soak_depth <= 0:
                                winch.soak_depth = np.interp(1.1, winch.cal_data["meters"], winch.cal_data["rotations"])
                            else:
                                winch.soak_depth = np.interp(soak_depth, winch.cal_data["meters"],
                                                             winch.cal_data["rotations"])
                            # If soak time is 0 or negative default to 60 seconds
                            if soak_time <= 0:
                                winch.soak_time = 60
                            else:
                                winch.soak_time = soak_time

                            command = command.split()[0]
                            # TODO: Create method for interpolation?
                            winch.target_depth = np.interp(meters, winch.cal_data["meters"],
                                                           winch.cal_data["rotations"])
                        # Add command to queue for execution on next cycle
                        winch.queue_command(command)
                    except:
                        # Print exception and ignore commands
                        traceback.print_exc()
                        print("Command not valid")
            else:
                # If state_sequence has state, transition into that state
                winch.do_transition(winch.state_sequence[0])
            # The idea behind this sleep is to timeout the last command
            # TODO: This could cause problems of missing commands, change on buffer research
            sleep(.1)


class CastState(State):
    """Automatically soak, downcast, and upcast to a specific depth"""

    def on_entry_behavior(self, winch):
        print("Casting to %d..." % winch.target_depth)
        winch.queue_command("SOAK")
        winch.queue_command("DOWNCAST")
        winch.queue_command("UPCAST")
        winch.queue_command("READDATA")
        winch.queue_command("STOP")
        # Pop off the Cast state allowing soak to begin
        winch.state_sequence.pop(0)


class ManualWinchOutState(State):
    """Manually winch in - state requires continuous command input so is popped every time"""

    def on_entry_behavior(self, winch):
        # If the current command is None that means MANOUT timed out winch should stop
        # This should only be occurring when connection to client is lost
        if winch.command is None:
            winch.stop()

        # Do not winch out if winch has slack and slack sensor is on
        if not winch.has_slack or not winch.slack_sensor_on:
            # Do not winch down if winch is out of line, depth is > 50, and line sensor is on
            if not winch.line_sensor_on or (not winch.is_out_of_line and winch.depth < 417):  # 417 is 50 meters
                winch.down()
            else:
                # Turns off motor when maximum depth is reached
                # TODO: Could be moved to future error checking state, maybe error? Should be docked
                winch.motor_off()
        winch.state_sequence.pop(0)


class ManualWinchInState(State):
    """Manually winch out - state requires continuous command input so is popped every time"""

    def on_entry_behavior(self, winch):
        # If the current command is None that means MANIN timed out winch should stop
        # This should only be occurring when connection to client is lost
        if winch.command is None:
            winch.stop()

        # Do not winch in if winch has slack and slack sensor is on
        if not winch.has_slack or not winch.slack_sensor_on:
            # Do not winch down if winch is docked, depth is > 0, and dock sensor is on
            if not winch.dock_sensor_on or (not winch.is_docked and winch.depth > 0):
                winch.up()
            else:
                # Turns off motor when depth is < 0
                # TODO: Could be moved to future error checking state, maybe error? Should be docked
                winch.motor_off()
        winch.state_sequence.pop(0)


class DownCastState(State):
    """ Downcast while depth is less than target depth """

    def on_entry_behavior(self, winch):
        # Target depth reached
        if winch.depth >= winch.target_depth:
            winch.motor_off()
            winch.state_sequence.pop(0)
            return

        # TODO: Could be moved to future error/sensor checking state
        if not winch.has_slack and not winch.is_out_of_line:
            winch.down()
        else:
            winch.motor_off()


class SoakState(State):
    """ Soak CTD at specified soak depth for specified soak time """

    def on_entry_behavior(self, winch):
        # Target soak depth reached
        if winch.depth >= winch.soak_depth:
            winch.motor_off()
            print("Soaking...")
            # Soak
            sleep(winch.soak_time)
            winch.state_sequence.pop(0)
            return

        if not winch.has_slack and not winch.is_out_of_line:
            winch.down()
        else:
            winch.motor_off()


class UpCastState(State):
    """ Upcast while depth is greater than 0 """

    def on_entry_behavior(self, winch):
        # print("Going up to 0...")

        # Dock reached
        if winch.depth <= 0:
            winch.state_sequence.pop(0)
        if not winch.has_slack:
            winch.up()
        else:
            winch.motor_off()


class ReadDataState(State):
    """ Read Data from CTD, Not used currently """

    def on_entry_behavior(self, winch):
        # if winch.is_docked:
        #   winch.error("Winch not docked, cannot read data")
        print("C:", winch.conductivity, "T:", winch.temp, "D:", winch.depth)
        winch.state_sequence.pop(0)


class ErrorState(State):
    """
    Error state of winch
    Error message is printed and winch is kept in error state until error is cleared by client
    """

    def on_entry_behavior(self, winch):
        # Motors are turned off, error is flagged, state_sequence is cleared
        winch.motor_off()
        winch.has_error = True
        command = None
        winch.state_sequence = []
        print("ERROR:" + winch.error_message)
        winch.error_message = ""
        # Holds in error state until cleared
        while winch.has_error:
            print("Waiting for error to be cleared")
            sleep(1)
            pass


class StopState(State):
    """
    Stop state of winch
    Stops motor, clears state_sequence
    """
    def on_entry_behavior(self, winch):
        print("Stopping...")
        winch.motor_off()
        winch.state_sequence = []
        command = None
