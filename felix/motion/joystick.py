from typing import Dict
from lib.interfaces import Twist
from felix.settings import settings
import numpy as np
from felix.signals import cmd_vel_signal, joystick_signal
from lib.log import logger
import math

class JoystickRequest:
    def __init__(self, x: any, y: any, strafe: any):
        self.x = float(x)
        self.y = float(y)
        self.strafe = bool(strafe)

    @classmethod
    def model_validate(cls, data):
        return JoystickRequest(**data)
    
    def __repr__(self):
        return f"JoystickRequest(x={self.x}, y={self.y}, strafe={self.strafe})"
    
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
    def __init__(self, curve_factor=0.25):
        self.dampener = JoystickNonLinearDampener(curve_factor)
        joystick_signal.connect(self.handle_joystick)
        logger.info("Joystick initialized")

    def get_twist(self, joy_x, joy_y, strafe: bool = False) -> Twist:
        t = Twist()

        _joy_x, _joy_y = self.dampener.apply(joy_x, joy_y)

        if strafe:
            vel = np.array([_joy_y, -_joy_x, 0])
        else:
            vel = np.array([_joy_y, 0, -_joy_x])
 # x left right, y is forwrad backward for joystick
        t.linear.x, t.linear.y, t.angular.z = np.vectorize(dampen)(vel)*settings.VEHICLE.velocity_scaler
        #t.linear.x, t.linear.y, t.angular.z = (vel)*settings.VEHICLE.velocity_scaler

        return t 

    def handle_joystick(self, sender, payload: JoystickRequest):
        logger.info(f"Joystick signal received from {sender}: {payload}")
        cmd_vel_signal.send("robot", payload=self.get_twist(payload.x, payload.y, payload.strafe))
