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