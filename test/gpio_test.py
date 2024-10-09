import Jetson.GPIO as GPIO
import time

# Pin Definitions (using BOARD numbering)
pin1 = 32 # Pin 16 (output pin)
pin2 = 33 # Pin 18 (input pin)

# Set up GPIO mode (use BOARD pin numbering)
GPIO.setmode(GPIO.BOARD)

# Set up pin 16 as an output and pin 18 as an input
GPIO.setup(pin1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(pin2, GPIO.OUT, initial=GPIO.LOW)

def print_states():
    state1 = GPIO.input(pin1)
    state2 = GPIO.input(pin2)
    print(f"Pin 16 state: {'HIGH' if state1 else 'LOW'}")
    print(f"Pin 18 state: {'HIGH' if state2 else 'LOW'}")

try:

    print_states()

    time.sleep(2)

    # Set pin 16 high
    GPIO.output(pin1, GPIO.LOW)
    GPIO.output(pin2, GPIO.LOW)
    

    # Give some time for the signal to propagate
    time.sleep(2)
    print_states()

    time.sleep(30)

    

finally:
    # Clean up GPIO settings
    GPIO.cleanup()
