import math
from typing import Optional
from src.interfaces.msg import Twist
from settings import settings
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
        if self.type == JoystickEventType.move:

            dist = self.distance/100.0
            # x is left/right for joystick
            x = self.x
            y = self.y
            
            if settings.JOY_DAMPENING_MODE == 1:
                x = math.floor(100*(1+math.cos(math.radians(x*180 + 180)))/2)/100  # Math.cos(((x*100)*100/180+180)*RADIANS))/100
                x = -x if self.x < 0 else x
            elif settings.JOY_DAMPENING_MODE == 2:
                x = math.floor(100*(1+math.cos(math.radians(x*90 + 180)))/2)/100  # Math.cos(((x*100)*100/180+180)*RADIANS))/100
                x = -x if self.x < 0 else x
                
            try:
                t = Twist()
                
                angle = math.degrees(math.atan2(self.x,self.y))
                
                if abs(angle) <= 5 or abs(angle) >=175:
                    # forward / backward
                    t.angular.z = 0
                    t.linear.x = y
                else: 
                    # turn
                    t.linear.x = y
                    t.angular.z = -x
                return t
            except Exception as ex:
                print(ex.__str__())
                return Twist()
        else:
            return Twist()
        
    
    def dict(self):
        return self.__dict__
