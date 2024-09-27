import math
from abc import ABC, abstractmethod
import numpy as np

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
        self.wheel_circumference = 2*math.pi*self.wheel_radius
        self.wheel_angles = [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]
        self.robot_circumference = math.pi*(self.wheel_base+self.track_width)
        self.encoder_resolution = 2.0/self.gear_ratio
        self.ticks_per_meter = int(self.encoder_resolution/self.wheel_circumference)
        self.ticks_per_robot_rotation = int(self.encoder_resolution/self.robot_circumference)
        self.max_wheel_angular_velocity = self.max_rpm*(2*math.pi)/60
        self.motor_power_factor = motor_voltage/12.0
        self.meters_per_rotation = 2*self.wheel_radius*math.pi
        self.max_linear_velocity = 1.0
        self.max_angular_velocity = 1.0
        self.min_linear_velocity = 0.0
        self.min_angular_velocity = 0.0
        self.velocity_scaler = np.array([1,1,1],dtype="float32")

    @property
    def dof(self):
        return 2

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
       

class MecanumVehicle(Vehicle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        @property
        def dof(self):
            return 2
    
        self.IK_MATRIX = np.array([
            [1,1,1,1],
            [-1,1,1,-1],
            [-1,1,-1,1]
        ])

        self.IK_DIVISOR = np.array([4,4,4*(self.track_width)])

        self.max_linear_velocity = self._calc_max_linear_velocity(self.max_rpm)
        self.max_angular_velocity = self._calc_max_angular_velocity(self.max_rpm)
        self.min_linear_velocity = self._calc_max_linear_velocity(self.min_rpm)
        self.min_angular_velocity = self._calc_max_angular_velocity(self.min_rpm)
        self.velocity_scaler = np.array([self.max_linear_velocity, self.max_linear_velocity, self.max_angular_velocity],dtype="float32")

    def forward_kinematics(self, v_x, v_y, omega) -> np.ndarray:
        """
        Perform forward kinematics to calculate wheel velocities given desired robot velocities.

        Args:
        - v_x: Desired linear velocity along the x-axis (m/s)
        - v_y: Desired linear velocity along the y-axis (m/s)
        - omega: Desired angular velocity about the z-axis (rad/s)

        Returns:
        - v_fl: Velocity of the front-left wheel (m/s)
        - v_fr: Velocity of the front-right wheel (m/s)
        - v_rl: Velocity of the rear-left wheel (m/s)
        - v_rr: Velocity of the rear-right wheel (m/s)
        """
        v_fl = v_x - v_y - self.track_width * omega
        v_fr = v_x + v_y + self.track_width * omega
        v_rl = v_x + v_y - self.track_width * omega
        v_rr = v_x - v_y + self.track_width * omega

        return np.array([v_fl, v_fr, v_rl, v_rr])

    
    def inverse_kinematics(self, wheel_velocities: np.ndarray) -> np.ndarray:
        """
        Perform inverse kinematics to calculate robot velocities given wheel velocities.

        Args:
        - ndarray [v_fl, v_fr, v_rl, v_rr] (m/s)

        Returns:
        - ndarray [v_x (m/s), v_y (m/s), omega (rad/s)] 
        """

        return self.IK_MATRIX.dot(wheel_velocities)/self.IK_DIVISOR
    

class DifferentialDriveVehicle(Vehicle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.max_linear_velocity = self._calc_max_linear_velocity(self.max_rpm)
        self.max_angular_velocity = self._calc_max_angular_velocity(self.max_rpm)
        self.min_linear_velocity = self._calc_max_linear_velocity(self.min_rpm)
        self.min_angular_velocity = self._calc_max_angular_velocity(self.min_rpm)
        self.velocity_scaler = np.array([self.max_linear_velocity, 0, self.max_angular_velocity],dtype="float32")

    def forward_kinematics(self, v_x, v_y, omega) -> np.ndarray:
        """
        Calculate wheel velocities for the left and right side given desired robot velocities.

        Args:
        - v_x: Desired linear velocity along the x-axis (m/s)
        - v_y: Desired linear velocity along the y-axis (m/s) - ignored
        - omega: Desired angular velocity about the z-axis (rad/s)

        Returns:
        - v_left: Velocity of the left wheels (m/s)
        - v_right: Velocity of the right wheels (m/s)
        """
        v_left = v_x - (self.track_width / 2) * omega
        v_right = v_x + (self.track_width / 2) * omega

        return np.array([v_left, v_right, v_left, v_right])

    def inverse_kinematics(self, wheel_velocities: np.ndarray) -> np.ndarray:
        """
        Calculate robot velocities given wheel velocities.

        Args:
        - wheel_velocities: [v_left, v_right] (m/s)

        Returns:
        - [v_x (m/s), omega (rad/s)]
        """
        v_left, v_right = wheel_velocities[:2]

        v_x = (v_left + v_right) / 2
        v_y = 0
        omega = (v_right - v_left) / self.track_width

        return np.array([v_x, v_y, omega])