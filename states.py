import socket
from time import sleep
from time import time
import threading

try:
    import RPi.GPIO as GPIO
except:
    pass


class State():
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

    def on_exit_behavior(self, winch):
        """
        Exits behavior of the state
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
        winch.dock_pin = 17
        winch.up_pin = 23
        winch.down_pin = 24
        if not winch.sim:
            GPIO.setmode(GPIO.BCM)
            ## Set each pin as an output and make it low:
            GPIO.setup(winch.up_pin, GPIO.OUT)
            GPIO.output(winch.up_pin, GPIO.LOW)
            GPIO.setup(winch.down_pin, GPIO.OUT)
            GPIO.output(winch.down_pin, GPIO.LOW)

            # Slack sensor
            GPIO.setup(winch.slack_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(winch.slack_pin, GPIO.BOTH)

            GPIO.setup(winch.dock_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(winch.dock_pin, GPIO.BOTH)
        
        with file(winch.cal_file) as f:
            while True:
                try:
                    rot,m = f.readline().split()
                    winch.cal_data['rotations'].append(rot)
                    winch.cal_data['meters'].append(m)
                except:
                    print("Finished reading data.")
                    print("Read %d values." % len(winch.cal_data["rotations"]))
                    break
        
        
        command_thread = threading.Thread(target=winch.receive_commands)
        command_thread.start()

        winch.queue_command({"from": "INIT", "to": "STDBY"})
        winch.execute_state_stack()


class StdbyState(State):

    def on_entry_behavior(self, winch):
        """
        Standby waiting for commands
        :param winch: Context
        :return:
        """

        while winch.command is None:
            pass

        if len(winch.command.split()) == 2:
            winch.target_depth = int(winch.command.split()[1])
            winch.command = winch.command.split()[0]

        winch.queue_command({"from": "STDBY", "to": winch.command})
        winch.execute_state_stack()


class CastState(State):

    def on_entry_behavior(self, winch):
        """
        Automatically downcast and upcast to a specific depth
        :param winch: Context
        :return:
        """
        print("Casting to %d..." % winch.target_depth)
        winch.queue_command({"from": "CAST", "to": "DOWNCAST"})
        winch.queue_command({"from": "DOWNCAST", "to": "UPCAST"})
        winch.queue_command({"from": "UPCAST", "to": "READDATA"})
        winch.execute_state_stack()


class ManualWinchOutState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch out n meters
        :param winch: Context
        :return:
        """
        print("Going down...")

        while winch.command == "MANOUT":
            winch.down()
        print("Stopping...")
        winch.stop()


class ManualWinchInState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch in n meters
        :param winch: Context
        :return:
        """
        print("Going up...")
        while winch.command == "MANIN":
            winch.up()
        print("Stopping...")
        winch.stop()


class DownCastState(State):
    def on_entry_behavior(self, winch):
        """
        Downcast while less than target
        :param winch:
        :return:
        """
        print("Going down to %d..." % winch.target_depth)
        while winch.depth < winch.target_depth:
            if winch.command == "STOP":
                break
            winch.down()
            print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))

        print("Stopping...")
        winch.stop()


class UpCastState(State):
    def on_entry_behavior(self, winch):
        """
        Upcast while greater than target
        :param winch: Context
        :return:
        """
        print("Going up to 0...")
        while winch.depth > 0:
            if winch.command == "STOP":
                break
            winch.up()
            print("Depth: %d, Target: %d" % (winch.depth, winch.target_depth))
        print("Stopping...")
        winch.stop()


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
        sleep(0.)


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
        winch.queue_command({"from": "ERROR", "to": "STDBY"})
        winch.execute_state_stack()


class StopState(State):

    def on_entry_behavior(self, winch):
        """
        Print the available state commands
        :param winch: Context
        :return:
        """
        winch.motors_off()
        winch.state_sequence = []
        winch.command = None
