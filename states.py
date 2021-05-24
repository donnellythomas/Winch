import socket
from time import sleep
from time import time
import threading
import traceback

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
    def on_entry_behavior(self, winch):
        """
        Set the default parameters of the winch
        :param winch: Context
        :return:
        """
        # Initialize GPIO

        #
        # # Create a dictionary called pins to store the pin number, name, and pin state:
        winch.slack_pin = 6
        winch.dock_pin = 12
        winch.out_of_line_pin = 17
        winch.up_pin = 23
        winch.down_pin = 24
        if not winch.sim:
            GPIO.setmode(GPIO.BCM)
            ## Set each pin as an output and make it low:
            GPIO.setup(winch.up_pin, GPIO.OUT)
            GPIO.output(winch.up_pin, GPIO.LOW)
            GPIO.setup(winch.down_pin, GPIO.OUT)
            GPIO.output(winch.down_pin, GPIO.LOW)
            GPIO.setup(winch.slack_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(winch.dock_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(winch.out_of_line_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Slack sensor
            # GPIO.add_event_detect(12, GPIO.BOTH, callback=dockstop)

            GPIO.add_event_detect(winch.slack_pin, GPIO.BOTH, callback=winch.slack_callback)
            GPIO.add_event_detect(winch.dock_pin, GPIO.BOTH, callback=winch.docked_callback)
            GPIO.add_event_detect(winch.out_of_line_pin, GPIO.BOTH, callback=winch.out_of_line_callback)

            # If line has slack initiall set has_slack to true;
            if GPIO.input(winch.slack_pin) == GPIO.HIGH:
                winch.has_slack = True

        with file(winch.cal_file) as f:
            while True:
                try:
                    rot, m = f.readline().split()
                    winch.cal_data['rotations'].append(float(rot))
                    winch.cal_data['meters'].append(float(m))
                except:
                    print("Finished reading data.")
                    print("Read %d values." % len(winch.cal_data["rotations"]))
                    break

        command_thread = threading.Thread(target=winch.receive_commands)
        command_thread.start()

        winch.queue_command("STDBY")
        winch.execute_state_stack()


class StdbyState(State):

    def on_entry_behavior(self, winch):
        """
        Standby waiting for commands
        :param winch: Context
        :return:
        """
        while True:
            winch.set_state("STDBY")
            print("Entered Standby...")
            # sleep to time out any commands that have already happened
            sleep(0.2)

            while winch.command is None:
                pass

            try:
                if len(winch.command.split()) == 2:
                    meters = long(winch.command.split()[1])
                    if meters < 0 or meters > 50:
                        raise Exception
                    winch.command = winch.command.split()[0]
                    winch.target_depth = np.interp(meters, winch.cal_data["meters"], winch.cal_data["rotations"])

                winch.queue_command(winch.command)
                winch.execute_state_stack()
            except Exception as e:
                traceback.print_exc()
                print(e)
                print("Command not valid")
                winch.do_transition("STDBY")


class CastState(State):

    def on_entry_behavior(self, winch):
        """
        Automatically downcast and upcast to a specific depth
        :param winch: Context
        :return:
        """
        print("Casting to %d..." % winch.target_depth)
        winch.queue_command("DOWNCAST")
        winch.queue_command("UPCAST")
        winch.queue_command("READDATA")
        winch.execute_state_stack()


class ManualWinchOutState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch out n meters
        :param winch: Context
        :return:
        """
        if not (winch.has_slack or winch.is_out_of_line):
            winch.down()


class ManualWinchInState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch in n meters
        :param winch: Context
        :return:
        """
        if not (winch.has_slack or winch.is_docked):
            winch.up()


class DownCastState(State):
    def on_entry_behavior(self, winch):
        """
        Downcast while less than target
        :param winch:
        :return:
        """
        print("Going down to %d..." % winch.target_depth)
        while winch.depth < winch.target_depth:
            if winch.direction != "down" and not winch.is_out_of_line:
                winch.down()
            print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))


class UpCastState(State):
    def on_entry_behavior(self, winch):
        """
        Upcast while greater than target
        :param winch: Context
        :return:
        """
        print("Going up to 0...")
        while winch.depth > 0 and not winch.has_slack:
            if winch.direction != "up" and not winch.is_docked:
                winch.up()
            print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))


class ReadDataState(State):
    def on_entry_behavior(self, winch):
        """
        Read CTD info from winch
        :param winch: Context
        :return:
        """
        if winch.is_docked():
            winch.error("Winch not docked, cannot read data")
        print("C:", winch.conductivity, "T:", winch.temp, "D:", winch.depth)


class ErrorState(State):
    def on_entry_behavior(self, winch):
        """
        Handle errors that occur
        :param winch: Context
        :return:
        """
        winch.state_sequence = []
        print("ERROR:", winch.error_message)
        winch.error_message = ""
        winch.queue_command("STDBY")
        winch.execute_state_stack()


class StopState(State):

    def on_entry_behavior(self, winch):
        """
        Print the available state commands
        :param winch: Context
        :return:
        """
        print("Stopping...")
        winch.has_slack = True
        winch.motors_off()
        winch.state_sequence = []
        winch.command = None
