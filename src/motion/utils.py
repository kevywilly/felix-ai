from src.interfaces.msg import Twist
from typing import Optional, Dict

def twist_to_json(t: Twist) -> Dict:
    return {
        'linear': {'x': t.linear.x, 'y': t.linear.y, 'z': t.linear.z},
        'angular': {'x': t.angular.x, 'y': t.angular.y, 'z': t.angular.z},
    }

def twist_from_json(data: Optional[Dict]) -> Twist:
    if not data:
        return Twist()
    
    t = Twist()
    t.linear.x = float(data['linear']['x'])
    t.linear.y = float(data['linear']['y'])
    t.linear.z = float(data['linear']['z'])
    t.angular.x = float(data['angular']['x'])
    t.angular.y = float(data['angular']['y'])
    t.angular.z = float(data['angular']['z'])

    return t

def scale_abs(x, abs_in_min, abs_in_max, abs_out_min, abs_out_max, keep_zero=True):
    if x == 0 and keep_zero:
        return x
    return scale(abs(x), abs_in_min, abs_in_max, abs_out_min, abs_out_max) * (-1 if x != abs(x) else 1)

def scale(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
