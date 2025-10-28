from dataclasses import dataclass
from enum import Enum
from functools import cached_property
import math
from abc import ABC, abstractmethod
import numpy as np

from lib.interfaces import Twist

class VehicleDirection(int,Enum):
    BACKWARD = -2
    STATIONARY = -1
    FORWARD = 0
    LEFT = 1
    RIGHT = 2
    STRAFE_LEFT = 3
    STRAFE_RIGHT = 4
    

@dataclass
class VehicleTrajectory:
    direction: VehicleDirection
    magnitude: float
    degrees_per_sec: float = 0.0  # Optional: direction in degrees, if needed
    
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
    def vehicle_radius(self) -> float:
        return 0.5 * math.sqrt(self.track_width**2 + self.wheel_base**2)

    def is_turning_more_than_forward(self, linear_x, angular_z):
        """
        Determine if vehicle is turning more than going forward.
        
        Args:
            linear_x: forward velocity (m/s)
            angular_z: yaw rate (rad/s)
        
        Returns:
            True if turning dominates forward motion
        """
        # Convert angular velocity to linear velocity at corner
        angular_linear_equiv = abs(angular_z) * self.vehicle_radius
        
        # Compare magnitudes
        return angular_linear_equiv > abs(linear_x)
    
    def get_turning_ratio(self, linear_x, angular_z):
        """
        Returns ratio > 1 if turning dominates, < 1 if forward motion dominates.
        """
        if abs(linear_x) < 0.001:  # avoid division by zero
            return float('inf') if abs(angular_z) > 0.001 else 0.0
        
        angular_linear_equiv = abs(angular_z) * self.vehicle_radius
        return angular_linear_equiv / abs(linear_x)
        
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
       


    def get_relative_motion(self, linear_x: float, linear_y: float, angular_z: float, 
                        threshold: float = 0.05,
                        angular_threshold_deg: float = 3.0) -> VehicleTrajectory:
        """
        Determine primary motion direction based on linear and angular velocities.
        Optimized for visual/obstacle avoidance where camera perspective matters.
        
        Args:
            linear_x: forward velocity (m/s)
            linear_y: lateral (strafe) velocity (m/s)
            angular_z: yaw rate (rad/s) - positive = left turn
            threshold: minimum velocity magnitude to consider (m/s)
            angular_threshold_deg: minimum angular velocity to prioritize turning (degrees/sec)
        
        Returns:
            VehicleTrajectory with primary direction, magnitude, and rotation rate
        """
        # Convert angular threshold from degrees to radians
        angular_threshold_rad = math.radians(angular_threshold_deg)
        
        # Convert angular velocity to degrees per second for output
        angular_deg_per_sec = math.degrees(angular_z)
        
        # Convert angular velocity to equivalent linear velocity for magnitude calculation
        angular_linear_equiv = abs(angular_z) * self.vehicle_radius
        
        # Calculate total magnitude
        magnitude = math.sqrt(linear_x**2 + linear_y**2 + angular_linear_equiv**2)
        
        # Check if effectively stopped
        if magnitude < threshold:
            return VehicleTrajectory(
                direction=VehicleDirection.STATIONARY, 
                magnitude=0.0,
                degrees_per_sec=0.0
            )
        
        # Prioritize turning if angular velocity exceeds threshold
        if abs(angular_z) >= angular_threshold_rad:
            direction = VehicleDirection.LEFT if angular_z > 0 else VehicleDirection.RIGHT
        elif abs(linear_x) >= abs(linear_y):
            direction = VehicleDirection.FORWARD if linear_x > 0 else VehicleDirection.BACKWARD
        else:
            direction = VehicleDirection.STRAFE_LEFT if linear_y > 0 else VehicleDirection.STRAFE_RIGHT
        
        return VehicleTrajectory(
            direction=direction, 
            magnitude=magnitude,
            degrees_per_sec=angular_deg_per_sec
    )
