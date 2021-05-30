try:
    import RPi.GPIO as GPIO
except: pass

class WinchController:
    def __init__(self):
        self.setup()

    def up(self):
        pass

    def down(self):
        pass

    def off(self):
        pass

    def has_slack(self):
        pass

    def is_docked(self):
        pass

    def is_out_of_line(self):
        pass

    def set_slack_callback(self, callback):
        pass

    def set_line_callback(self, callback):
        pass

    def set_dock_callback(self, callback):
        pass

    def set_rotation_callback(self, callback):
        pass

    def setup(self):
        pass


class PiController(WinchController):
    def __init__(self):
        self.up_pin = 23
        self.down_pin = 24
        self.slack_pin = 6
        self.dock_pin = 12
        self.line_pin = 17
        self.rotation_pin = 21
        WinchController.__init__(self)

    def up(self):
        GPIO.output(self.down_pin, GPIO.HIGH)
        GPIO.output(self.up_pin, GPIO.LOW)

    def down(self):
        GPIO.output(self.down_pin, GPIO.LOW)
        GPIO.output(self.up_pin, GPIO.HIGH)

    def off(self):
        GPIO.output(self.down_pin, GPIO.LOW)
        GPIO.output(self.up_pin, GPIO.LOW)

    def has_slack(self):
        return GPIO.input(self.slack_pin) == GPIO.HIGH

    def is_out_of_line(self):
        return GPIO.input(self.line_pin) == GPIO.LOW

    def is_docked(self):
        return GPIO.input(self.dock_pin) == GPIO.LOW

    def set_slack_callback(self, callback):
        GPIO.add_event_detect(self.slack_pin, GPIO.BOTH, callback=callback)

    def set_line_callback(self, callback):
        GPIO.add_event_detect(self.line_pin, GPIO.BOTH, callback=callback)

    def set_dock_callback(self, callback):
        GPIO.add_event_detect(self.dock_pin, GPIO.BOTH, callback=callback)

    def set_rotation_callback(self, callback):
        GPIO.add_event_detect(self.rotation_pin, GPIO.FALLING, callback=callback, bouncetime=100)

    def setup(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.up_pin, GPIO.OUT)
        GPIO.output(self.up_pin, GPIO.LOW)
        GPIO.setup(self.down_pin, GPIO.OUT)
        GPIO.output(self.down_pin, GPIO.LOW)
        GPIO.setup(self.slack_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.dock_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.line_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.rotation_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
