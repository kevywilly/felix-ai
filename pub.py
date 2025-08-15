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

from felix.topics import Topics
from felix.types import Twist, Vector3
from felix.bus import SimpleEventBus


class Publisher(BaseService):
    pass
        


publisher = Publisher()
publisher.start()

while 1:
    publisher.publish_message(Topics.CMD_VEL, Twist(linear=Vector3(x=0.0, y=0.4, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0)).dict)    
    time.sleep(2)
    publisher.publish_message(Topics.CMD_VEL, Twist(linear=Vector3(x=0.0, y=0.0, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0)).dict)    
    time.sleep(2)
    