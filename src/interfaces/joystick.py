import math
from typing import Optional
from pydantic import BaseModel
from enum import Enum
from src.interfaces.msg import Twist

class JoystickEventType(str, Enum):
    move = "move"
    stop = "stop"
    start = "start"

class JoystickDirection(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

class JoystickUpdateEvent(BaseModel):
    type: JoystickEventType
    x: Optional[float] = 0.0
    y: Optional[float] = 0.0
    direction: Optional[JoystickDirection] = None
    distance: Optional[float] = 0.0

    def get_twist(self) -> Twist:
        t = Twist()
        if self.type == JoystickEventType.move:
            try:
                dist = self.distance/100.0
                angle = math.degrees(math.atan2(self.x,self.y))
                x = self.x * dist
                y = self.y * dist
                if abs(angle) <= 10 or abs(angle) >=170:
                    # forward / backward
                    t.linear.x = y
                elif abs(angle) <= 85 or abs(angle) >=95:
                    # turn
                    t.linear.x = y
                    t.angular.z = -x
                else:
                    # slide
                    # t.linear.x = y
                    t.linear.y = -x
            except Exception as ex:
                t = Twist()
                print(ex.__str__())
        return t