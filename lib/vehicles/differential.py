from functools import cached_property
import numpy as np
from lib.vehicles.vehicle import Vehicle


class DifferentialDriveVehicle(Vehicle):
    
    @cached_property
    def velocity_scaler(self):
        return np.array([self.max_linear_velocity, 0, self.max_angular_velocity],dtype=np.float32)

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