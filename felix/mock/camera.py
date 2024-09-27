from functools import cached_property
import traitlets
import cv2
from felix.settings import settings
from lib.nodes import BaseNode
from felix.vision.image import ImageUtils

class VideoCapture:
    def __init__(self, *args):
        pass
    
    @cached_property
    def frame(self):
        return cv2.imread("felix/mock/camera_image.jpg")
    
    def read(self):
        return True, self.frame
    
    def release(self):
        return
    
    def isOpened(self):
        return True

    def __del__(self):
        pass

class Camera(BaseNode):

    value = traitlets.Any()
    sensor_id = traitlets.Int(default_value=0)

    def __init__(self, **kwargs):
        super(Camera, self).__init__(**kwargs)
        self.sensor_mode = settings.DEFAULT_SENSOR_MODE
        self.frequency = self.sensor_mode.framerate
        self.cap = self._init_camera()

        self.loaded()

    def _init_camera(self) -> VideoCapture:
        cap = VideoCapture(self.sensor_mode.to_nvargus_string(self.sensor_id))
        ret, frame = cap.read()
        if not ret:
            raise Exception("Could not initialize camera")
        else:
            self.value = frame
            return cap

    def _convert_color(self, frame):
        return frame #cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)
    

    def _undistort(self, frame):
        return cv2.undistort(frame, settings.CAMERA_MATRIX, settings.DISTORTION_COEFFICIENTS)
    
    
    def _read(self, cap: VideoCapture):
        
        if not cap.isOpened():
            return
        
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
        try:
            cv2.destroyAllWindows()
        except:  # noqa: E722
            pass
        if self.cap:
            self.cap.release()

        


