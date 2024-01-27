
from typing import Optional
import traitlets
from src.nodes.node import Node
from src.interfaces.msg import Odometry, Twist, Vector3
from src.utils.rosmaster import Rosmaster
import atexit
import numpy as np
import time
from copy import deepcopy
from settings import settings

class Controller(Node):

    cmd_vel = traitlets.Instance(Twist, allow_none=True)
    nav_target = traitlets.Instance(Odometry, allow_none=True)
    publish_frequency_hz = traitlets.Int(default_value=10, config=True)

    attitude_data = traitlets.Any()
    magnometer_data = traitlets.Any()
    gyroscope_data = traitlets.Any()
    accelerometer_data = traitlets.Any()
    motion_data = traitlets.Any()

    def __init__(self, **kwargs):
        super(Controller, self).__init__(**kwargs)
        self._bot = Rosmaster(car_type=2, com="/dev/ttyUSB0")
        self._bot.create_receive_threading()
        self._running = False
        self._cmd_vel: Optional[Twist] = None
        self._nav_target: Optional[Odometry] = None
        self.attitude_data = np.zeros(3)
        self.magnometer_data = np.zeros(3)
        self.gyroscope_data = np.zeros(3)
        self.accelerometer_data = np.zeros(3)
        self.motion_data = np.zeros(3)
        self.angle_delta = 0

        atexit.register(self.stop)


    def get_imu_data(self):
        self.attitude_data = Vector3.from_tuple(self._bot.get_imu_attitude_data())
        self.magnometer_data = Vector3.from_tuple(self._bot.get_magnetometer_data())
        self.gyroscope_data = Vector3.from_tuple(self._bot.get_gyroscope_data())
        self.accelerometer_data = Vector3.from_tuple(self._bot.get_accelerometer_data())
        self.motion_data = Vector3.from_tuple(self._bot.get_motion_data())

    def spinner(self):
        self.get_imu_data()
        

    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """
    
    def stop(self):
        self._bot.set_car_motion(0,0,0)
        
    
    def _apply_cmd_vel(self):
        if self.cmd_vel:
            self._bot.set_car_motion(
                self._cmd_vel.linear.x*settings.Robot.max_linear_velocity, 
                self._cmd_vel.linear.y*settings.Robot.max_linear_velocity, 
                self._cmd_vel.angular.z*settings.Robot.max_angular_velocity
            )
        else:
            self.stop()


    def _reset_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self.bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()
        self.bot.set_car_motion(0,0,0)

    def _start_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self.bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()

    def _apply_nav_target(self):
        if self._nav_target:
            self._bot.set_car_motion(
                self._nav_target.twist.linear.x*settings.Robot.max_linear_velocity, 
                self._nav_target.twist.linear.y*settings.Robot.max_linear_velocity, 
                self._nav_target.twist.angular.z*settings.Robot.max_angular_velocity
            )
        else:
            self.stop()


    @traitlets.observe('cmd_vel')
    def _cmd_val_change(self, change):
        if change.new:
            self.logger.info(f'cmd_vel changed to: {change.new}')
            self._cmd_vel = deepcopy(change["new"])
            self._nav_target = None
            #self.cmd_vel = None
            self._apply_cmd_vel()

    @traitlets.observe('nav_target')
    def _nav_target_change(self, change):
        if change.new:
            self.logger.info(f'nav_target changed to: {change.new}')
            self._nav_target = deepcopy(change["new"])
            self.nav_target = None
            self._cmd_vel = None
            self._apply_nav_target()