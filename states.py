from abc import ABCMeta, abstractmethod


class State(metaclass=ABCMeta):
    """State base class"""

    def __init__(self, name):
        self.__name = name

    def __str__(self):
        return self.__name

    def get_name(self):
        return self.__name

    @abstractmethod
    def on_entry_behavior(self, winch):
        pass

    @abstractmethod
    def on_exit_behavior(self, winch):
        pass


class InitState(State):
    def on_entry_behavior(self, winch):
        # set default parameters
        try:
            winch.payout_rate = int(input("Payout rate: "))
            winch.queue_command({"from": "INIT", "to": "STDBY"})
            winch.execute_command_stack()
        except:
            print("Invalid input in INIT")
            self.on_entry_behavior(winch)

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class StdbyState(State):
    def on_entry_behavior(self, winch):
        command = input("Enter Command (HELP for help): ")
        winch.queue_command({"from": "STDBY", "to": command})
        winch.execute_command_stack()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class CastState(State):

    def on_entry_behavior(self, winch):
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
        try:
            while True:
                cmd = (input("Manually enter distance (or STOP): "))
                if cmd == "STOP":
                    break
                measurement = int(cmd)
                for i in range(measurement):
                    winch.down()
        except:
            print("Invalid input in MANIN")
            self.on_entry_behavior(winch)

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ManualWinchInState(State):
    def on_entry_behavior(self, winch):
        while True:
            try:
                cmd = (input("Manually enter distance (or STOP): "))
                if cmd == "STOP":
                    break
                measurement = int(cmd)
                for i in range(measurement):
                    winch.up()
            except:
                print("Invalid input in MANIN")
                self.on_entry_behavior(winch)

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ReportPositionState(State):
    def on_entry_behavior(self, winch):
        pass

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class DownCastState(State):
    def on_entry_behavior(self, winch):
        while winch.depth < winch.target_depth:
            winch.down()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class UpCastState(State):
    def on_entry_behavior(self, winch):
        while winch.depth > 0:
            winch.up()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ReadDataState(State):
    def on_entry_behavior(self, winch):
        if winch.depth != 0:
            winch.error("Winch not on surface, cannot read data")

        print("C:", winch.conductivity, "T:", winch.temp, "D:", winch.depth)

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)


class ErrorState(State):
    def on_entry_behavior(self, winch):
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
        winch.print_states()

    def on_exit_behavior(self, winch):
        pass

    def __init__(self, name):
        State.__init__(self, name)
