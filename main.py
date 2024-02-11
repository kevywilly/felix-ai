#!/usr/bin/env python3

from typing import Dict
from src.motion.joystick import JoystickUpdateEvent
from src.motion.kinematics import Kinematics
from src.interfaces.msg import Odometry, Twist
from src.nodes.robot import Robot
import logging
import os
from flask_cors import CORS
from flask import Flask, Response, jsonify, request

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

CORS(app)

cors = CORS(app, resource={
    r"/*": {
        "origins": "*"
    }
})

@app.route('/')
def index():
    return {"status": "ok"}

@app.route('/api/stream')
def stream():
    return Response(app.robot.get_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.post('/api/twist')
def api_twist():
    return app.robot.handle_twist(request.get_json()).dict()
    
    
@app.get('/api/autodrive')
def api_get_autodrive():
    return {'status': app.robot.get_autodrive()}


@app.post('/api/autodrive')
def api_set_autodrive():
    return {'status': app.robot.toggle_autodrive()}


@app.post('/api/navigate')
def api_navigate():
    return {'captured' : app.robot.handle_navigate(request.get_json())}


@app.post('/api/joystick')
def api_joystick():
    return app.robot.handle_joystick(request.get_json()).dict()
    

@app.post('/api/tags')
def add_tag():
    data = request.get_json()
    if data['tag']:
        return app.robot.save_tag(data['tag'])
    else:
        return app.robot.get_tags()


@app.get('/api/tags')
def get_tags():
    return app.robot.get_tags()


if __name__ == "__main__":
    app.robot: Robot = Robot(capture_when_driving=False)
    app.robot.spin(frequency=0.5)
    app.run(host='0.0.0.0', debug=False)
