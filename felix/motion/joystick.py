from lib.interfaces import Twist
from felix.settings import settings
import numpy as np
import math

class JoystickRequest:
    def __init__(self, x: any = 0, y: any = 0, strafe: any = 0, power: any = 1.0):
        self.x = float(x)
        self.y = float(y)
        self.strafe = bool(strafe)
        self.power = float(power)
        if self.power > 1:
            self.power = self.power / 100.0

    @property
    def x_adj(self):
        return self.x * self.power
    
    @property
    def y_adj(self):
        return self.y * self.power

    @classmethod
    def model_validate(cls, data):
        return JoystickRequest(**data)
    
    def __repr__(self):
        return f"JoystickRequest(x={self.x}, y={self.y}, strafe={self.strafe}, power={self.power})"
    
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
        smoothed_y = 0.0 if input_y == 0 else (0.9 * dampened_y) + (0.1 * self.prev_y)

        # Store the smoothed values for the next frame
        self.prev_x = smoothed_x
        self.prev_y = smoothed_y

        return smoothed_x, smoothed_y

class Joystick:
    dampener = JoystickNonLinearDampener(settings.JOY_DAMPENING_CURVE_FACTOR)

    @classmethod
    def dampen(cls, x):
        if x > 0:
            y = (1 - math.cos(math.radians(x * 180))) / 2
        else:
            y = -(1 - math.cos(math.radians(x * 180))) / 2

        return math.floor(100 * y) / 100.0
    @classmethod
    def get_twist(cls, request: JoystickRequest) -> Twist:
        t = Twist()

        _joy_x, _joy_y = cls.dampener.apply(request.x_adj, request.y_adj)

        if request.strafe:
            vel = np.array([_joy_y, -_joy_x, 0])
        else:
            vel = np.array([_joy_y, 0, -_joy_x])

        # x left right, y is forwrad backward for joystick
        scaler = settings.VEHICLE.velocity_scaler

        t.linear.x, t.linear.y, t.angular.z = np.vectorize(cls.dampen)(vel)*scaler
        #t.linear.x, t.linear.y, t.angular.z = (vel)*settings.VEHICLE.velocity_scaler

        return t 
