import math
import logging
from typing import Optional
from src.interfaces.msg import Twist
from settings import settings

logger = logging.getLogger('FELIX')

ONEMINUSTANH1 = 1-math.tanh(1)

class JoystickEventType:
    move = "move"
    stop = "stop"
    start = "start"

class JoystickDirection:
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

class JoystickUpdateEvent:
    def __init__(
            self, 
            type: str, 
            x: float = 0.0, 
            y: float = 0.0, 
            distance: float = 0.0,
            direction: Optional[str] = None,
            ):
        
        self.type = type
        self.x = x
        self.y = y
        self.direction = direction
        self.distance: float = distance

    def get_twist(self) -> Twist:

        def same_sign(x,v):
            if (x < 0 and v > 0) or (x > 0 and v < 0):
                return -1 * v
            return v
        
        def dampen(x,a,b):
            return same_sign(x,math.floor(100*(1+math.cos(math.radians(a*x+180)))*b)/100)
            
        def tdampen(x):
            return math.tanh(x)+ONEMINUSTANH1
        
        if self.type == JoystickEventType.move:

            vz = -self.x
            vx = self.y

            if settings.JOY_DAMPENING_MODE == 1:
                vx = dampen(vx, 180, 0.5)
                vz = dampen(vz, 180, 0.5)
            elif settings.JOY_DAMPENING_MODE == 2:
                vx = dampen(vx, 180, 0.5)
                vz = dampen(vz, 90, vz)
            elif settings.JOY_DAMPENING_MODE == 3:
                vx = tdampen(vx) 
                vz = tdampen(vz)
                
            t = Twist()
            
            # angle = math.degrees(math.atan2(self.x,self.y))
            t.linear.x = vx
            t.angular.z = vz
            logger.info(f"joy-in: [{-self.y},0,{-self.x}]")
            logger.info(f"joy-out: [{t.linear.x},0,{t.angular.z}]")
            return t

        else:
            return Twist()
        
    
    def dict(self):
        return self.__dict__
