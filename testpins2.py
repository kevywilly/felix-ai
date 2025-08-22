import time
import Jetson.GPIO as GPIO
import board
from digitalio import DigitalInOut


i2c = board.I2C()



pins = [board.D7, board.D12], # Define the pins to be used
for pin in pins:
    pin = DigitalInOut(pin)
    pin.switch_to_output(value=False)

exit()
for pin in pins:
    dig
    GPIO.output(pin, GPIO.LOW)  # Set each pin to HIGH
    time.sleep(0.5)  # Wait for half a second
    print(f"Pin {pin} set to LOW")


try:
    while True:
        time.sleep(1)
      # Keep the script running to observe the state
except KeyboardInterrupt:
    GPIO.cleanup()