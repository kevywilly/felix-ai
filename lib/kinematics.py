

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

    import math

    @staticmethod
    def calculate_direction(linear_velocity, angular_velocity, time):
        # Assuming linear_velocity is the velocity along the heading direction
        # Convert angular velocity from radians per second to degrees per second
        angular_velocity_deg = math.degrees(angular_velocity)

        # Calculate change in heading angle
        delta_heading = angular_velocity_deg * time

        # Calculate new heading direction
        new_heading = delta_heading

        return new_heading

    @staticmethod
    def calculate_heading(linear_x, linear_y, angular_z):
        # Calculate the magnitude of linear velocity
        linear_velocity_magnitude = math.sqrt(linear_x ** 2 + linear_y ** 2)

        # If the linear velocity is almost zero, return current heading
        #if linear_velocity_magnitude < 0.001:
        #    return None

        # Calculate the heading angle using arctan2 function
        heading = math.atan2(linear_y, linear_x)

        # Adjust heading based on the direction of linear velocity
        if heading < 0:
            heading += 2 * math.pi

        # Adjust heading based on angular velocity
        heading += angular_z

        # Normalize heading to be within [0, 2*pi)
        heading %= 2 * math.pi

        return heading

    @staticmethod
    def calculate_turn(linear_x, linear_y, angular_z) -> np.ndarray:
        heading = Kinematics.calculate_heading(linear_x, linear_y, angular_z)
        forward = 0
        left = 0
        right = 0

        if heading > math.radians(5) and heading <= math.radians(180):
            return 1
        elif heading > math.radians(180) and heading < math.radians(355):
            return 2
        else:
            return 0

        return np.array(([forward,left,right]))


# Wheel layout
#  0 2
#  1 3
