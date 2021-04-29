import threading

from context import Context
from states import *


class Winch(Context):
    payout_rate = 0
    command_sequence = []
    target_depth = 0
    current_depth = 0
    error_message = ""

    def __init__(self, context_name):
        Context.__init__(self, context_name)

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

        self.__active = False
        self.__timer = 0

    def power_on(self):
        self.__active = True
        print("Power is ON!")
        self.set_state("INIT")
        print("Automatically entering State_Initialization!")
        self.entry_behavior(self.get_state())

    def power_off(self):
        self.__active = False
        print("Calling Power Off!")

    def queue_command(self, command):
        self.command_sequence.append(command)
        print("COMMAND QUEUE:", self.command_sequence)

    def execute_command_stack(self):
        while self.command_sequence:
            winch.do_transition(self.command_sequence.pop(0))
        winch.do_transition({"from":self.get_state().get_name(), "to":"STDBY"})

    def down(self):
        self.current_depth += 1
        self.report_position()

    def up(self):
        self.current_depth -= 1
        self.report_position()

    def report_position(self):
        print("Current Depth: ", self.current_depth, "Target Depth:", self.target_depth)

if __name__ == "__main__":
    winch = Winch("my_winch")
    winch.power_on()
