import traitlets
from traitlets.config.configurable import SingletonConfigurable
from src.models.vector import Vector3
from src.nodes.controller import Controller
import time
import logging
import atexit
from src.nodes.node import Node

logger = logging.getLogger(__name__)

class Robot(Node):

    def __init__(self, *args, **kwargs):
        super(Robot, self).__init__(name="Felix", *args, **kwargs)
        logger.info("Starting all systems...")
        self._controller: Controller = Controller.instance()
        self._controller.spin()
        #self._controller.observe(self._on_controller_data_change)
        

    def set_velocity(self, value: Vector3):
        self._controller.cmd_vel=value

    def _on_controller_data_change(self, change):
        #if(change["name"]=="motion_data"):
        print(change['name'], change['new'])

        
