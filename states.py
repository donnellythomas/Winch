from abc import ABCMeta, abstractmethod
import socket
from time import sleep
from time import time

try:
    import RPi.GPIO as GPIO
except:
    pass


class State(metaclass=ABCMeta):
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

    @abstractmethod
    def on_entry_behavior(self, winch):
        """
        Entry behavior of the state
        :param winch: Context
        :return:
        """
        pass

    @abstractmethod
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

        # GPIO.setmode(GPIO.BCM)
        #
        # # Create a dictionary called pins to store the pin number, name, and pin state:
        # winch.pins = {
        #    23 : {'name' : 'GPIO 23 (up)', 'state' : GPIO.LOW},
        #    24 : {'name' : 'GPIO 24 (down)', 'state' : GPIO.LOW}
        #    }
        #
        # # Set each pin as an output and make it low:
        # for pin in winch.pins:
        #    GPIO.setup(pin, GPIO.OUT)
        #    GPIO.output(pin, GPIO.LOW)
        #
        #
        #
        # #winch.payout_rate = int(input("Payout rate: "))

        UDP_IP = "127.0.0.1"
        UDP_PORT = 5005

        winch.sock = socket.socket(socket.AF_INET,  # Internet
                                   socket.SOCK_DGRAM)  # UDP
        winch.sock.bind((UDP_IP, UDP_PORT))
        winch.sock.settimeout(0.01)
        winch.queue_command({"from": "INIT", "to": "STDBY"})
        winch.execute_command_stack()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class StdbyState(State):

    def on_entry_behavior(self, winch):
        """
        Standby waiting for commands
        :param winch: Context
        :return:
        """
        command = None
        while command is None:
            command = winch.receive_command()
        winch.queue_command({"from": "STDBY", "to": command})
        winch.execute_command_stack()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class CastState(State):

    def on_entry_behavior(self, winch):
        """
        Automatically downcast and upcast to a specific depth
        :param winch: Context
        :return:
        """
        winch.target_depth = int(input("Enter depth: "))
        winch.queue_command({"from": "CAST", "to": "DOWNCAST"})
        winch.queue_command({"from": "DOWNCAST", "to": "UPCAST"})
        winch.queue_command({"from": "UPCAST", "to": "READDATA"})
        winch.execute_command_stack()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ManualWinchOutState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch out n meters
        :param winch: Context
        :return:
        """

        while True:
            cmd = (input("Start, STOP or EXIT: "))
            if cmd == "START":
                winch.down()
            elif cmd == "STOP":
                winch.stop()
            elif cmd == "EXIT":
                break
            else:
                print("Invalid input:", cmd)
                winch.stop()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ManualWinchInState(State):
    def on_entry_behavior(self, winch):
        """
        Manually winch in n meters
        :param winch: Context
        :return:
        """

        winch.up()
        while winch.receive_command() == "MANIN":
            i = i+1
            pass
        winch.stop()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class DownCastState(State):
    def on_entry_behavior(self, winch):
        """
        Downcast while less than target
        :param winch:
        :return:
        """
        winch.down()
        while winch.receive_command() == "MANOUT":
            pass
        winch.stop()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class UpCastState(State):
    def on_entry_behavior(self, winch):
        """
        Upcast while greater than target
        :param winch: Context
        :return:
        """
        while winch.depth > 0:
            winch.up()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ReadDataState(State):
    def on_entry_behavior(self, winch):
        """
        Read CTD info from winch
        :param winch: Context
        :return:
        """
        if winch.depth != 0:
            winch.error("Winch not on surface, cannot read data")

        print("C:", winch.conductivity, "T:", winch.temp, "D:", winch.depth)

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ErrorState(State):
    def on_entry_behavior(self, winch):
        """
        Handle errors that occur
        :param winch: Context
        :return:
        """
        winch.command_sequence = []
        print("ERROR:", winch.error_message)
        winch.error_message = ""
        winch.queue_command({"from": "ERROR", "to": "STDBY"})
        winch.execute_command_stack()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class HelpState(State):

    def on_entry_behavior(self, winch):
        """
        Print the available state commands
        :param winch: Context
        :return:
        """
        winch.print_states()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)
