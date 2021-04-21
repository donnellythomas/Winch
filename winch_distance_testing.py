import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN,pull_up_down = GPIO.PUD_UP)

rotations = 0;

def gotWheelTurn(channel):
    global rotations 
    rotations += 1
def down():
    print("Going down...")
    GPIO.output(24, GPIO.LOW)
    GPIO.output(23, GPIO.HIGH)

def up():
    print("Going up...")
    GPIO.output(23, GPIO.LOW)
    GPIO.output(24, GPIO.HIGH)
def stop():
    global rotations 
    print("Stopping...")
    GPIO.output(23, GPIO.LOW)
    GPIO.output(24, GPIO.LOW)
    print("rotations:", rotations)
    rotations = 0
       
up_pin = 23
down_pin = 24

## Set each pin as an output and make it low:
GPIO.setup(up_pin, GPIO.OUT)
GPIO.output(up_pin, GPIO.LOW)
GPIO.setup(down_pin, GPIO.OUT)
GPIO.output(down_pin, GPIO.LOW)
            
GPIO.add_event_detect(21, GPIO.FALLING,callback = gotWheelTurn,bouncetime=100)

while True:
    cmd = input("UP, DOWN, STOP, EXIT: ")
    if cmd == "UP":
        up()
    elif cmd == "DOWN":
        down()
    elif cmd == "STOP":
        stop()
    elif cmd == "EXIT":
        break
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       
       