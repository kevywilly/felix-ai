import cv2
from cv2 import VideoCapture
from felix.settings import settings

from lib.nodes import BaseNode
from felix.signals import sig_raw_image

class Camera(BaseNode):

    def __init__(self, sensor_id: int = 0, **kwargs):
        super(Camera, self).__init__(**kwargs)
        self.sensor_id = sensor_id
        self.sensor_mode = settings.DEFAULT_SENSOR_MODE
        self.frequency = self.sensor_mode.framerate
        self.cap = self._init_camera()
        self.image = None

        self.loaded()

    def _init_camera(self) -> VideoCapture:
        cap = VideoCapture(self.sensor_mode.to_nvargus_string(self.sensor_id))
        ret, frame = cap.read()
        if not ret:
            raise Exception("Could not initialize camera")
        else:
            self.image = frame
            sig_raw_image.send(self, payload=frame)
            return cap

    def _convert_color(self, frame):
        return cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_I420)

    def _undistort(self, frame):
        return cv2.undistort(
            frame, settings.CAMERA_MATRIX, settings.DISTORTION_COEFFICIENTS
        )

    def _read(self, cap: VideoCapture):
        if not cap.isOpened():
            return

        ret, frame = cap.read()

        if not ret:
            self.logger.warn(f"Can't receive frame for cap{self.sensor_id}")
        else:
            frame = self._convert_color(frame)
            frame = self._undistort(frame)
            self.image = frame
            sig_raw_image.send(self, payload=frame)
            """
            try:
                cv2.namedWindow("felix", cv2.WINDOW_NORMAL)
                i2 = cv2.resize(frame, (300,300), cv2.INTER_LINEAR)
                cv2.imshow("felix", i2)
                cv2.waitKey(0)
            except Exception as ex:
                raise ex
                pass
            """

    def spinner(self):
        self._read(self.cap)

    def shutdown(self):
        try:
            
            cv2.destroyAllWindows()
        except:  # noqa: E722
            pass

        try:
            self.cap.release()
        except:  # noqa: E722
            pass
