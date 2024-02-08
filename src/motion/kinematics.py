from settings import settings
from src.interfaces.msg import Odometry

from typing import Tuple
import math
import numpy as np

# Wheel layout
#  0 2
#  1 3

mechanum_matrix = np.array(
            [
                [1,1,1,1],
                [-1,1,1,-1],
                [-1,-1,1,1]
            ]
        )


RPS_TO_RPM = 60/(2*math.pi)
     




class Kinematics:

    @staticmethod
    def xywh_to_nav_target(x: int, y: int, w: int, h: int, fov: int = 160) -> Odometry:
        _x = float((x - w/2)/(w/2))
        _y = float((y - h/2)/(h/2))

        # in our frame of robot motion x=y, y=x
        #_vx = math.tanh((1-_y)/4) # reverse _y since + is counter clockwise 
        #_vz = math.tanh(-_x) # reverse and shift positive since y=0 is top of image

        degrees = _x*fov/2
        radians = math.radians(degrees)

        max_x = 0.1
        max_z = 0.2
        
        turn_factor = (degrees/(fov/2.0))
        _vx = float((1-abs(turn_factor)))*0.2
        _vz = float(turn_factor*-1)*0.3

        angle = float(math.radians(_x*fov))

        odom = Odometry()
        odom.twist.linear.x = _vx
        odom.twist.angular.z = _vz
        odom.pose.orientation.z = radians

        return odom


    @staticmethod
    def calc_rpm(ticks: int, time_elapsed: float, ticks_per_rev: int = 360) -> float:
        return (ticks / ticks_per_rev)/(time_elapsed/60.0)


    @staticmethod
    def calc_rps(ticks: int, time_elapsed: float, ticks_per_rev: int = 360) -> float:
        return Kinematics.calc_rpm(ticks=ticks, time_elapsed=time_elapsed, ticks_per_rev=ticks_per_rev)/60.0
    

    @staticmethod
    def calculate_robot_velocity(
        rpm_front_left, 
        rpm_front_right, 
        rpm_rear_left, 
        rpm_rear_right, 
        R, 
        L, 
        W
    ):

        """
        Calculate linear and angular velocity of the robot from the RPMs of its four wheels.

        Args:
        - rpm_front_left: RPM of the front-left wheel
        - rpm_front_right: RPM of the front-right wheel
        - rpm_rear_left: RPM of the rear-left wheel
        - rpm_rear_right: RPM of the rear-right wheel
        - R: radius of the wheels (m)
        - L: distance between the front and rear wheels (m)
        - W: distance between the left and right wheels (m)

        Returns:
        - V: linear velocity of the robot (m/s)
        - omega: angular velocity of the robot (rad/s)
        """
        # Calculate linear velocity
        V = ((rpm_front_left + rpm_front_right + rpm_rear_left + rpm_rear_right) * 2 * math.pi * R) / (4 * 60)

        # Calculate angular velocity
        omega = ((rpm_front_right + rpm_rear_right - rpm_front_left - rpm_rear_left) * 2 * math.pi * R) / (4 * L)

        return V, omega
        


    @staticmethod
    def calculate_motor_speeds(
        V,
        omega, 
        R, 
        L, 
        W
    ):
       
        f1 = L*omega/2
        f2 = omega*W/(2*R)
        f3 = 60/(2*math.pi)

        # Calculate linear and angular velocities for each wheel
        fl = (V-f1)/R + f2
        fr = (V+f1)/R - f2
        rl = (V-f1)/R - f2 
        rr = (V+f1)/R + f2
        
        return (
            fl*RPS_TO_RPM,
            fr*RPS_TO_RPM,
            rl*RPS_TO_RPM,
            rr*RPS_TO_RPM
        )
    
    


# Wheel layout
#  0 2
#  1 3
