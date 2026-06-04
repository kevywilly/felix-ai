#!/usr/bin/env python3
import logging
import sys
import time
import faulthandler
# Dump the C/Python stack of every thread to stderr if a fatal signal
# (SIGSEGV/SIGABRT/SIGBUS/...) fires. Enabled before torch/cv2/aiortc load so a
# core dump on exit prints which thread/library faulted (camera vs CUDA vs ...).
faulthandler.enable()
from dataclasses import dataclass
from nicegui import ui, app
import asyncio
import threading
from felix.motion.joystick import Joystick, JoystickRequest
from felix.agents.video_agent import VideoStream

from felix.nodes import (
    Controller, PicoSensors
)
from felix.nodes.robot import Robot
from felix.settings import settings
from felix.signals import Topics

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

@dataclass
class AppState:
    power_percent: int = 60  # default 60%
    xy_lock: bool = False
    autodrive_active: bool = False
    snapshots = {"left": 0, "forward": 0, "right": 0 }
    nav_capture: bool = False
    seek_active: bool = False
    seek_target: str = "person"

from felix.nodes.autodriver import TernaryObstacleAvoider
autodrive = TernaryObstacleAvoider()

# if settings.TRAINING.mode == "ternary":
#    from felix.nodes.autodriver import TernaryObstacleAvoider
#    autodrive = TernaryObstacleAvoider()
#else:
#    from felix.nodes.autodriver import BinaryObstacleAvoider
#    autodrive = BinaryObstacleAvoider()

from felix.nodes.detector import Detector
from felix.nodes.object_seeker import ObjectSeeker

controller = Controller(frequency=30)
pico = PicoSensors()
robot = Robot()
detector = Detector(frequency=8)  # perception only: publishes Topics.detections
object_seeker = ObjectSeeker(target_label="person")  # detections -> cmd_vel

state = AppState()
state.snapshots = robot.get_snapshots("ternary")
state.autodrive_active = autodrive.is_active

# One VideoStream instance so app.on_shutdown can stop it cleanly. It owns its
# own event loop, so it runs on a dedicated thread (kept here for the join).
video_stream = VideoStream()
_video_thread: threading.Thread | None = None

@app.on_startup
async def _start_background_nodes():
    # Launch everything on NiceGUI's own event loop, once, after the server
    # starts. NiceGUI's ui.run() owns the main thread and event loop; spawning
    # a second asyncio.run() or running ui.run() off-thread makes NiceGUI
    # re-execute this script (binding 8554 twice, nesting asyncio.run()).
    global _video_thread
    _video_thread = threading.Thread(target=video_stream.run, daemon=True)
    _video_thread.start()
    for coro in (
        pico.spin(10),
        controller.spin(),
        autodrive.spin(20),
        detector.spin(8),
        object_seeker.spin(8),
    ):
        asyncio.create_task(coro)

@app.on_shutdown
def _stop_background():
    # Release the CSI camera (nvargus) + WebRTC server before the process exits.
    # Without this the daemon thread is killed mid-capture on Ctrl-C and nvargus
    # tears down abruptly -> core dump. shutdown() flips the serve loop's flag;
    # the join waits for run()'s finally to call camera.stop() (cap.release()).
    video_stream.shutdown()
    if _video_thread is not None:
        _video_thread.join(timeout=4)

def _apply_lock(x: float, y: float, strafe: bool) -> tuple[float, float, bool]:
    if state.xy_lock:
        print(x,y,strafe)
        if strafe:
            return (x,0.0, False)
        else:
            return (0.0, y, False)
        # return (0.0, y) if abs(y) > abs(x) else (x, 0.0)
    return x, y, strafe

def handle_joystick(x: float, y: float, strafe: bool = False, power: float | None = None):
    x, y, use_strafe = _apply_lock(x, y, strafe)
    p = (state.power_percent / 100.0) if power is None else power
    req = JoystickRequest(x=x, y=y, strafe=use_strafe, power=p)
    twist = Joystick.get_twist(req)
    Topics.cmd_vel.send("felix", payload=twist)

def handle_snapshot(label: str):
    val = robot.create_snapshot("ternary", label)
    state.snapshots=val
    capture_buttons.refresh()

def handle_autodrive(e):
    state.autodrive_active = not autodrive.is_active
    # mutual exclusion: only one driver may command the robot at a time
    if state.autodrive_active and state.seek_active:
        state.seek_active = False
        object_seeker.activate(False)
    controller.stop()
    Topics.autodrive.send("felix")
    if not state.autodrive_active:
        time.sleep(1)
        controller.stop()
    drive_mode_buttons.refresh()

def handle_seek(e):
    state.seek_active = not state.seek_active
    # mutual exclusion: turn autodrive off if we're enabling seek
    if state.seek_active and autodrive.is_active:
        state.autodrive_active = False
        Topics.autodrive.send("felix")
    controller.stop()
    object_seeker.activate(state.seek_active)
    if not state.seek_active:
        time.sleep(1)
        controller.stop()
    drive_mode_buttons.refresh()

def handle_seek_target(label: str):
    state.seek_target = label
    object_seeker.set_target(label)

def handle_nav_capture(e):
    state.nav_capture = not state.nav_capture
    Topics.nav_capture.send("felix", payload=state.nav_capture)
    capture_buttons.refresh()

def handle_xy_lock(e):
    state.xy_lock = not state.xy_lock
    capture_buttons.refresh()

def _on_left_move(e):
    handle_joystick(e.x, e.y, strafe=False)

def _on_right_move(e):
    handle_joystick(e.x, e.y, strafe=True)

