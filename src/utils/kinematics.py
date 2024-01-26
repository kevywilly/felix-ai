
from typing import Tuple
import math
from src.interfaces.msg import Odometry
from settings import settings


class Kinematics:

    @staticmethod
    def xywh_to_nav_target(x: int, y: int, w: int, h: int) -> Odometry:
        _x = float((x - w/2)/(w/2))
        _y = float((y - h/2)/(h/2))

        # in our frame of robot motion x=y, y=x
        #_vx = math.tanh((1-_y)/4) # reverse _y since + is counter clockwise 
        #_vz = math.tanh(-_x) # reverse and shift positive since y=0 is top of image

        _vx = math.tanh(1-_y)
        _vz = -math.tanh(_x/2)  # dampen it a bit

        angle = float(math.radians(_x*settings.Camera.fov/2.0))

        odom = Odometry()
        odom.twist.linear.x = _vx
        odom.twist.angular.z = _vz
        odom.pose.orientation.z = angle

        return odom

    @staticmethod
    def ddr_ik(v_x, omega, L=0.5, R=0.1) -> Tuple[float, float]:
        """DDR inverse kinematics: calculate wheel rps from desired velocity."""
        return ((v_x - (L/2)*omega)/R, (v_x + (L/2)*omega)/R)

    @staticmethod
    def calc_velocity(wl, wr, L=0.5, R=0.1) -> Tuple[float,float,float]:
        """DDR inverse kinematics: calculate robot velocity from wheel rps"""
        return (R*(wr+wl)/2.0, 0, (R/2)*(wr-wl)/L)

    @staticmethod
    def calc_rpm(ticks: int, time_elapsed: float, ticks_per_rev: int = 360) -> float:
        return (ticks / ticks_per_rev)/(time_elapsed/60.0)

    @staticmethod
    def calc_rps(ticks: int, time_elapsed: float, ticks_per_rev: int = 360) -> float:
        return Kinematics.calc_rpm(ticks=ticks, time_elapsed=time_elapsed, ticks_per_rev=ticks_per_rev)/60.0
    
    @staticmethod
    def forward_kinematics(left_wheel_velocity, right_wheel_velocity, wheel_base, wheel_radius):
        # Calculate linear and angular velocity
        x = (wheel_radius / 2) * (left_wheel_velocity + right_wheel_velocity)
        z = (wheel_radius / wheel_base) * (right_wheel_velocity - left_wheel_velocity)

    @staticmethod
    def calculate_mecanum_velocities(wheel_velocities, wheel_radius, robot_width, robot_length):
        # Assuming wheel_velocities is a list containing the velocities of all 4 wheels in m/s
        # wheel_radius: Radius of the wheels in meters
        # robot_width: Width of the robot in meters (distance between left and right wheels)
        # robot_length: Length of the robot in meters (distance between front and rear wheels)

        # Calculate linear velocity components in x and y directions
        vx = (wheel_velocities[0] + wheel_velocities[1] + wheel_velocities[2] + wheel_velocities[3]) / 4
        vy = (-wheel_velocities[0] + wheel_velocities[1] + wheel_velocities[2] - wheel_velocities[3]) / 4

        # Calculate linear velocity magnitude
        linear_velocity = math.sqrt(vx**2 + vy**2)

        # Calculate angular velocity
        angular_velocity = (wheel_velocities[0] - wheel_velocities[1] + wheel_velocities[2] - wheel_velocities[3]) \
                        * wheel_radius / (2 * (robot_width + robot_length))

        return linear_velocity, angular_velocity
