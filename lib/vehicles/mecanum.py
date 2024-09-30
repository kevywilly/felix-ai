from functools import cached_property
import numpy as np
from lib.vehicles.vehicle import Vehicle


class MecanumVehicle(Vehicle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
        self.IK_MATRIX = np.array([
            [1,1,1,1],
            [-1,1,1,-1],
            [-1,1,-1,1]
        ])

        self.IK_DIVISOR = np.array([4,4,4*(self.track_width)])

    @cached_property
    def dof(self):
        return 2
    

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
    
    @cached_property
    def velocity_scaler(self):
        return np.array([self.max_linear_velocity, self.max_linear_velocity, self.max_angular_velocity],dtype=np.float32)