from states import State


class Context:
    def __init__(self, context_name):
        """
        :param context_name: String - Initialize context with name
        """
        self.__states = {}
        self.__currentState = None  # state name
        self.__name = context_name

    def add_state(self, state):
        """
        add state to context
        :param state: State
        :return:
        """
        self.__states[state.get_name()] = state
        print("States: ", self.__states.keys())

    def set_state(self, state_name):
        """
        :param state_name: String - name of state
        :return:
        """
        if state_name in self.__states:
            self.__currentState = self.__states[state_name]

        else:
            print("Error: unknown state: {}".format(state_name))

    def get_state(self):
        """
        :return: State
        """
        return self.__currentState

    def get_context_name(self):
        """
        :return: String
        """
        return self.__name

    def print_states(self):
        """
        Print all the keys of the avalible states
        :return:
        """
        print("Available: commands ")
        print(self.__states.keys())

    def do_transition(self, msg):
        """
        Map containing From and To state transitions using state names
        :param msg: Map<String,String>
        :return:
        """
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
        """
        :param to_state: State - State being called
        :return:
        """
        if isinstance(to_state, State):
            to_state.on_entry_behavior(self)

    def exit_behavior(self, from_state):
        """
        :param from_state: State - State being exited
        :return:
        """
        if isinstance(from_state, State):
            from_state.on_exit_behavior(self)