_BTN_STYLE = 'flex: 1 1 0; min-width: 100px; height: 40px;'

@ui.refreshable
def capture_buttons():
    with ui.row().classes('capture-row justify-center items-stretch mt-4').style('gap: 8px;'):
        ui.button(f'Left {state.snapshots.get("left",0)}',
                on_click=lambda: handle_snapshot('left')
                ).style(_BTN_STYLE)
        ui.button(f'Forward {state.snapshots.get("forward",0)}',
                on_click=lambda: handle_snapshot('forward')
                ).style(_BTN_STYLE)
        ui.button(f'Right {state.snapshots.get("right",0)}',
                on_click=lambda: handle_snapshot('right')
                ).style(_BTN_STYLE)
        ui.button(f'LockXY {"On" if state.xy_lock else "Off"}',
                  on_click=lambda e: handle_xy_lock(e)
                  ).style(_BTN_STYLE)
        ui.button(f'NavCap {"On" if state.nav_capture else "Off"}',
                on_click=lambda e: handle_nav_capture(e)
                ).style(_BTN_STYLE)

@ui.refreshable
def drive_mode_buttons():
    # AutoDrive + Seek live in the controls column, below the power slider.
    with ui.row().classes('w-full justify-center items-stretch').style('gap: 8px;'):
        ui.button(f'AutoDrive {"On" if state.autodrive_active else "Off"}',
                on_click=lambda e: handle_autodrive(e)
                ).style('flex: 1 1 0; min-width: 120px; height: 40px;')
        ui.button(f'Seek {"On" if state.seek_active else "Off"}',
                on_click=lambda e: handle_seek(e)
                ).style('flex: 1 1 0; min-width: 120px; height: 40px;')

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

def video_frame():
    with ui.column().classes('video-column').style('width: 968px; max-width: 100vw; margin: 0 auto; padding: 0;'):
        ui.html('''
        <style>
        .video-wrap {
            width: 968px;
            height: 548px;
            max-width: 100vw;
            position: relative;
            background: #333;
            overflow: hidden;
            margin: 0 auto;
            padding: 0;
            box-sizing: border-box;
        }
        .video-wrap iframe {
            width: 968px;
            height: 548px;
            border: 0;
            display: block;
            background: #333;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        .capture-row {
            width: 100%;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        </style>
        ''', sanitize=False)
        with ui.element('div').classes('video-wrap'):
            # sanitize=False is required: NiceGUI's ui.html sanitizes by
            # default and strips <iframe> (and <style>/<script>), which is why
            # the video area rendered as nothing — no iframe, no gray box.
            # allow="autoplay" lets this cross-origin iframe (port 8554 vs the
            # app on 80) autoplay the muted WebRTC video.
            ui.html('<iframe src="http://orin1:8554" scrolling="no" allow="autoplay; fullscreen" allowfullscreen style="width:960px;height:540px"></iframe>', sanitize=False)
        capture_buttons()

ui.add_head_html('''<style>
html, body {
    background: #006CA5 !important;
    color: #fff !important;
    margin: 0 !important;
    padding: 8px !important;            /* was "8" (no unit) -> ignored */
    overflow-x: hidden !important;       /* no horizontal scrollbar... */
    overflow-y: auto !important;         /* ...but let content/menus show */
    height: 100%;
}
.main-grid {
    min-height: unset !important;
}
/* The global white text above would make dropdown options white-on-white
   (Quasar menus have a light background), so only the highlighted item shows.
   Force dark, readable text inside popup menus. */
.q-menu, .q-menu .q-item, .q-menu .q-item__label {
    color: #1a1a1a !important;
}
</style>''')
# New layout: video and buttons side by side, joysticks at bottom
with ui.element('div').classes('main-grid').style('display: grid; grid-template-columns: 968px minmax(280px, 360px); gap: 24px; align-items: start; justify-content: center; width: 100%; padding-top: 8px;'):
    with ui.element('div').classes('video-cell'):
        video_frame()
    # Controls vertically centered next to the video (height matches the 548px
    # video box, so the joysticks line up with the video's vertical center).
    with ui.element('div').classes('controls-cell').style('min-width: 280px; max-width: 360px; height: 548px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 18px;'):
        # Joysticks in a horizontal row, centered
        with ui.row().classes('joystick-row').style('width: 100%; justify-content: center; align-items: center; gap: 40px;'):
            left = ui.joystick(size=100, color='blue', throttle=0.05).style('background: #3895D3; border-radius: 50%;')
            right = ui.joystick(size=100, color='green', throttle=0.05).style('background: #3895D3; border-radius: 50%;')
        left.on_move(_on_left_move)
        left.on_end(lambda: handle_joystick(0, 0, strafe=False))
        right.on_move(_on_right_move)
        right.on_end(lambda: handle_joystick(0, 0, strafe=True))
        # Seek-target selector (roomy spot so its dropdown isn't clipped).
        with ui.row().classes('w-full justify-center items-center').style('gap: 8px;'):
            ui.label('Seek target').classes('text-sm')
            ui.select(
                ['person', 'chair', 'bottle', 'cup', 'sports ball', 'dog', 'cat', 'backpack'],
                value=state.seek_target,
                on_change=lambda e: handle_seek_target(e.value),
            ).props('dense outlined options-dense').style('min-width: 160px;')
        # Power slider, then the AutoDrive / Seek toggles below it.
        power_slider()
        drive_mode_buttons()

# NiceGUI re-imports this module as "__mp_main__" in its server process, so
# guard on both names. ui.run() blocks on the main thread and owns the loop;
# background work is started from app.on_startup above.
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='Robot Control', host="0.0.0.0", port=80, reload=False)