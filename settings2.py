import os
import numpy as np
import math
from typing import List, Optional, Any, Dict
from felix.motion.robot import Robot
from felix.vision.sensor_mode import CameraSensorMode


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
        self.navigation_path = os.path.join(data_root,"training/navigation")
        self.tags_path = os.path.join(data_root,"training/tags")
        self.model_root = os.path.join(data_root,"models")
        self.best_model_folder = os.path.join(self.model_root,"best")
        self.best_model_file = os.path.join(self.best_model_folder,self.filename+".pth")
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


POPPA = Robot(
    wheel_radius=0.0485,
    wheel_base=0.15,
    track_width=0.229,
    max_rpm=205,
    gear_ratio=1/56,
    yaboom_port='/dev/myserial',
    motor_voltage=12
)

JUNIOR = Robot(
    wheel_radius=65.00/2000.0,
    wheel_base=140.0/1000.0,
    track_width=155.00/1000,
    max_rpm=90,
    gear_ratio=1/48,
    yaboom_port='/dev/myserial',
    motor_voltage=5
)

CAMERA_MATRIX_NANO = np.array([
        [848.721379, 0.000000, 939.509142],
        [0.000000, 848.967602, 596.153547], 
        [0.000000, 0.000000, 1.000000]
    ])

DISTORTION_COEFFICIENTS_NANO = np.array(
    [
        [-0.296850, 0.061372, 0.002562, -0.002645, 0.000000]
    ]
)

CAMERA_MATRIX_POPPA = np.array(
   [804.43002,   0.     , 840.24672,
           0.     , 803.05029, 635.00151,
           0.     ,   0.     ,   1.     ]
).reshape(3,3)

DISTORTION_COEFFICIENTS_POPPA = np.array(
    [
        [-0.296054, 0.064942, -0.001960, -0.001250, 0.000000]
    ]
)

SYS_USER = os.getenv('ROBOT_PLATFORM','JUNIOR').upper()

if SYS_USER == 'POPPA':
    curr_robot = POPPA
    dist_coefficients = DISTORTION_COEFFICIENTS_POPPA
    camera_matrix = CAMERA_MATRIX_POPPA
else:
    curr_robot = JUNIOR
    dist_coefficients = DISTORTION_COEFFICIENTS_NANO
    camera_matrix = CAMERA_MATRIX_NANO


class AppSettings:
    
    OBSTACLE_PATH=''
    
    class Topics:
        raw_video: str = "/camera/image_raw"
        cmd_vel: str = "/cmd_vel"
        autodrive: str = "/autodrive"
        cmd_nav: str = "/cmd_nav"
    
    class Camera:
        width: int = 1640
        height: int = 1232
        fps: float = 30
        capture_width: int = 1640
        capture_height:int = 1232
        stereo: bool = False
        fov: int=160

    NAV_LINEAR_VELOCITY: float = .16
    NAV_ANGULAR_VELOCITY: float = .32
    
    DEFAULT_SENSOR_MODE = CameraSensorMode(3,1640,1232,29)

    SENSOR_MODES = [
        CameraSensorMode(0,3264,2464,21),
        CameraSensorMode(1,3264,1848,28),
        CameraSensorMode(2,1928,1080,29),
        CameraSensorMode(3,1640,1232,29),
        CameraSensorMode(4,1280,720,59),
        CameraSensorMode(5,1280,720,120),
    ]

    Training: TrainingProfile = obstacle3d_profile

    DISTORTION_COEFFICIENTS = dist_coefficients
    CAMERA_MATRIX = camera_matrix

    debug: bool = False

    SYS_USER = os.getenv('USER','NANO')
    
    robot: Robot = curr_robot

settings = AppSettings

