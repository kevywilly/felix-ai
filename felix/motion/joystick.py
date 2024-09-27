from typing import Dict
from lib.interfaces import Twist
from felix.settings import settings
import numpy as np
from felix.signals import cmd_vel_signal, joystick_signal
from lib.log import logger
import math


class JoystickNonLinearDampener:
    def __init__(self, curve_factor=0.5):
        """
        curve_factor: Controls the responsiveness.
                      Lower values (e.g., 0.5) mean more responsive at lower speeds,
                      but slower increase at higher speeds.
        """
        self.curve_factor = curve_factor
        self.prev_x = 0.0
        self.prev_y = 0.0

    def apply(self, input_x, input_y):
        # Ensure the input is in the valid range (-1.0, 1.0) for both x and y
        input_x = max(min(input_x, 1.0), -1.0)
        input_y = max(min(input_y, 1.0), -1.0)

        # Apply non-linear dampening using an exponential response curve
        dampened_x = input_x * (abs(input_x) ** self.curve_factor)
        dampened_y = input_y * (abs(input_y) ** self.curve_factor)

        # Optional smoothing using previous values (low-pass filter) for extra smoothness
        smoothed_x = 0.0 if input_x == 0 else (0.9 * dampened_x) + (0.1 * self.prev_x)
        smoothed_y = 0.0 if input_x == 0 else (0.9 * dampened_y) + (0.1 * self.prev_y)

        # Store the smoothed values for the next frame
        self.prev_x = smoothed_x
        self.prev_y = smoothed_y

        return smoothed_x, smoothed_y


def dampen(x):
        if x > 0:
            y = (1 - math.cos(math.radians(x * 180))) / 2
        else:
            y = -(1 - math.cos(math.radians(x * 180))) / 2

        return math.floor(100 * y) / 100.0

class Joystick:
    def __init__(self, dampen_ratio=0.25):
        self.dampener = JoystickNonLinearDampener(dampen_ratio)
        joystick_signal.connect(self.handle_joystick)
        logger.info("Joystick initialized")

    def get_twist(self, joy_x, joy_y, strafe: bool = False) -> Twist:
        t = Twist()
        if strafe:
            vel = np.array([joy_y, -joy_x, 0])
        else:
            vel = np.array([joy_y, 0, -joy_x])

        vel = np.array(vel)  # x left right, y is forwrad backward for joystick
        t.linear.x, t.linear.y, t.angular.z = np.vectorize(dampen)(vel)*settings.VEHICLE.velocity_scaler
        #t.linear.x, t.linear.y, t.angular.z = (vel)*settings.VEHICLE.velocity_scaler

        return t

    def handle_joystick(self, sender, payload: Dict) -> Twist:
        logger.info(f"Joystick signal received from {sender}: {payload}")
        x = float(payload.get("x", 0))
        y = float(payload.get("y", 0))
        strafe = float(payload.get("strafe", False))
        _x, _y = self.dampener.apply(x, y)

        t = Joystick.get_twist(_x, _y, strafe)
        cmd_vel_signal.send("robot", payload=t)
        return t
