
import time
import board
from digitalio import DigitalInOut
from adafruit_vl53l0x import VL53L0X
import atexit
import logging
pins = [
    DigitalInOut(board.D4),  # GP115 (33)
    DigitalInOut(board.D18),  # GP14 (27)
    DigitalInOut(board.D12),
    DigitalInOut(board.D13),  # GP113_PWM7 (32()
]

for power_pin in pins:
    power_pin.switch_to_output(value=False)
    power_pin.value = False
    time.sleep(0.02)

#pins[0].value = True


