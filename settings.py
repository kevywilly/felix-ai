import numpy as np
from typing import List, Dict
import os

from src.utils.sensors import CameraSensorMode

class TrainingType:
    OBSTACLE="OBSTACLE"
    PATH="PATH"

class TrainingProfile:

    def __init__(
        self, 
        data_root: str, 
        name: str, 
        type: str,
        classifier: str, 
        categories: List[str], 
        velocity_map: Dict,
        epochs: int = 30, 
        learning_rate: float = 0.001, 
        momentum: float = 0.9
        ):
        self.type = type
        self.name = name
        self.filename = name.lower().replace(" ","_")
        self.classifier = classifier
        self.categories = categories
        self.velocity_map = velocity_map
        self.data_root = data_root
        self.planning_path = os.path.join(data_root,"planning")
        self.snapshot_path = os.path.join(data_root,"snapshots")
        self.model_root = os.path.join(data_root,"models")
        self.best_model_folder = os.path.join(self.model_root,"best")
        self.best_model_file = os.path.join(self.best_model_folder,self.filename+".pth")
        self.training_data_path = os.path.join(self.data_root, self.filename)
        self.num_categories = len(self.categories)
        self.onnx_folder = os.path.join(self.model_root,"onnx")
        self.onnx_file = os.path.join(self.onnx_folder,self.filename+".onnx")
        self.trt_folder = os.path.join(self.model_root, "trt")
        self.trt_file = os.path.join(self.trt_folder,f"{self.filename}.trt")

obstacle3d_profile= TrainingProfile(
    data_root="/felix/data",
    name="obstacle3d",
    type=TrainingType.OBSTACLE,
    classifier="alexnet",
    categories=["forward","left","right"],
    velocity_map={"forward": (0.5,0,0), "left": (0,0,0.3), "right": (0,0,-0.3)}
)

obstacle_profile= TrainingProfile(
    data_root="/felix/data",
    name="obstacle",
    type=TrainingType.OBSTACLE,
    classifier="alexnet",
    categories=["blocked","free"],
    velocity_map={"blocked": (0,0,0.3), "free": (0.5,0,0), }
)  

path_profile= TrainingProfile(
    data_root="/felix/data",
    name="path_planning",
    type=TrainingType.PATH,
    classifier="alexnet",
    categories=[],
    velocity_map={}
)   


class AppSettings:

    class Data:
        root: str = '/home/nano/projects/felix-ai/data'
        driving_data_path = os.path.join(root,'driving_data')

    class Topics:
        raw_video: str = "/left/image_raw"
        cmd_vel: str = "/cmd_vel"
        autodrive: str = "/autodrive"
        
    class Robot:
        wheel_radius: float = 65.00/2000.0
        wheel_base: float = 140.0/1000.0
        track_width: float = 130.00/1000
        wheel_x_offset: float = 71.5/1000
        body_length: float = 152/1000
        body_width: float = 126.00/1000
        encoder_resolution: int = 48*2 # gear ratio * 2 #int(1000/48)
        max_linear_velocity: float = 0.20
        max_angular_velocity: float = 0.85
    
    class Camera:
        width: int = 1640
        height: int = 1232
        fps: float = 30
        capture_width: int = 1640
        capture_height:int = 1232
        stereo: bool = False
        fov: int=160
    

    Training: TrainingProfile = obstacle3d_profile

    DEFAULT_SENSOR_MODE = CameraSensorMode(3,1640,1232,29)

    SENSOR_MODES = [
        CameraSensorMode(0,3264,2464,21),
        CameraSensorMode(1,3264,1848,28),
        CameraSensorMode(2,1928,1080,29),
        CameraSensorMode(3,1640,1232,29),
        CameraSensorMode(4,1280,720,59),
        CameraSensorMode(5,1280,720,120),
    ]

    CAMERA_MATRIX = np.array([
        [848.721379, 0.000000, 939.509142],
        [0.000000, 848.967602, 596.153547], 
        [0.000000, 0.000000, 1.000000]
    ])

    DISTORTION_COEFFICIENTS = np.array(
        [
            [-0.296850, 0.061372, 0.002562, -0.002645, 0.000000]
        ]
    )
    debug: bool = False

settings = AppSettings

