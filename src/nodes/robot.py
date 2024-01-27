import os
from typing import Optional
import traitlets
from settings import settings
from src.utils.image import Image, ImageUtils
from src.interfaces.msg import Odometry, Twist
from src.nodes.node import Node
from src.nodes.controller import Controller
from src.nodes.camera import Camera
import time
import numpy as np
import atexit

class Robot(Node):

    image = traitlets.Instance(Image)
    capture_when_driving = traitlets.Bool(default_value=False)
    capture_when_driving_frequency = traitlets.Float(default_value=0.5)

    def __init__(self, **kwargs):
        super(Robot, self).__init__(**kwargs)
        
        self.image = Image()
        self._camera: Camera = Camera()
        self._controller: Controller = Controller()
        self._controller.spin()
        self._camera.spin()
        self._setup_subscriptions()
        self.last_capture_time = time.time()
        self._make_folders()
        self._nav_data = np.zeros(3*4)

        atexit.register(self._remove_subscriptions)
        
    def _make_folders(self):
        try:
            os.makedirs(settings.Data.driving_data_path)
        except FileExistsError:
            pass

    def _setup_subscriptions(self):
        traitlets.dlink((self._camera, 'value'), (self.image, 'value'), transform=ImageUtils.bgr8_to_jpeg)
        self._controller.observe(self._motion_changed, names=["motion_data"])


    def _remove_subscriptions(self):
        self._camera.unobserve_all()
        self._controller.unobserve_all()


    def _motion_changed(self, changed):
        if changed.new != changed.old:
            self.logger.info(changed.new)
        

    def get_image(self):
        return self.image.value
    
    
    def set_nav_target(self, msg: Odometry):
        self._controller.nav_target=msg


    def set_cmd_vel(self, msg: Twist):
        self._controller.cmd_vel=msg

    
    def spinner(self):
        self._capture()
        

    def _prepare_nav_data(self) -> np.ndarray:
        return np.concatenate(
            (
                self._controller.motion_data.numpy(),
                self._controller.attitude_data.numpy(),
                self._controller.gyroscope_data.numpy(),
                self._controller.accelerometer_data.numpy()   
            )
        )
    
    def _nav_data_unchanged(self, nav_data: np.ndarray) -> bool:
        return min(self._nav_data[:3] == nav_data[:3]) 
    
    def _capture(self):
        t = time.time()
        if not self.capture_when_driving:
            return
        
        if (t-self.last_capture_time) < 1.0/self.capture_when_driving_frequency:
            return
            
        nav_data = self._prepare_nav_data()

        if self._nav_data_unchanged(nav_data):
            return
            
        
        filepath = self._take_snapshot(path = settings.Data.driving_data_path)
        if filepath:
            self._save_motion_data_to_csv(filepath, nav_data)
        self.last_capture_time = t
        self.logger.info("captured")


    def _save_motion_data_to_csv(self, image_filepath: str, nav_data: np.ndarray):
        data_filepath = image_filepath.replace('.jpg', ".label.csv")
        image_file_name = image_filepath.split("/")[-1]
       
        csv = image_file_name + "," + ",".join(
            [f"{item}" for item in nav_data]
        ) 

        self.logger.info(f"writing data to {data_filepath}")
        with open(data_filepath, 'w') as f:
            try:
                f.write(csv)
                self._nav_data = nav_data
                return data_filepath
            except Exception as ex:
                self.logger.error(ex)
                return None

    def _take_snapshot(self, path: str) -> Optional[str]:
        if not self.image:
            return None
        
        filename = f'{time.time()}.jpg'
        filepath = os.path.join(path,filename)

        self.logger.info(f"writing image to {path}")
        with open(filepath, 'wb') as f:
            try:
                f.write(self.image.value)
                return filepath
            except Exception as ex:
                self.logger.error(ex)
                return None






        
