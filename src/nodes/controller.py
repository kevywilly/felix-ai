
import traitlets
import time
from traitlets.config.configurable import SingletonConfigurable
from src.models.vector import Vector3
from src.utils.rosmaster import Rosmaster
import atexit
import numpy as np
from copy import deepcopy
from src.nodes.node import Node

class Controller(Node):

    cmd_vel = traitlets.Instance(Vector3)
    publish_frequency_hz = traitlets.Int(default_value=10, config=True)
    attitude_data = traitlets.Any()
    magnometer_data = traitlets.Any()
    gyroscope_data = traitlets.Any()
    accelerometer_data = traitlets.Any()
    motion_data = traitlets.Any()

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(name="Controller", *args, **kwargs)
        self._bot = Rosmaster(car_type=2, com="/dev/ttyUSB0")
        self._bot.create_receive_threading()
        self._running = False
        self._cmd_vel: Vector3 = Vector3()
        self.attitude_data = np.zeros(3)
        self.magnometer_data = np.zeros(3)
        self.gyroscope_data = np.zeros(3)
        self.accelerometer_data = np.zeros(3)
        self.motion_data = np.zeros(3)
        atexit.register(self.shutdown)


    def spinner(self):
        
        self.attitude_data = np.array(self._bot.get_imu_attitude_data())
        self.magnometer_data = np.array(self._bot.get_magnetometer_data())
        self.gyroscope_data = np.array(self._bot.get_gyroscope_data())
        self.accelerometer_data = np.array(self._bot.get_accelerometer_data())
        self.motion_data = np.array(self._bot.get_motion_data())
        


    def get_stats(self):
        return f"""
            cmd_vel: {self.cmd_vel}
        """
    
    def shutdown(self):
        self._bot.set_car_motion(0,0,0)
        
    
    @traitlets.observe('cmd_vel')
    def _cmd_val_change(self, change):
        self.logger.info(f'cmd_vel changed to: {change["new"]}')
        self._cmd_vel = deepcopy(change["new"])
        self._bot.set_car_motion(self._cmd_vel.x, self._cmd_vel.y, self._cmd_vel.z)