#!/usr/bin/env python3

import logging
logging.basicConfig(level=logging.DEBUG )
import asyncio
import click
"""
import felix.service.video as video
import felix.service.autodrive as autodrive

import felix.service.controller as controller
import felix.service.tof as tof"""
from felix.service.robot import RobotService
from felix.topics import Topics
from felix.types import Twist, Vector3
from felix.bus import SimpleEventBus


bus = SimpleEventBus(port=5555)

async def control():
    print("Starting control loop")
    robot = RobotService(bus)
    robot.start()

    while 1:
        robot.publish_message(Topics.CMD_VEL, Twist(linear=Vector3(x=0.0, y=0.7, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0)).dict)
        await asyncio.sleep(1)
        robot.publish_message(Topics.CMD_VEL, Twist().dict)
        await asyncio.sleep(1)


"""
async def runall():
    await asyncio.gather(
        tof.run(10),
        controller.run(10),
        autodrive.run(10),
        video.run(10),
         
        control()
    )
"""


@click.command()
@click.option('--log-level', default='INFO', help='Logging level')
def cli(log_level):

    #logging.basicConfig(level=getattr(logging, log_level.upper()))
    asyncio.run(control())

    
if __name__ == "__main__":
    asyncio.run(cli())

