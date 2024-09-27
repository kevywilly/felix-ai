#!/usr/bin/env python3

import asyncio
import logging
import os
from blinker import NamedSignal
from flask_cors import CORS
from flask import Flask, Response, request, render_template
from felix.motion.joystick import Joystick, JoystickRequest
from felix.nodes import Robot
from felix.nodes.camera import Camera
from felix.mock.camera import Camera as MockCamera
from felix.nodes.controller import Controller, ControllerNavRequest
from felix.signals import sig_joystick, sig_nav_target, sig_cmd_vel, sig_autodrive
from lib.interfaces import Twist
from felix.settings import settings

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

app = Flask(__name__)

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

CORS(app)

cors = CORS(app, resource={r"/*": {"origins": "*"}})


def _send(signal: NamedSignal, payload):
    signal.send("robot", payload=payload)
    return payload


@app.route("/healthcheck")
def healthcheck():
    return {"status": "ok"}


@app.get("/")
def _index():
    return render_template("index.html")


@app.route("/api/stream")
def stream():
    return Response(
        app.robot.get_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/api/twist")
def api_twist():
    return sig_cmd_vel.send(
        "robot", payload=Twist.model_validate(request.get_json())
    ).dict


@app.get("/api/autodrive")
def api_get_autodrive():
    return {"status": app.controller.autodrive}


@app.post("/api/autodrive")
def api_set_autodrive():
    sig_autodrive.send("robot", payload=None)
    return {"status": app.controller.autodrive}


@app.post("/api/navigate")
def api_navigate():

    data = request.get_json()
    nav_request = ControllerNavRequest.model_validate(data)
    _send(sig_nav_target, nav_request)

    return data


@app.post("/api/joystick")
def api_joystick():
    data = request.get_json()
    _send(sig_joystick, JoystickRequest.model_validate(data))
    return data

@app.post("/api/snapshots/<folder>/<label>")
def create_snapshot(folder: str, label: str):
    return app.robot.create_snapshot(folder, label)


@app.get("/api/snapshots/<folder>")
def get_snapshots(folder: str):
    return app.robot.get_snapshots(folder)


@app.post("/api/tags")
def add_tag():
    data = request.get_json()
    if data["tag"]:
        return app.robot.save_tag(data["tag"])
    else:
        return app.robot.get_tags()


@app.get("/api/tags")
def get_tags():
    return app.robot.get_tags()


@app.get("/api/image/raw")
def get_image_raw():
    image = app.robot.get_raw_image()
    return {"image_raw": image.tolist()}


async def main():
    app.robot = Robot()
    try:
        app.camera = Camera()
    except:  # noqa: E722
        app.camera = MockCamera()

    app.controller = Controller(frequency=30)
    
    app.joystick = Joystick(curve_factor=settings.JOY_DAMPENING_CURVE_FACTOR)

    asyncio.create_task(app.robot.spin(frequency=0.5))
    asyncio.create_task(app.camera.spin())
    asyncio.create_task(app.controller.spin())
    
    app.run(host="0.0.0.0", port=80, debug=False)


if __name__ == "__main__":
    asyncio.run(main())
