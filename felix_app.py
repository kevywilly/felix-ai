#!/usr/bin/env python3
import logging 
import sys

from lib.interfaces import Twist
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

import os
import time
from dataclasses import dataclass
from nicegui import ui
import asyncio
import threading
from felix.motion.joystick import Joystick, JoystickRequest
from felix.agents.video_agent import VideoStream

from felix.nodes import (
    Controller,
)
from felix.nodes.robot import Robot
from felix.nodes.tof_cluster import TOFCluster
from felix.settings import settings
from felix.signals import Topics

@dataclass
class AppState:
    power_percent: int = 60  # default 60%
    xy_lock: bool = False
    autodrive_active: bool = False
    snapshots = {"left": 0, "forward": 0, "right": 0 }

if settings.TRAINING.mode == "ternary":
    from felix.nodes.autodriver import TernaryObstacleAvoider
    autodrive = TernaryObstacleAvoider()
else:
    from felix.nodes.autodriver import BinaryObstacleAvoider
    autodrive = BinaryObstacleAvoider()

controller = Controller(frequency=30)
tof = TOFCluster(debug=False)

robot = Robot()

state = AppState()
state.snapshots = robot.get_snapshots("ternary")
state.autodrive_active = autodrive.is_active

def start_flask():
    ui.run(title='Robot Control', host="0.0.0.0", port=80, reload=False, )


def start_video():
    # args = {'video_input': 'csi://0', 'video_output': 'webrtc://@:8554/output', 'log_level': "info"}
    VideoStream().run()
    return


async def main():
    await asyncio.gather(
        tof.spin(10),
        controller.spin(), 
        autodrive.spin(20)
    )

def _apply_lock(x: float, y: float) -> tuple[float, float]:
    if state.xy_lock:
        return (0.0, y) if y > x else (x, 0.0)
    
    return x, y

def handle_joystick(x: float, y: float, strafe: bool = False, power: float | None = None):
    x, y = _apply_lock(x, y)
    p = (state.power_percent / 100.0) if power is None else power
    req = JoystickRequest(x=x, y=y, strafe=strafe, power=p)
    twist = Joystick.get_twist(req)
    Topics.cmd_vel.send("felix", payload=twist)

def handle_snapshot(label: str):
    val = robot.create_snapshot("ternary", label)
    state.snapshots=val
    capture_buttons.refresh()

def handle_autodrive(e):
    state.autodrive_active = not autodrive.is_active
    controller.stop() 
    Topics.autodrive.send("felix")
    if not state.autodrive_active:
        time.sleep(1)
        controller.stop()
    settings_buttons.refresh()

def handle_xy_lock(e):
    state.xy_lock = not state.xy_lock

def _on_left_move(e):
    handle_joystick(e.x, e.y, strafe=False)

def _on_right_move(e):
    handle_joystick(e.x, e.y, strafe=True)

@ui.refreshable
def capture_buttons():
    with ui.row().classes('w-full justify-center items-start mt-4').style('gap: 24px;'):
        # Capture buttons (horizontal)
        with ui.row().classes('w-full max-w-3xl justify-center').style('gap: 8px; flex-wrap: nowrap;'):
            ui.button(f'Left {state.snapshots.get("left",0)}',
                    on_click=lambda: handle_snapshot('left')
                    ).style('flex: 1 1 0; min-width: 140px;')
            ui.button(f'Forward {state.snapshots.get("forward",0)}',
                    on_click=lambda: handle_snapshot('forward')
                    ).style('flex: 1 1 0; min-width: 140px;')
            ui.button(f'Right {state.snapshots.get("right",0)}',
                    on_click=lambda: handle_snapshot('right')
                    ).style('flex: 1 1 0; min-width: 140px;')

def video_frame():
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

@ui.refreshable
def settings_buttons():
    with ui.row().classes('w-full justify-center items-start mt-2').style('gap: 12px;'):
        with ui.row().classes('w-full max-w-3xl justify-center').style('gap: 8px; flex-wrap: nowrap;'):                
            ui.button(f'Lock XY: {state.xy_lock}', on_click=lambda e: handle_xy_lock(e)).style('flex: 1 1 0; min-width: 160px;')

            ui.button(f'Auto Drive {"On" if state.autodrive_active else "Off"}',
                    on_click=lambda e: handle_autodrive(e)
                    ).style('flex: 1 1 0; min-width: 160px;')
            
def joysticks():
    with ui.row().classes('w-full justify-center items-start mt-2').style('gap: 64px; flex-wrap: wrap;'):
        with ui.column().classes('items-center').style('padding: 12px;'):
            left = ui.joystick(size=160, color='blue', throttle=0.05)
        left.on_move(_on_left_move)
        left.on_end(lambda: handle_joystick(0, 0, strafe=False))

        with ui.column().classes('items-center').style('padding: 12px;'):
            right = ui.joystick(size=160, color='green', throttle=0.05)
        right.on_move(_on_right_move)
        right.on_end(lambda: handle_joystick(0, 0, strafe=True))

def power_slider():
    with ui.row().classes('w-full justify-center items-center mt-1 mb-4').style('gap: 12px;'):
        power_label = ui.label(f"Power: {state.power_percent}%").classes('text-sm')
        def _on_power_change(v):
            state.power_percent = int(v)
            power_label.text = f"Power: {state.power_percent}%"
            power_label.update()
        ui.slider(min=0, max=100, value=state.power_percent, step=1) \
            .style('min-width: 300px; width: min(60vw, 640px);') \
            .on_value_change(lambda e: _on_power_change(e.value))
        
video_frame()
capture_buttons()
settings_buttons()
power_slider()
joysticks()
    
if __name__ == "__main__":
    try:
        
        video_thread = threading.Thread(target=start_video)
        video_thread.daemon = True
        video_thread.start()

        flask_thread = threading.Thread(target=start_flask)
        flask_thread.daemon = True
        flask_thread.start()


        asyncio.run(main())
    finally:
        video_thread.join()
        flask_thread.join()

