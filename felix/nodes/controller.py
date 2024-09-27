
from typing import Optional
from felix.settings import settings
from lib.interfaces import Odometry, Twist, Vector3
from lib.kinematics import Kinematics
from lib.nodes.base import BaseNode

if settings.ROBOT == 'felixMac':
    from lib.mock.rosmaster import MockRosmaster as Rosmaster
else:
    from lib.controllers.rosmaster import Rosmaster

import numpy as np
import time
from felix.signals import cmd_vel_signal, nav_target_signal, raw_image_signal, autodrive_signal

class ControllerNavRequest:
    def __init__(self, x: any, y: any, w: any, h: any):
        self.x = float(x)
        self.y = float(y)
        self.w = float(h)
        self.h = float(h)

    @classmethod
    def model_validate(cls, data):
        return ControllerNavRequest(**data)
    
    def __repr__(self):
        return f"ControllerNavRequest(x={self.x}, y={self.y}, w={self.w}, h={self.h})"


class Controller(BaseNode):

    def __init__(self, publish_frequency_hz=10, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self.publish_frequency_hz = publish_frequency_hz
        self.camera_image = None
        self.cmd_vel = Twist()
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
        self.last_cmd = None

        self.print_stats()
        self.autodrive = False

        self.autodriver = None #TernaryObstacleAvoider(model_file=settings.TRAINING.model_root+"/checkpoints/ternary_obstacle_avoidance.pth")

        cmd_vel_signal.connect(self._apply_cmd_vel)
        nav_target_signal.connect(self._apply_nav_request)
        raw_image_signal.connect(self._update_camera_image)
        autodrive_signal.connect(self._autodrive_changed)

        self.loaded()
    
    def print_stats(self):
        s = f"""
            min_linear_velocity: {self.vehicle.min_linear_velocity}
            min_angular_velicity: {self.vehicle.min_angular_velocity}
            max_linear_velocity: {self.vehicle.max_linear_velocity}
            max_angular_velicity: {self.vehicle.max_angular_velocity}
        """
        self.logger.info(s)

    def get_imu_data(self):
        self.attitude_data = Vector3.from_tuple(self._bot.get_imu_attitude_data())
        self.magnometer_data = Vector3.from_tuple(self._bot.get_magnetometer_data())
        self.gyroscope_data = Vector3.from_tuple(self._bot.get_gyroscope_data())
        self.accelerometer_data = Vector3.from_tuple(self._bot.get_accelerometer_data())
        self.motion_data = Vector3.from_tuple(self._bot.get_motion_data())

    async def spinner(self):
        self.get_imu_data()
        if self.motion_data.x != 0 or self.motion_data.y != 0:
            pass
            #self.logger.info(f'twist: \t{self.motion_data} \ncmd: \t{self.last_cmd}')
        if self.autodrive and self.autodriver is not None and self.camera_image is not None:
            self.cmd_vel = self.autodriver.predict(self.camera_image)
            #self.logger.info(f"Got prediction: {predictions}")

    
    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """
    
    def stop(self):
        self._bot.set_motor(0,0,0,0)


    def _autodrive_changed(self, sender, payload):
        self.autodrive = payload
        if self.autodrive:
            self._start_nav()
        else:
            self._reset_nav()

    def _update_camera_image(self, sender, payload):
        self.camera_image = payload

    def _scale_cmd_vel(self, cmd: Twist):
        
        return(
            self.vehicle.max_linear_velocity if cmd.linear.x > self.vehicle.max_linear_velocity else cmd.linear.x,
            self.vehicle.max_linear_velocity if cmd.linear.y > self.vehicle.max_linear_velocity else cmd.linear.y,
            self.vehicle.max_angular_velocity if cmd.angular.z > self.vehicle.max_angular_velocity else cmd.angular.z,
        )
    
    def _apply_nav_request(self, sender, payload: ControllerNavRequest):
        odom = Kinematics.xywh_to_nav_target(payload.x, payload.y, payload.w, payload.h)
        self._apply_cmd_vel(sender, odom.twist)

    def _apply_cmd_vel(self, sender, payload: Twist):
    
        vx, vy, omega = self._scale_cmd_vel(payload)
        
    
        vel = self.vehicle.forward_kinematics(
            vx, vy, omega
        )

        pow = self.vehicle.mps_to_motor_power(vel)
       
        self._bot.set_motor(pow[0], pow[2], pow[1], pow[3])
        
        self.logger.info(f"cmd: [{payload.linear.x},{payload.linear.y},{payload.angular.z}]")
        self.logger.info(f"scaled: [{vx},{vy},{omega}]")
        self.logger.info(f"power: {pow}")

        self.last_cmd = payload
       

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
        