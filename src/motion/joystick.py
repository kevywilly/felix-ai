import math
import logging
from typing import Optional
from src.interfaces.msg import Twist
from src.settings import settings
import numpy as np

logger = logging.getLogger('FELIX')

ONEMINUSTANH1 = 1-math.tanh(1)


class Joystick:
    
    @classmethod
    def dampen(cls, x):
        if x > 0:
            y = (1-math.cos(math.radians(x*180)))/2
        else:
            y = -(1-math.cos(math.radians(x*180)))/2 
        
        return math.floor(100*y)/100.0
            
    @classmethod
    def get_twist(cls, joy_x, joy_y, strafe: bool = False) -> Twist:
        t = Twist()
        if strafe:
            vel = np.array([joy_y, -joy_x, 0])
        else:
            vel = np.array([joy_y, 0, -joy_x])
            
        vel = np.array(vel)  # x left right, y is forwrad backward for joystick
        t.linear.x, t.linear.y, t.angular.z = np.vectorize(cls.dampen)(vel)*settings.VEHICLE.velocity_scaler
        return t
