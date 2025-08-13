from dataclasses import dataclass
import time
import streamlit as st
from st_joystick import st_joystick
import asyncio
import threading
import logging
import os
from blinker import NamedSignal
from flask_cors import CORS
from flask import Flask, Response, request, render_template
from felix.motion.joystick import Joystick, JoystickRequest
from felix.agents.video_agent import VideoStream

from felix.nodes import (
    Controller,
    Robot,
)

from felix.nodes.controller import NavRequest
from felix.nodes.tof_cluster import TOFCluster
from felix.signals import (
    sig_joystick,
    sig_nav_target,
    sig_cmd_vel,
    sig_autodrive,
    sig_stop,
)
from lib.interfaces import Twist
from felix.settings import settings

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

# setup core components

robot = Robot()
# if not settings.MOCK_MODE else MockCamera()
# chat_node = ChatNode()
controller = Controller(frequency=30)
joystick = Joystick(curve_factor=settings.JOY_DAMPENING_CURVE_FACTOR)
tof = TOFCluster(debug=False)

if settings.TRAINING.mode == "ternary":
    from felix.nodes.autodriver import TernaryObstacleAvoider

    autodrive = TernaryObstacleAvoider()
else:
    from felix.nodes.autodriver import BinaryObstacleAvoider

    autodrive = BinaryObstacleAvoider()


def _send(signal: NamedSignal, payload):
    signal.send("robot", payload=payload)
    return payload

def run_async_tasks():
    async def tasks():
        await asyncio.gather(
            controller.spin(),
            autodrive.spin(20),
            tof.spin(10)
        )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(tasks())

def start_video():
    # args = {'video_input': 'csi://0', 'video_output': 'webrtc://@:8554/output', 'log_level': "info"}
    VideoStream().run()

@dataclass
class JoystickValue:
    x: float = 0.0
    y: float = 0.0
    strafe: bool = False
    power: float = 0.6

    @property
    def stopped(self) -> bool:
        return self.x == 0.0 and self.y == 0.0

    @classmethod
    def from_dict(cls, data: dict):
        pos = data.get('vector', {})
        x = pos.get('x', 0.0)
        y = pos.get('y', 0.0)
        return JoystickValue(x,y)


@st.fragment
def left_joystick():
    value = st_joystick(options={'size': 200}, id=0) # default joystick id for the zone element = 0
    # st.write(value)
    print(value)
    if value:
        # You can access the joystick values like this
        pos = JoystickValue.from_dict(value)
        st.write(value.get("vector", {}))

@st.fragment
def right_joystick():
    value = st_joystick(options={'size': 200}, id=1) #remember to set the zone element id for subsequent joysticks
    # st.write(value)
    if value:
        pos = JoystickValue.from_dict(value)
        st.write(value.get("vector", {}))

def display():
    st.set_page_config(page_title="Robot Control", layout="wide")

    st.title("Robot Control Interface")

    st.title("Felix Video Stream")
    st.components.v1.iframe("https://orin1:8554/", width=1280, height=720)
    cols = st.columns(3, gap="small")
    with cols[0]:
        st.header("Left Joystick")
        left_joystick()
    with cols[1]:
        pass
    with cols[2]:
        st.header("Right Joystick")
        right_joystick()



# Use Streamlit singleton to ensure only one thread per app session
@st.cache_resource
def get_video_thread():
    t = threading.Thread(target=start_video, daemon=True)
    t.start()
    return t

@st.cache_resource
def get_async_thread():
    t = threading.Thread(target=run_async_tasks, daemon=True)
    t.start()
    return t

get_video_thread()
get_async_thread()

display()
        

