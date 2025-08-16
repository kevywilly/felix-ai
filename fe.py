#!/usr/bin/env python3

from nicegui import ui
from felix.bus import SimpleEventBus
from felix.motion.joystick import Joystick, JoystickRequest
from felix.topics import Topics
import time

bus = SimpleEventBus()

# UI state
power_percent = 60  # default 60%
lock_mode = 'free'  # 'free' | 'lock_x' | 'lock_y'

def _apply_lock(x: float, y: float) -> tuple[float, float]:
    global lock_mode
    if lock_mode == 'lock_x':
        return 0.0, y
    if lock_mode == 'lock_y':
        return x, 0.0
    return x, y

def handle_joystick(x: float, y: float, strafe: bool = False, power: float | None = None):
    global power_percent
    x, y = _apply_lock(x, y)
    p = (power_percent / 100.0) if power is None else power
    req = JoystickRequest(x=x, y=y, strafe=strafe, power=p)
    twist = Joystick.get_twist(req)
    bus.publish(Topics.CMD_VEL, twist.dict, f"ui-{int(time.time()*1000)}")


def _on_left_move(e):
    handle_joystick(e.x, e.y, strafe=False)

def _on_right_move(e):
    handle_joystick(e.x, e.y, strafe=True)

with ui.row().classes('w-full'):
    ui.html('''
    <style>
      .video-wrap {
        width: 100%;
        /* keep 16:9 while allowing it to shrink/grow */
        aspect-ratio: 16 / 9;
        /* never taller than half the viewport */
        max-height: 50vh;
        /* when capped by height, limit width to preserve 16:9: width = 50vh * 16/9 */
        max-width: calc(50vh * 16 / 9);
        margin: 0 auto; /* center when width is capped */
      }
      .video-wrap iframe {
        width: 100%;
        height: 100%;
        border: 0;
      }
    </style>
    <div class="video-wrap">
      <iframe src="https://orin1:8554" scrolling="no"></iframe>
    </div>
    ''').classes('w-full')

with ui.row().classes('w-full justify-center items-start mt-4').style('gap: 24px;'):
    # Capture buttons (horizontal)
    with ui.row().classes('w-full max-w-3xl justify-center').style('gap: 8px; flex-wrap: nowrap;'):
        ui.button('Left',
                  on_click=lambda: bus.publish('capture', {'label': 'Left'}, f"ui-{int(time.time()*1000)}")
                 ).style('flex: 1 1 0; min-width: 140px;')
        ui.button('Forward',
                  on_click=lambda: bus.publish('capture', {'label': 'Forward'}, f"ui-{int(time.time()*1000)}")
                 ).style('flex: 1 1 0; min-width: 140px;')
        ui.button('Right',
                  on_click=lambda: bus.publish('capture', {'label': 'Right'}, f"ui-{int(time.time()*1000)}")
                 ).style('flex: 1 1 0; min-width: 140px;')

    # Settings buttons
with ui.row().classes('w-full justify-center items-start mt-2').style('gap: 12px;'):
    with ui.row().classes('w-full max-w-3xl justify-center').style('gap: 8px; flex-wrap: nowrap;'):
        def _toggle_lock():
            global lock_mode
            lock_mode = 'lock_x' if lock_mode == 'free' else ('lock_y' if lock_mode == 'lock_x' else 'free')
            lock_btn.text = f"Lock XY: {'X only' if lock_mode=='lock_y' else ('Y only' if lock_mode=='lock_x' else 'Off')}"
        lock_btn = ui.button('Lock XY: Off', on_click=_toggle_lock).style('flex: 1 1 0; min-width: 160px;')

        ui.button('Auto Drive',
                  on_click=lambda: bus.publish(Topics.AUTODRIVE, {}, f"ui-{int(time.time()*1000)}")
                 ).style('flex: 1 1 0; min-width: 160px;')

# Joysticks row
with ui.row().classes('w-full justify-center items-start mt-2').style('gap: 64px; flex-wrap: wrap;'):
    with ui.column().classes('items-center').style('padding: 12px;'):
        left = ui.joystick(size=160, color='blue', throttle=0.05)
    left.on_move(_on_left_move)
    left.on_end(lambda: handle_joystick(0, 0, strafe=False))

    with ui.column().classes('items-center').style('padding: 12px;'):
        right = ui.joystick(size=160, color='green', throttle=0.05)
    right.on_move(_on_right_move)
    right.on_end(lambda: handle_joystick(0, 0, strafe=True))

# Horizontal power slider below joysticks
with ui.row().classes('w-full justify-center items-center mt-2 mb-12').style('gap: 12px;'):
    power_label = ui.label(f"Power: {power_percent}%").classes('text-sm')
    def _on_power_change(v):
        global power_percent
        power_percent = int(v)
        power_label.text = f"Power: {power_percent}%"
        power_label.update()
    ui.slider(min=0, max=100, value=power_percent, step=1) \
        .style('min-width: 300px; width: min(60vw, 640px);') \
        .on_value_change(lambda e: _on_power_change(e.value))

    
ui.run(title='Robot Control', host="0.0.0.0", port=80, reload=False, )