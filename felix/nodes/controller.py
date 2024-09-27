
import math
from typing import Optional
from felix.settings import settings
from lib.interfaces import Odometry, Twist, Vector3
from lib.nodes.base import BaseNode

if settings.ROBOT == 'felixMac':
    from lib.mock.rosmaster import MockRosmaster as Rosmaster
else:
    from lib.controllers.rosmaster import Rosmaster

import numpy as np
import time
from felix.signals import sig_cmd_vel, sig_nav_target, sig_raw_image, sig_stop

class ControllerNavRequest:
    def __init__(self, x: any, y: any, w: any, h: any):
        # x = horizontal coordinate
        # y = vertical coordinate
        # w = width of canvas
        # h = height of canvas

        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)

        # relative x and y as percentage of width and height
        self.x_rel = (self.x - self.w/2)/(self.w/2)
        self.y_rel = (self.h - self.y)/self.h

    def __repr__(self):
        return f"ControllerNavRequest(x={self.x}, y={self.y}, w={self.w}, h={self.h}, x_rel={self.x_rel}, y_rel={self.y_rel})"  

    @property
    def target(self) -> Odometry:
        degrees = self.x_rel*settings.CAMERA_FOV/2.0
        radians = math.radians(degrees)
        #angle = float(math.radians(self.x_rel*settings.CAMERA.fov))

        odom = Odometry()
        # we need to flip x and y is vertical, x is horizontal
        odom.twist.linear.x = self.y_rel
        odom.twist.angular.z =-self.x_rel
        odom.pose.orientation.z = radians

        return odom

    @classmethod
    def model_validate(cls, data):
        return ControllerNavRequest(**data)
    
    

class Controller(BaseNode):

    def __init__(self, publish_frequency_hz=10, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.publish_frequency_hz = publish_frequency_hz
        self.camera_image = None

        self.cmd_vel = Twist()
        self.prev_cmd_vel = Twist()

        self.vehicle = settings.VEHICLE
        self._bot = Rosmaster(car_type=2, com=self.vehicle.yaboom_port)
        self._bot.create_receive_threading()
        self._running = False
        self._nav_target: Optional[Odometry] = None

        self.attitude_data = np.zeros(3)
        self.magnometer_data = np.zeros(3)
        self.gyroscope_data = np.zeros(3)
        self.accelerometer_data = np.zeros(3)
        self.motion_data = np.zeros(3)

        self.angle_delta = 0
        self.camera_image = None

        self.print_stats()
        self.autodrive = False

        self.autodriver = None #TernaryObstacleAvoider(model_file=settings.TRAINING.model_root+"/checkpoints/ternary_obstacle_avoidance.pth")

        self._connect_signals()

        self.loaded()
    
    def print_stats(self):
        s = f"""
            min_linear_velocity: {self.vehicle.min_linear_velocity}
            min_angular_velicity: {self.vehicle.min_angular_velocity}
            max_linear_velocity: {self.vehicle.max_linear_velocity}
            max_angular_velicity: {self.vehicle.max_angular_velocity}
        """
        self.logger.info(s)

    def _connect_signals(self):
        sig_stop.connect(self._on_stop_signal)
        sig_cmd_vel.connect(self._on_cmd_vel_signal)
        sig_nav_target.connect(self._on_nav_signal)
        sig_raw_image.connect(self._on_raw_image_signal)

    def _on_stop_signal(self, sender, **kwargs):
        self.stop()

    def _on_nav_signal(self, sender, payload: ControllerNavRequest):
        self._apply_nav_request(payload)

    def _on_cmd_vel_signal(self, sender, payload: Twist):
        self._apply_cmd_vel(payload)

    def _on_raw_image_signal(self, sender, payload):
        self.camera_image = payload

    def get_imu_data(self):
        self.attitude_data = Vector3.from_tuple(self._bot.get_imu_attitude_data())
        self.magnometer_data = Vector3.from_tuple(self._bot.get_magnetometer_data())
        self.gyroscope_data = Vector3.from_tuple(self._bot.get_gyroscope_data())
        self.accelerometer_data = Vector3.from_tuple(self._bot.get_accelerometer_data())
        self.motion_data = Vector3.from_tuple(self._bot.get_motion_data())

    async def spinner(self):
        self.get_imu_data()
    
    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """
    
    def stop(self):
        self.cmd_vel = Twist()
        self.prev_cmd_vel = Twist()
        self._bot.set_motor(0,0,0,0)
    
    def _apply_nav_request(self, payload: ControllerNavRequest):
        self.logger.info(f"applying nav request\n: {payload}")
        odom = payload.target
        self.logger.info(f"applying nav target\n: {odom}")
        self._apply_cmd_vel(odom.twist)

    def _apply_cmd_vel(self, cmd_vel: Twist):
    
        if cmd_vel == self.prev_cmd_vel and not cmd_vel.is_zero:
            self.logger.info("cmd_vel is the same as previous, skipping")
            return
        
        self.prev_cmd_vel = self.cmd_vel.copy()
        self.cmd_vel = cmd_vel.copy()

        scaled = self.vehicle.scale_twist(cmd_vel)
         
        velocity = self.vehicle.forward_kinematics(scaled.linear.x, scaled.linear.y, scaled.angular.z)

        power = self.vehicle.mps_to_motor_power(velocity)

        self._bot.set_motor(power[0], power[2], power[1], power[3])
        self.logger.info("")
        self.logger.info("-------------------APPLY CMD VEL--------------------")
        self.logger.info(f"cmd: {cmd_vel}")
        self.logger.info(f"scaled_cmd: {scaled}")
        self.logger.info(f"power: {power}\n")
       

    def _reset_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self._bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()
        self._bot.set_car_motion(0,0,0)


    def _start_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self._bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()

    async def shutdown(self):
        self.stop()
        self.autodrive = False
        