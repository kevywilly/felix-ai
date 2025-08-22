import time
import Jetson.GPIO as GPIO
import board
from adafruit_vl53l0x import VL53L0X    
i2c = board.I2C()

GPIO.cleanup()

GPIO.setmode(GPIO.TEGRA_SOC)

# 7 (GP167) and 32 (GP113_PWM7) are the pins used for the VL53L0X sensors

PINS = ["GP167", "GP113_PWM7"]  # Define the pins to be used
#PINS = [7, 12, 32, 33]  # Define the pins to be used

GPIO.setup(PINS, GPIO.OUT, initial=GPIO.LOW)

for pin in PINS:
    GPIO.output(pin, GPIO.HIGH)  # Set each pin to HIGH
    time.sleep(0.5)  # Wait for half a second
    print(f"Pin {pin} set to LOW")


try:
    while True:
        time.sleep(1)
      # Keep the script running to observe the state
except KeyboardInterrupt:
    GPIO.cleanup()