
from typing import Optional
import traitlets
from src.motion.autodriver import AutoDriver, BinaryObstacleAvoider, TernaryObstacleAvoider
from src.motion.vehicle import MecanumVehicle, Vehicle
from src.nodes.node import Node
from src.interfaces.msg import Odometry, Twist, Vector3
from src.motion.rosmaster import Rosmaster
import atexit
import numpy as np
import time
from copy import deepcopy
from settings import settings

class Controller(Node):

    autodrive = traitlets.Bool(default_value=False)
    cmd_vel = traitlets.Instance(Twist, allow_none=True)
    nav_target = traitlets.Instance(Odometry, allow_none=True)
    publish_frequency_hz = traitlets.Int(default_value=10, config=True)
    camera_image = traitlets.Any(allow_none=True)

    attitude_data = traitlets.Any()
    magnometer_data = traitlets.Any()
    gyroscope_data = traitlets.Any()
    accelerometer_data = traitlets.Any()
    motion_data = traitlets.Any()

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)
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

        self.autodriver = TernaryObstacleAvoider(model_file=settings.TRAINING.model_root+"/checkpoints/ternary_obstacle_avoidance.pth")

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

    def spinner(self):
        self.get_imu_data()
        if self.motion_data.x != 0 or self.motion_data.y != 0:
            pass
            #self.logger.info(f'twist: \t{self.motion_data} \ncmd: \t{self.last_cmd}')
        if self.autodrive and self.camera_image is not None:
            self.cmd_vel = self.autodriver.predict(self.camera_image)
            #self.logger.info(f"Got prediction: {predictions}")

    
    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """
    
    def stop(self):
        self._bot.set_motor(0,0,0,0)

     
    def _scale_cmd_vel(self, cmd: Twist):
        
        return(
            self.vehicle.max_linear_velocity if cmd.linear.x > self.vehicle.max_linear_velocity else cmd.linear.x,
            self.vehicle.max_linear_velocity if cmd.linear.y > self.vehicle.max_linear_velocity else cmd.linear.y,
            self.vehicle.max_angular_velocity if cmd.angular.z > self.vehicle.max_angular_velocity else cmd.angular.z,
        )
    
    def _apply_cmd_vel(self, cmd: Twist):
    
        vx, vy, omega = self._scale_cmd_vel(cmd)
        
    
        vel = self.vehicle.forward_kinematics(
            vx, vy, omega
        )

        pow = self.vehicle.mps_to_motor_power(vel)
       
        self._bot.set_motor(pow[0], pow[2], pow[1], pow[3])
        
        self.logger.info(f"cmd: [{cmd.linear.x},{cmd.linear.y},{cmd.angular.z}]")
        self.logger.info(f"scaled: [{vx},{vy},{omega}]")
        self.logger.info(f"power: {pow}")

        self.last_cmd = cmd
        

    def _apply_cmd_vel2(self, cmd):
    
        vx, vy, omega = self._scale_cmd_vel(cmd)
        print(vx,vy,omega)
       

        self._bot.set_car_motion(vx, vy, omega)
        self.last_cmd = cmd
       

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
        if self.nav_target:
            self._apply_cmd_vel(
                self.nav_target.twist
            )
            self._start_nav()
        else:
            self.stop()


    def shutdown(self):
        self.stop()
        self.autodrive = False
        

    @traitlets.observe('autodrive')
    def _autodrive_chnged(self, change):
        print(f'autodrive changed to: {self.autodrive}')
        self.stop()
        pass

    #@traitlets.observe('camera_image')
    #def _camera_image_changed(self, change):
    #    self.logger.info("got image")

        
        
    @traitlets.observe('cmd_vel')
    def _cmd_val_change(self, change):
        self._apply_cmd_vel(change.new)

    @traitlets.observe('nav_target')
    def _nav_target_change(self, change):
        if change.new:
            pass
            #self._apply_nav_target(change.new)