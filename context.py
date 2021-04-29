from states import State


class Context:
    def __init__(self, context_name):
        self.__states = {}
        self.__currentState = None  # state name
        self.__name = context_name

    def add_state(self, state):
        self.__states[state.get_name()] = state
        print("States: ", self.__states.keys())

    def set_state(self, state_name):
        if state_name in self.__states:
            self.__currentState = self.__states[state_name]

        else:
            print("Error: unknown state: {}".format(state_name))

    def get_state(self):
        return self.__currentState

    def get_context_name(self):
        return self.__name

    def print_states(self):
        print("Available: commands ")
        print(self.__states.keys())

    def do_transition(self, msg):
        current = self.__currentState.get_name()
        if msg["from"] == current:
            if msg["to"] in self.__states:
                print("Transition from {} to {}".format(msg["from"], msg["to"]))
                self.exit_behavior(self.__states[msg["from"]])
                self.set_state(msg["to"])
                self.entry_behavior(self.__states[msg["to"]])
            else:
                print("Error: Invalid transition from {} to {}".format(msg["from"], msg["to"]))
                self.entry_behavior(self.__states[current])

        else:
            print(
                "Error: Current State is {}, received transition from {} to {}".format(current, msg["from"], msg["to"]))
            # self.entry_behavior(self.__states[current])

    def entry_behavior(self, to_state):
        if isinstance(to_state, State):
            to_state.on_entry_behavior(self)

    def exit_behavior(self, from_state):
        if isinstance(from_state, State):
            from_state.on_exit_behavior(self)
