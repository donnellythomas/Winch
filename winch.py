import threading
from time import sleep

from context import Context
from states import *


class Winch(Context):
    payout_rate = 0
    command_sequence = []
    target_depth = 0
    depth = 0
    conductivity = 0;
    temp = 0

    error_message = ""

    def __init__(self, context_name):
        Context.__init__(self, context_name)
        # add all the states to the winch
        self.add_state(InitState("INIT"))
        self.add_state(StdbyState("STDBY"))
        self.add_state(CastState("CAST"))
        self.add_state(HelpState("HELP"))
        self.add_state(DownCastState("DOWNCAST"))
        self.add_state(UpCastState("UPCAST"))
        self.add_state(ReadDataState("READDATA"))
        self.add_state(ErrorState("ERROR"))
        self.add_state(ManualWinchInState("MANIN"))
        self.add_state(ManualWinchOutState("MANOUT"))

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
        print("Calling Power Off!")

    def queue_command(self, command):
        """
        Queue a transition command to the execution stack
        :param command: Map<String,String>
        :return:
        """
        self.command_sequence.append(command)
        # print("COMMAND QUEUE:", self.command_sequence)

    def execute_command_stack(self):
        """
        Pop off and run the commands in the command stack on at a time
        :return:
        """
        while self.command_sequence:
            winch.do_transition(self.command_sequence.pop(0))
        winch.do_transition({"from": self.get_state().get_name(), "to": "STDBY"})

    def down(self):
        """
        Winch out
        :return:
        """
        sleep(.5)
        self.depth += 1
        self.report_position()

    def up(self):
        """
        Winch in
        :return:
        """
        if self.depth > 0:
            sleep(.5)
            self.depth -= 1
            self.report_position()
        else:
            print("already on surface")

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
        self.do_transition({"from": self.get_state().get_name(), "to": "ERROR"})


if __name__ == "__main__":
    winch = Winch("my_winch")
    winch.power_on()
