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
        winch.depth_pin = 21
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
            GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Slack sensor
            # GPIO.add_event_detect(12, GPIO.BOTH, callback=dockstop)

            GPIO.add_event_detect(winch.slack_pin, GPIO.BOTH, callback=winch.slack_callback)
            GPIO.add_event_detect(winch.dock_pin, GPIO.BOTH, callback=winch.docked_callback)
            GPIO.add_event_detect(winch.out_of_line_pin, GPIO.BOTH, callback=winch.out_of_line_callback)
            GPIO.add_event_detect(21, GPIO.FALLING, callback=winch.depth_callback, bouncetime=100)

            # If line has slack initiall set has_slack to true;
            if GPIO.input(winch.slack_pin) == GPIO.HIGH:
                winch.has_slack = True
            if GPIO.input(winch.dock_pin) == GPIO.LOW:
                winch.is_docked = True
            if GPIO.input(winch.out_of_line_pin) == GPIO.LOW:
                winch.is_out_of_line = True

        winch.dock_sensor_on = True
        winch.line_sensor_on = True
        winch.slack_sensor_on = True

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
            winch.is_stopped = False
            winch.set_state("STDBY")
            print("Entered Standby...")
            # sleep to time out any commands that have already happened
            sleep(0.2)

            while winch.command is None:
                pass

            try:
                if len(winch.command.split()) == 4:
                    meters = float(winch.command.split()[1])
                    soak_depth = float(winch.command.split()[2])
                    soak_time = float(winch.command.split()[3])
                    if meters < 0 or meters > 50 or soak_depth > 50:
                        raise Exception

                    if soak_depth < 0:
                        winch.soak_depth = np.interp(1.1, winch.cal_data["meters"], winch.cal_data["rotations"])
                    else:
                        winch.soak_depth = np.interp(soak_depth, winch.cal_data["meters"], winch.cal_data["rotations"])
                    if soak_time < 0:
                        winch.soak_time = 60
                    else:
                        winch.soak_time = soak_time

                    winch.command = winch.command.split()[0]
                    winch.target_depth = np.interp(meters, winch.cal_data["meters"], winch.cal_data["rotations"])

                winch.queue_command(winch.command)
                winch.execute_state_stack()
            except Exception as e:
                traceback.print_exc()
                print(e)
                print("Command not valid")


class CastState(State):

    def on_entry_behavior(self, winch):
        """
        Automatically downcast and upcast to a specific depth
        :param winch: Context
        :return:
        """
        print("Casting to %d..." % winch.target_depth)
        winch.queue_command("SOAK")
        winch.queue_command("DOWNCAST")
        winch.queue_command("UPCAST")
        winch.queue_command("READDATA")
        winch.queue_command("STOP")

        winch.execute_state_stack()


class ManualWinchOutState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch out n meters
        :param winch: Context
        :return:
        """
        print("Entered MANOUT")
        print("has slack: " + str(winch.has_slack))
        print("is out of line: " + str(winch.is_out_of_line))

        if not (winch.has_slack or winch.slack_sensor_on):
            if not winch.line_sensor_on or (not winch.is_out_of_line and winch.depth < 417):  # 417 is 50 meters
                print("winching down")
                winch.down()
            else:
                winch.motors_off()


class ManualWinchInState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch in n meters
        :param winch: Context
        :return:
        """
        if not (winch.has_slack or winch.slack_sensor_on):
            if not winch.dock_sensor_on or (not winch.is_docked and winch.depth > 0):
                winch.up()
            else:
                winch.motors_off()


class DownCastState(State):
    def on_entry_behavior(self, winch):
        """
        Downcast while less than target
        :param winch:
        :return:
        """
        print("Going down to %d..." % winch.target_depth)

        while winch.depth < winch.target_depth and not winch.is_stopped:
            if not winch.has_slack and not winch.is_out_of_line:
                winch.down()
        winch.motors_off()


class SoakState(State):
    def on_entry_behavior(self, winch):
        """
        Upcast while greater than target
        :param winch: Context
        :return:
        """
        print("Going up to 0...")
        while winch.depth < winch.soak_depth and not winch.is_stopped:
            if not winch.has_slack and not winch.is_out_of_line:
                winch.down()
        winch.motors_off()
        sleep(winch.soak_time)


class UpCastState(State):
    def on_entry_behavior(self, winch):
        """
        Upcast while greater than target
        :param winch: Context
        :return:
        """
        print("Going up to 0...")
        while winch.depth > 0 and not winch.is_stopped:
            if not winch.has_slack and not winch.is_docked:
                winch.up()
        winch.motors_off()


class ReadDataState(State):
    def on_entry_behavior(self, winch):
        """
        Read CTD info from winch
        :param winch: Context
        :return:
        """
        # if winch.is_docked:
        #   winch.error("Winch not docked, cannot read data")
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
        winch.is_stopped = True
        winch.motors_off()
        winch.state_sequence = []
        winch.command = None
