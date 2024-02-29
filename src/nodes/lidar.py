import traitlets
import cv2
from cv2 import VideoCapture
from settings import settings
from src.nodes.node import Node
from src.vision.image import ImageUtils
from rplidar import RPLidar
import numpy as np

class Lidar(Node):
    value = traitlets.Any()
    scanning = traitlets.Bool(default_value = False)
    def __init__(self, **kwargs):
        super(Lidar, self).__init__(**kwargs)

        self.lidar = RPLidar('/dev/rplidar')
        self.lidar.reset()
        info = self.lidar.get_info()
        self.loaded()
        self.logger.info(info)
        # self.start_scan(3)
        

    def start_scan(self, retries = 3):
        count = 0
        while count < retries:
            try: 
                self.scan()
                self.scanning = True
                break
            except Exception as ex:
                self.lidar.reset()
                self.scanning = False
                self.logger.error(ex.__str__())


    def spinner(self):
        if not self.scanning:
            self.start_scan()

    def scan(self):
        for i, scan in enumerate(self.lidar.iter_scans()):
            self.value = np.array(scan).astype(int)
            # self.logger.info(self.value)

    def shutdown(self):
        self.lidar.stop()
        self.lidar.stop_motor()