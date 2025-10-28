from datetime import datetime, timezone
from enum import Enum
import math
from typing import Optional
from felix.settings import settings
from felix.vision.image import ImageUtils
from felix.vision.image_collector import ImageCollector
from lib.interfaces import Odometry, Twist, Vector3
from lib.nodes.base import BaseNode
import asyncio
import numpy as np
from lib.controllers.rosmaster import Rosmaster
import concurrent.futures

import time
from felix.signals import Topics
from lib.vehicles.vehicle import VehicleTrajectory, VehicleDirection


class NavRequest:
    """
    Request navigation toward an x,y point on an image.
    """

    def __init__(self, x: str | int, y: str | int, w: str | int, h: str | int):
        """
        x = horizontal coordinate
        y = vertical coordinate
        w = width of canvas
        h = height of canvas
        """

        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)

        # relative x and y as percentage of width and height
        self.x_rel = (self.x - self.w / 2) / (self.w / 2)
        self.y_rel = (self.h - self.y) / self.h

    def __repr__(self):
        return f"ControllerNavRequest(x={self.x}, y={self.y}, w={self.w}, h={self.h}, x_rel={self.x_rel}, y_rel={self.y_rel})"

    @property
    def target(self) -> Odometry:
        degrees = self.x_rel * settings.CAMERA_FOV / 2.0
        radians = math.radians(degrees)
        # angle = float(math.radians(self.x_rel*settings.CAMERA.fov))

        odom = Odometry()
        # we need to flip x and y is vertical, x is horizontal
        odom.twist.linear.x = self.y_rel
        odom.twist.angular.z = -self.x_rel
        odom.pose.orientation.z = radians

        return odom

    @classmethod
    def model_validate(cls, data):
        return NavRequest(**data)

def _generate_session_id() -> str:
    return datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')

def _angular_as_linear(angular: float) -> float:
    # relative angular normalized to linear based on ratio of max velocities
    return angular * settings.VEHICLE.max_linear_velocity / settings.VEHICLE.max_angular_velocity

