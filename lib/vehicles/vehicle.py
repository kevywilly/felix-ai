from functools import cached_property
import math
from abc import ABC, abstractmethod
import numpy as np

from lib.interfaces import Twist

# https://gm0.org/en/latest/docs/software/concepts/kinematics.html
class Vehicle(ABC):
    def __init__(self,
        wheel_radius: float,
        wheel_base: float,
        track_width: float,
        gear_ratio: float,
        max_rpm: int,
        min_rpm: int = 0,
        motor_voltage=12,
        yaboom_port: str = '/dev/myserial', 
        fov: int = 160,
    ):
        self.wheel_radius = wheel_radius
        self.wheel_base = wheel_base
        self.track_width = track_width
        self.max_rpm = max_rpm
        self.min_rpm = min_rpm
        self.gear_ratio = gear_ratio
        self.yaboom_port = yaboom_port
        self.fov = fov
        self.motor_voltage=motor_voltage

    @cached_property
    def max_wheel_anglular_velocity(self):
        return self.max_rpm*(2*math.pi)/60
    
    @cached_property
    def motor_power_factor(self):
        return self.motor_voltage/12.0
    
    @cached_property
    def meters_per_rotation(self):
        return 2*self.wheel_radius*math.pi
    
    @cached_property
    def ticks_per_robot_rotation(self):
        return int(self.encoder_resolution/self.robot_circumference)

    @cached_property
    def ticks_per_meter(self):
        return int(self.encoder_resolution/self.wheel_circumference)
    
    @cached_property
    def encoder_resolution(self):
        return 2.0/self.gear_ratio
    
    @cached_property
    def robot_circumference(self):
        return math.pi*(self.wheel_base+self.track_width)
    
    @cached_property
    def wheel_circumference(self):
        return 2 * math.pi * self.wheel_radius
    
    @cached_property
    def wheel_angles(self):
        return [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]
    
    @cached_property
    def max_linear_velocity(self):
        return self._calc_max_linear_velocity(self.max_rpm)
    
    @cached_property
    def max_angular_velocity(self):
        return self._calc_max_angular_velocity(self.max_rpm)
    
    @cached_property
    def min_linear_velocity(self):
        return self._calc_max_linear_velocity(self.min_rpm)
    
    @cached_property
    def min_angular_velocity(self):
        return self._calc_max_angular_velocity(self.min_rpm)
    
    @cached_property
    def velocity_scaler(self):
        return np.ndarray([self.max_linear_velocity, self.max_linear_velocity, self.max_angular_velocity],dtype=np.float32)
    
    @cached_property
    def dof(self):
        return 2
    
    def scale_twist(self, twist: Twist) -> Twist:
        t = twist.copy()
        t.linear.x = self.max_linear_velocity if twist.linear.x > self.max_linear_velocity else twist.linear.x
        t.linear.y = self.max_linear_velocity if twist.linear.y > self.max_linear_velocity else twist.linear.y
        t.angular.z = self.max_angular_velocity if twist.angular.z > self.max_angular_velocity else twist.angular.z

        return t

    @abstractmethod
    def forward_kinematics(self, v_x, v_y, omega) -> np.ndarray:
        pass
    
    @abstractmethod
    def inverse_kinematics(self, wheel_velocities: np.ndarray) -> np.ndarray:
        pass
    
    def _calc_max_linear_velocity(self, rpm)-> float:
        v_all = self.rpm_to_mps(rpm)
        v, _, _ = self.inverse_kinematics(np.array([v_all, v_all, v_all, v_all]))
        return v
    
    def _calc_max_angular_velocity(self, rpm) -> float:
        v_all = self.rpm_to_mps(rpm)
        _, _, omega = self.inverse_kinematics(np.array([-v_all, v_all, -v_all, v_all]))
        return omega

    def rpm_to_mps(self, rpm: float):
        rps = rpm/60
        mps = rps*self.meters_per_rotation
        
        return mps


    def mps_to_rpm(self, mps: np.ndarray) -> np.ndarray:
        rps = mps/self.meters_per_rotation
        rpm = rps*60
        return rpm
    
    def mps_to_motor_power(self, mps: np.ndarray) -> np.ndarray:
        power = 100*self.mps_to_rpm(mps)/self.max_rpm
        return np.vectorize(lambda t: min(max(t,-100),100))(power)
       

