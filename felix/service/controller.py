import asyncio
import logging
import math
from typing import Optional
import click
from felix.bus import SimpleEventBus
from felix.service.base import BaseService
from felix.settings import settings
from felix.topics import Topics
from felix.types import Odometry, Twist, Vector3
from lib.nodes.base import BaseNode
import numpy as np


if settings.ROBOT == "felixMac":
    from lib.mock.rosmaster import MockRosmaster as Rosmaster
else:
    from lib.controllers.rosmaster import Rosmaster

import numpy as np
import time


class NavRequest:
    """
    Request navigation toward an x,y point on an image.
    """

    def __init__(self, x: any, y: any, w: any, h: any):
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


class ControllerService(BaseService):
    def __init__(self, event_bus: SimpleEventBus):
        super().__init__(event_bus)

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

        self.autodriver = None  # TernaryObstacleAvoider(model_file=settings.TRAINING.model_root+"/checkpoints/ternary_obstacle_avoidance.pth")

    def print_stats(self):
        self.logger.info(
            "Vehicle Settings: min_linear_velocity: %s, min_angular_velocity: %s, max_linear_velocity: %s, max_angular_velocity: %s",
            self.vehicle.min_linear_velocity,
            self.vehicle.min_angular_velocity,
            self.vehicle.max_linear_velocity,
            self.vehicle.max_angular_velocity,
        )

    def setup_subscriptions(self):
        self.subscribe_to_topic(Topics.STOP, self._stop_handler)
        self.subscribe_to_topic(Topics.CMD_VEL, self._cmd_vel_handler)
        self.subscribe_to_topic(Topics.NAV_TARGET, self._nav_target_handler)
        self.subscribe_to_topic(Topics.RAW_IMAGE, self._raw_image_handler)

    def _stop_handler(self, payload=None):
        self.stop()

    def _nav_target_handler(self, payload: dict):
        request = NavRequest.model_validate(payload.get("message"))
        self._apply_nav_request(request)

    def _cmd_vel_handler(self, payload: dict):
        self.logger.info(f"Received cmd_vel: {payload}")
        request = Twist.model_validate(payload.get("message"))
        self.logger.info(f"Received PARSED")
        self._apply_cmd_vel(request)

    def _raw_image_handler(self, payload: dict):
        self.logger.info("Received raw image")
        self.camera_image = np.array(payload.get("message"), dtype=np.uint8)

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

    def on_stop(self):
        self.cmd_vel = Twist()
        self.prev_cmd_vel = Twist()
        self._bot.set_motor(0, 0, 0, 0)
        self.autodrive = False
  
    def _apply_nav_request(self, payload: NavRequest):
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

        velocity = self.vehicle.forward_kinematics(
            scaled.linear.x, scaled.linear.y, scaled.angular.z
        )

        power = self.vehicle.mps_to_motor_power(velocity)

        self._bot.set_motor(power[0], power[2], power[1], power[3])        
        self.logger.debug(f"Apply CMD Vel twist: {cmd_vel} scaled: {scaled} power: {power}")
    

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

    async def spinner(self):
        self.get_imu_data()

async def run(frequency: int = 10):
    event_bus = SimpleEventBus(port=5555)
    svc = ControllerService(event_bus=event_bus)
    #svc._apply_cmd_vel(Twist(linear=Vector3(x=0.5, y=0.0, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0)))
    svc.start()

    await svc.spin(frequency)


@click.command()
@click.option('--frequency', default=10, help='Frequency in Hz')
@click.option('--log-level', default='INFO', help='Logging level')
def cli(frequency, log_level):
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    asyncio.run(run(frequency))
        
if __name__ == "__main__":
    cli()



    