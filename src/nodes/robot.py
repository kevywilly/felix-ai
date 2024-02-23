import os
from typing import Dict, Optional
import traitlets
from settings import settings
from src.motion.joystick import Joystick
from src.motion.kinematics import Kinematics
# from src.nodes.video_viewer import VideoViewer
from src.vision.image import Image, ImageUtils
from src.interfaces.msg import Odometry, Twist
from src.nodes.node import Node
from src.nodes.controller import Controller
from src.nodes.camera import Camera
import time
import numpy as np

from src.vision.image_collector import ImageCollector

class Robot(Node):

    image = traitlets.Instance(Image)
    capture_when_driving = traitlets.Bool(default_value=False)
    capture_when_driving_frequency = traitlets.Float(default_value=0.5)

    def __init__(self, **kwargs):
        super(Robot, self).__init__(**kwargs)
        
        # initialize objects
        self.image = Image()
        self._image_collector = ImageCollector()

        # initialize nodes
        self._camera: Camera = Camera()
        self._controller: Controller = Controller(frequency=30)
        

        # start nodes
        self._controller.spin()
        self._camera.spin()
        self.last_capture_time = time.time()
        # self._video_viewer: VideoViewer = VideoViewer()
        self._setup_subscriptions()

        self.loaded()

    def _setup_subscriptions(self):
        traitlets.dlink((self._camera, 'value'), (self.image, 'value'), transform=ImageUtils.bgr8_to_jpeg)
        traitlets.dlink((self._camera, 'value'), (self._controller, 'camera_image'))
        # traitlets.dlink((self._camera, 'value'), (self._video_viewer, 'camera_image'))

    def shutdown(self):
        self._camera.unobserve_all()
        self._controller.unobserve_all()

    def save_tag(self, tag):
        return self._image_collector.save_tag(self.get_image(), tag)
    
    def get_tags(self):
        return self._image_collector.get_tags()
    
    def create_snapshot(self, folder, label):
        return self._image_collector.create_snapshot(self.get_image(), folder, label)
    
    def get_snapshots(self, folder):
        return self._image_collector.get_snapshots(folder)

    def _motion_changed(self, changed):
        self.logger.info("motion")
        if changed.new != changed.old:
            self.logger.info(changed.new)
        
    def get_autodrive(self):
        return self._controller.autodrive
    
    def handle_twist(self, data: Dict) -> Twist:
        t = Twist()
        t.linear.x = float(data["linear"]["x"])
        t.linear.y = float(data["linear"]["y"])
        t.angular.z = float(data["angular"]["z"])
        self.set_cmd_vel(t)
        return t

    def handle_joystick(self, data: Dict) -> Twist:
            x = float(data.get('event',{}).get('x',0))
            y = float(data.get('event',{}).get('y',0))
            strafe = float(data.get('strafe', False))
            t = Joystick.get_twist(x,y, strafe)
            self.set_cmd_vel(t)
            return t
    
    def handle_navigate(self, data: Dict) -> str:

        x = int(data["cmd"]["x"])
        y = int(data["cmd"]["y"])
        w = int(data["cmd"]["w"])
        h = int(data["cmd"]["h"])

        driveMode = data["driveMode"]
        captureMode = data["captureMode"]

        odom = Kinematics.xywh_to_nav_target(x,y,w,h)

        if driveMode:
            self.set_nav_target(odom)

        if captureMode:
            captured_image = self._image_collector.save_navigation_image(x, y, w, h, self.get_image())
            return captured_image

        return ''

    def toggle_autodrive(self):
        self._controller.autodrive = not self._controller.autodrive
        return self.get_autodrive()
    
    def get_image(self):
        return self.image.value
    
    def set_nav_target(self, msg: Odometry):
        self._controller.nav_target=msg

    def set_cmd_vel(self, msg: Twist):
        self._controller.cmd_vel=msg

    def get_stream(self):
        while True:
            # ret, buffer = cv2.imencode('.jpg', frame)
            try:
                yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + self.get_image() + b'\r\n'
                )  # concat frame one by one and show result
            except Exception as ex:
                pass
    
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
            
        
        filepath = self._image_collector.save_image(
            self.get_image(), 
            path = settings.TRAINING.driving_data_path, 
            filename=ImageCollector.filetime('jpg')
        )

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





        
