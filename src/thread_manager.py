import threading

class InputHolder:
    def __init__(self):
        self.input_data = None
        self.event = threading.Event()

    def set_input(self, data):
        self.input_data = data
        self.event.set()

    def get_input(self):
        self.event.wait()
        input_data = self.input_data
        self.event.clear()
        return input_data


def prompt(input_holder):
    while True:
        message = input("Your prompt: ")
        input_holder.set_input(message)

def some_action(input_holder):
    while True:
        user_input = input_holder.get_input()
        print(user_input)

input_holder = InputHolder()

t1 = threading.Thread(target=prompt, args=(input_holder,))
t2 = threading.Thread(target=some_action, args=(input_holder,))


t1.start()
t2.start()

t1.join()
t2.join()