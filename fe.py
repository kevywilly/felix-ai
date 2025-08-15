# ui_app.py
from nicegui import ui
from felix.bus import SimpleEventBus
from felix.motion.joystick import Joystick, JoystickRequest
from felix.topics import Topics
import time

bus = SimpleEventBus()

def handle_joystick(x: float, y: float, strafe: bool = False, power: float = 0.6):
    req = JoystickRequest(x=x, y=y, strafe=strafe, power=power)
    twist = Joystick.get_twist(req)
    bus.publish(Topics.CMD_VEL, twist.dict, f"ui-{int(time.time()*1000)}")


def _on_left_move(e):
    handle_joystick(e.x, e.y, strafe=False)

def _on_right_move(e):
    handle_joystick(e.x, e.y, strafe=True)

with ui.row().classes('w-full'):
    ui.html('''
    <div style="position:relative;padding-top:56.25%;overflow:hidden;">
      <iframe src="https://orin1:8554/"
              style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;overflow:hidden;"
              scrolling="no"></iframe>
    </div>
    ''').classes('w-full')

with ui.row().classes('w-full justify-center items-start mt-4 mb-12').style('gap: 64px; flex-wrap: wrap;'):
    with ui.column().classes('items-center').style('padding: 12px;'):
        left = ui.joystick(size=160, color='blue', throttle=0.05)
    left.on_move(_on_left_move)
    left.on_end(lambda: handle_joystick(0, 0, strafe=False))

    with ui.column().classes('items-center').style('padding: 12px;'):
        right = ui.joystick(size=160, color='green', throttle=0.05)
    right.on_move(_on_right_move)
    right.on_end(lambda: handle_joystick(0, 0, strafe=True))
    
ui.run(title='Robot Control', host="0.0.0.0", port=80, reload=False, )