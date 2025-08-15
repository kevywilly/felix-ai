#!/usr/bin/env python3

import logging
import time

from felix.service.base import BaseService
logging.basicConfig(level=logging.DEBUG )
import asyncio
import click
"""
import felix.service.video as video
import felix.service.autodrive as autodrive


import felix.service.tof as tof"""
from felix.service.robot import RobotService
from felix.topics import Topics
from felix.types import Twist, Vector3
from felix.bus import SimpleEventBus
import felix.service.controller as controller

class Subscriber(BaseService):
    def __init__(self):
        super().__init__()
        self.event_bus.subscribe(Topics.CMD_VEL, self.on_cmd_vel)

    def on_cmd_vel(self, message):
        print(f"Received CMD_VEL: {message}")



subscriber = Subscriber()
subscriber.start()

while 1:
    time.sleep(0.1)
    