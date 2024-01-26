import math
from math import atan, atan2
from turtle import distance
from typing import Dict
from src.interfaces.joystick import JoystickEventType, JoystickUpdateEvent
from src.utils.kinematics import Kinematics
from src.interfaces.msg import Odometry, Twist, Vector3
from src.nodes.robot import Robot
import logging
import os
import time
import flask
from flask_cors import CORS
from flask import Flask, Response, jsonify, request
import cv2

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

app = Flask(__name__)
CORS(app)
cors = CORS(app, resource={
    r"/*": {
        "origins": "*"
    }
})

app.robot: Robot = Robot()

def _get_stream():
    while True:
        # ret, buffer = cv2.imencode('.jpg', frame)
        try:
            yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + app.robot.get_image() + b'\r\n'
            )  # concat frame one by one and show result
        except Exception as ex:
            pass

def _joystick(data: Dict) -> Twist:
    event: JoystickUpdateEvent = JoystickUpdateEvent(**data)
    t: Twist = event.get_twist()
    app.robot.set_cmd_vel(t)
    return t
        
def _twist(data: Dict) -> Twist:
    t = Twist()
    t.linear.x = float(data["linear"]["x"])
    t.linear.y = float(data["linear"]["y"])
    t.angular.z = float(data["angular"]["z"])
    app.robot.set_cmd_vel(t)
    return t

def _navigate(data: Dict) -> Odometry:

    x = int(data["cmd"]["x"])
    y = int(data["cmd"]["y"])
    w = int(data["cmd"]["w"])
    h = int(data["cmd"]["h"])

    driveMode = data["driveMode"]
    captureMode = data["captureMode"]

    odom = Kinematics.xywh_to_nav_target(x,y,w,h)

    if driveMode:
        app.robot.set_nav_target(odom)

    if captureMode:
        #self.collect_x_y(x,y,w,h)
        pass

    return odom

@app.route('/')
def index():
    return {"status": "ok"}

@app.route('/api/stream')
def stream():
    return Response(_get_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.post('/api/twist')
def api_twist():
    return _twist(request.get_json()).dict()
    
    
@app.post('/api/navigate')
def api_navigate():
    return _navigate(request.get_json()).dict()

@app.post('/api/joystick')
def api_joystick():
    return _joystick(request.get_json()).dict()
    

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)