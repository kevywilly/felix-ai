#!/usr/bin/env python3

import asyncio
import threading
import logging
import os
from blinker import NamedSignal
from flask_cors import CORS
from flask import Flask, Response, request, render_template
from felix.motion.joystick import Joystick, JoystickRequest
from nano_llm.utils import ArgParser
from video_agent import VideoStream

from felix.nodes import (
    Controller,
    Robot,
)

from felix.nodes.controller import  NavRequest
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

app = Flask(__name__)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

CORS(app)

CORS(app, resources={r"/generate": {"origins": "*"}})

robot = Robot()
# if not settings.MOCK_MODE else MockCamera()
# chat_node = ChatNode()

controller = Controller(frequency=30)
joystick = Joystick(curve_factor=settings.JOY_DAMPENING_CURVE_FACTOR)

if settings.TRAINING.mode == "ternary":
    from felix.nodes.autodriver import TernaryObstacleAvoider
    autodrive = TernaryObstacleAvoider()
else:
    from felix.nodes.autodriver import BinaryObstacleAvoider
    autodrive = BinaryObstacleAvoider()

def _send(signal: NamedSignal, payload):
    signal.send("robot", payload=payload)
    return payload


@app.route("/healthcheck")
def healthcheck():
    return {"status": "ok"}


@app.get("/")
def _index():
    return render_template("index.html")


@app.post("/api/stop")
def _stop():
    sig_stop.send("robot")
    return {"status": "ok"}


@app.route("/api/stream")
def stream():
    return Response(
        robot.get_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/api/twist")
def api_twist():
    return sig_cmd_vel.send(
        "robot", payload=Twist.model_validate(request.get_json())
    ).dict


@app.get("/api/autodrive")
def api_get_autodrive():
    return {"status": autodrive.is_active}


@app.post("/api/autodrive")
def api_set_autodrive():
    sig_autodrive.send("robot")
    return {"status": autodrive.is_active}


@app.post("/api/navigate")
def api_navigate():
    data = request.get_json()
    nav_request = NavRequest.model_validate(data)
    _send(sig_nav_target, nav_request)

    return data


@app.post("/api/joystick")
def api_joystick():
    data = request.get_json()
    _send(sig_joystick, JoystickRequest.model_validate(data))
    return data


@app.post("/api/snapshots/<folder>/<label>")
def create_snapshot(folder: str, label: str):
    return robot.create_snapshot(folder, label)


@app.get("/api/snapshots/<folder>")
def get_snapshots(folder: str):
    return robot.get_snapshots(folder)


@app.post("/api/tags")
def add_tag():
    data = request.get_json()
    if data["tag"]:
        return robot.save_tag(data["tag"])
    else:
        return robot.get_tags()


@app.get("/api/tags")
def get_tags():
    return robot.get_tags()


@app.get("/api/image/raw")
def get_image_raw():
    image = robot.get_raw_image()
    return {"image_raw": image.tolist()}


"""
@app.get("/api/describe")
def describe():
    response = chat_node.chat()
    return {"response": response}


@app.post("/api/chat")
def chat():
    prompt = request.get_json().get("prompt", "Describe the image!")
    reply = chat.chat(prompt=prompt)
    return {"reply": reply}

"""

def start_flask():
    app.run(host="0.0.0.0", port=80, debug=False)


def start_video():
    args = {'video_input': 'csi://0', 'video_output': 'webrtc://@:8554/output', 'log_level': "info"}
    agent = VideoStream(**args).run()

async def main():
    await asyncio.gather(
        controller.spin(),
        autodrive.spin(20)
    )


if __name__ == "__main__":
   
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    video_thread = threading.Thread(target=start_video)
    video_thread.daemon = False
    video_thread.start()

    asyncio.run(main())
