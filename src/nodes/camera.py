import threading
import traitlets
import cv2
from cv2 import VideoCapture
from traitlets.config.configurable import SingletonConfigurable
from settings import settings
import atexit
import numpy as np
from src.nodes.node import Node


class Camera(Node):

    value = traitlets.Any()
    sensor_id = traitlets.Int(default_value=0)

    def __init__(self, **kwargs):
        super(Camera, self).__init__(**kwargs)
        self.sensor_mode = settings.DEFAULT_SENSOR_MODE
        self.spin_frequency = self.sensor_mode.framerate
        self.cap = self._init_camera()
        atexit.register(self.shutdown)

    def _init_camera(self) -> VideoCapture:
        cap = VideoCapture(self.sensor_mode.to_nvargus_string(self.sensor_id))
        ret, frame = cap.read()
        if not ret:
            raise Exception("Could not initialize camera")
        else:
            self.value = frame
            return cap

    def _convert_color(self, frame):
        return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
    

    def _undistort(self, frame):
        return cv2.undistort(frame, settings.CAMERA_MATRIX, settings.DISTORTION_COEFFICIENTS)
    
    
    def _read(self, cap: VideoCapture):
        
        ret, frame = cap.read()

        if not ret:
            self.logger.warn(f"Can't receive frame for cap{self.sensor_id}")
        else:
            frame = self._convert_color(frame)
            frame = self._undistort(frame)
            self.value = frame
            
            
    def spinner(self):
        self._read(self.cap)


    def shutdown(self):
        if self.cap:
            self.cap.release()
        