class Direction(Enum):
    FORWARD = 0
    LEFT = 1
    RIGHT = 2
    BACKWARD = 3
    
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
        self.nav_capture = False
        self._image_collector = ImageCollector()
        self._last_capture_time = time.time()
        self.capture_session_id = _generate_session_id()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._is_capturing = False

        self.trajectory = VehicleTrajectory(VehicleDirection.STATIONARY, 0.0)

        self.print_stats()

        self._connect_signals()

        self.loaded()

    def print_stats(self):
        self.logger.info(
            f"""
            Vehicle Settings:
            \tmin_linear_velocity: {self.vehicle.min_linear_velocity}
            \tmin_angular_velicity: {self.vehicle.min_angular_velocity}
            \tmax_linear_velocity: {self.vehicle.max_linear_velocity}
            \tmax_angular_velicity: {self.vehicle.max_angular_velocity}
            """
        )

    def _connect_signals(self):
        Topics.stop.connect(self._on_stop_signal)
        Topics.cmd_vel.connect(self._on_cmd_vel_signal)
        Topics.nav_target.connect(self._on_nav_signal)
        Topics.raw_image.connect(self._on_raw_image_signal)
        Topics.nav_capture.connect(self._on_nav_capture_signal)

    def _on_stop_signal(self, sender, **kwargs):
        self.stop()

    def _on_nav_signal(self, sender, payload: NavRequest):
        self._apply_nav_request(payload)

    def _on_cmd_vel_signal(self, sender, payload: Twist):
        self._apply_cmd_vel(payload)

    def _on_raw_image_signal(self, sender, payload):
        self.camera_image = payload

    def _on_nav_capture_signal(self, sender, payload: bool):
        self.nav_capture = payload
        if self.nav_capture:
            self.capture_session_id = _generate_session_id()
            self.logger.info(f"Navigation image capture enabled, session id: {self.capture_session_id}")

    def get_imu_data(self):
        self.attitude_data = Vector3.from_tuple(self._bot.get_imu_attitude_data())
        self.magnometer_data = Vector3.from_tuple(self._bot.get_magnetometer_data())
        self.gyroscope_data = Vector3.from_tuple(self._bot.get_gyroscope_data())
        self.accelerometer_data = Vector3.from_tuple(self._bot.get_accelerometer_data())
        self.motion_data = Vector3.from_tuple(self._bot.get_motion_data())

    def _capture_wrapper(self):
        asyncio.run(self.capture_nav_image())

    async def capture_nav_image(self):
        if self.nav_capture:
            if time.time() - self._last_capture_time > settings.nav_capture_frequency_seconds:
                if self.cmd_vel.is_zero:
                    return
                if self.camera_image is None:
                    return
                
                image = ImageUtils.bgr8_to_jpeg(self.camera_image)
                self.logger.info("Capturing nav image")
                saved = self._image_collector.save_navigation_image(self.cmd_vel, image, self.capture_session_id)
                self.logger.info(f"Saved nav image: {saved}")
                self._last_capture_time = time.time()
            
    def spinner(self):
        self.get_imu_data()
        
        # Only submit if not already capturing
        if not self._is_capturing:
            if self.nav_capture and time.time() - self._last_capture_time > settings.nav_capture_frequency_seconds:
                self._is_capturing = True
                future = self._executor.submit(self._capture_wrapper)
                future.add_done_callback(lambda f: setattr(self, '_is_capturing', False))
        
        self.logger.debug(f"motion: {self._bot.get_motion_data()}")

    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """

    def stop(self):
        self.logger.info("Stopping controller")
        self.cmd_vel = Twist()
        self.prev_cmd_vel = Twist()
        self._bot.set_motor(0, 0, 0, 0)
        self.logger.info(self._bot.get_motion_data())
        self.trajectory = VehicleTrajectory(VehicleDirection.STATIONARY, 0.0)

    def _apply_nav_request(self, payload: NavRequest):
        self.logger.info(f"applying nav request\n: {payload}")
        odom = payload.target
        self.logger.info(f"applying nav target\n: {odom}")
        self._apply_cmd_vel(odom.twist)

    def _apply_cmd_vel(self, cmd_vel: Twist):
        if cmd_vel.is_zero:
            self.logger.info("cmd_vel is zero, stopping")
            self.stop()
            return
        
        if cmd_vel == self.prev_cmd_vel:
            self.logger.info("cmd_vel is the same as previous, skipping")
            return

        self.prev_cmd_vel = self.cmd_vel.copy()
        self.cmd_vel = cmd_vel.copy()
        

        

        scaled = self.vehicle.scale_twist(cmd_vel)

        self.trajectory = self.vehicle.get_relative_motion(
            linear_x=scaled.linear.x,
            linear_y=scaled.linear.y,
            angular_z=scaled.angular.z
        )

        velocity = self.vehicle.forward_kinematics(
            scaled.linear.x, scaled.linear.y, scaled.angular.z
        )

        power = self.vehicle.mps_to_motor_power(velocity)

        self._bot.set_motor(power[0], power[2], power[1], power[3])
        self.logger.info("--- Applying CMD Vel ---")
        self.logger.info(f"CMD Vel: (x: {cmd_vel.linear.x},y:{cmd_vel.linear.y}, z:{cmd_vel.angular.z}")
        self.logger.debug(f"Scaled CMD Vel: (x: {scaled.linear.x},y:{scaled.linear.y}, z:{scaled.angular.z}")
        self.logger.info(f"Trajectory: direction={self.trajectory.direction}, magnitude={self.trajectory.magnitude}, degrees_per_sec={self.trajectory.degrees_per_sec}")
        self.logger.debug(f"Motor Power: {power}")
    

    def _reset_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self._bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()
        self._bot.set_car_motion(0, 0, 0)

    def _start_nav(self):
        self.nav_delta = 0
        self.nav_delta_target = 0
        self.nav_yaw = self._bot.get_imu_attitude_data()[2]
        self.nav_start_time = time.time()

    def shutdown(self):
        self.stop()
