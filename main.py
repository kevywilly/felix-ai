#!/usr/bin/env python3

import logging
import os
from flask_cors import CORS
from flask import Flask, Response, request, jsonify, render_template
from src.nodes.robot import Robot
from settings import settings

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

@app.route('/healthcheck')
def healthcheck():
    return {"status": "ok"}

@app.get('/')
def _index():
    return render_template('index.html')

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
    

@app.post('/api/snapshots/<folder>/<label>')
def create_snapshot(folder: str, label: str):
    return app.robot.create_snapshot(folder, label)


@app.get('/api/snapshots/<folder>')
def get_snapshots(folder: str):
    return app.robot.get_snapshots(folder)


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

@app.get('/api/image/raw')
def get_image_raw():
    image =  app.robot.get_raw_image()
    return {"image_raw": image.tolist()}


if __name__ == "__main__":
    app.robot = Robot(capture_when_driving=settings.capture_when_driving)
    app.robot.spin(frequency=0.5)
    app.run(host='0.0.0.0', port=80, debug=False)
