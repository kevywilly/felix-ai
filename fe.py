from dataclasses import dataclass
import time

import streamlit as st
from st_joystick import st_joystick
from felix.bus import SimpleEventBus
from felix.motion.joystick import Joystick, JoystickRequest
from felix.service.base import BaseService
from felix.topics import Topics
import logging

from felix.types import Twist, Vector3 

logging.basicConfig(level=logging.DEBUG)

#if "bus" not in st.session_state:
#    st.session_state.bus = SimpleEventBus(port=5555)

class Publisher(BaseService):
    def __init__(self):
        super().__init__("Publisher", SimpleEventBus(port=5555))
        self.logger = logging.getLogger("Publisher")
        self.logger.setLevel(logging.DEBUG)

p = Publisher()

p.start()

p.publish_message(Topics.CMD_VEL, Twist(linear=Vector3(x=0.0, y=0.7, z=0.0), angular=Vector3(x=0.0, y=0.0, z=0.0)).dict)

while True:
    time.sleep(1)
"""
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
    
def _handle_joystick(value: JoystickValue):
    req = JoystickRequest(x=value.x, y=value.y, strafe=value.strafe, power=value.power)
    twist = Joystick.get_twist(req)
    p.publish_message(Topics.CMD_VEL, twist.dict)

@st.fragment
def left_joystick():
    value = st_joystick(options={'size': 150}, id=0) # default joystick id for the zone element = 0
    if value:
        # You can access the joystick values like this
        pos = JoystickValue.from_dict(value)
        st.write(value.get("vector", {}))
        _handle_joystick(pos)

@st.fragment
def right_joystick():
    value = st_joystick(options={'size': 150}, id=1) #remember to set the zone element id for subsequent joysticks
    if value:
        pos = JoystickValue.from_dict(value)
        pos.strafe = True
        st.write(value.get("vector", {}))
        _handle_joystick(pos)

st.markdown('''
<style>
body {
    overflow-y: hidden; /* Hide vertical scrollbar */
    overflow-x: hidden; /* Hide horizontal scrollbar */
}
</style>
''', unsafe_allow_html=True)

st.set_page_config(page_title="Robot Control", layout="centered")
st.components.v1.iframe("https://orin1:8554/", width=720, height=405)

cols = st.columns(2)
with cols[0]:
    left_joystick()
with cols[1]:
    right_joystick() 
"""