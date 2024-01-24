from src.models.vector import Vector3
from src.nodes.robot import Robot
import logging
import os
import time
import flask
from flask_cors import CORS
from flask import Flask, Response, jsonify, request


logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

app = Flask(__name__)
CORS(app)
cors = CORS(app, resource={
    r"/*": {
        "origins": "*"
    }
})

app.robot: Robot = Robot.instance()

@app.route('/')
def index():
    return {"status": "ok"}


@app.post('/cmd_vel')
def cmd_vel():
    d = request.get_json()
    v = Vector3(**d)
    app.robot.set_velocity(v)
    return v.json()
    

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)