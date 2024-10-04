import os
import numpy as np
from pathlib import Path
from typing import List, Dict
from lib.vehicles import MecanumVehicle, DifferentialDriveVehicle
from felix.utils.format import comment_block
from felix.vision.sensors import CameraSensor

import yaml

## define custom tag handler
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

## register the tag handler
yaml.add_constructor('!join', join)
yaml.SafeLoader.add_constructor(tag='!join', constructor=join) 

_ROBOT = os.getenv('ROBOT') if os.getenv('ROBOT') else 'felixV2'
print(comment_block(f'Robot = {_ROBOT}'))

if not(_ROBOT):
    raise Exception("Environment variable ROBOT not set, use either ROBOT=felixV1 or ROBOT=felixV2")
    exit()

class TrainingConfig:
    def __init__(self, config):
        self.mode = config.get('training').get('mode')
        self.data_root = config.get('training').get('data_root')
        self.training_path = config.get('training').get('training_path')
        self.tags_path = config.get('training').get('tags_path')
        self.navigation_path = config.get('training').get('navigation_path')
        self.model_root = config.get('training').get('model_root')
        self.driving_data_path = config.get('training').get('driving_data_path')
        self.num_categories =3 if self.mode == 'ternary' else 2

    @property
    def training_model_path(self):
        return os.path.join(self.model_root, f'checkpoints/{self.mode}_obstacle_avoidance.pth')
    
    @property
    def training_images_path(self):
        return os.path.join(self.data_root, f"training/{self.mode}")

    def training_folder(self,folder):
        return os.path.join(self.training_path,folder.lower())

class AppSettings:


    def __init__(self, config_file):

        print(comment_block('Loading App Settings'))
    
        config = self.load_config(config_file)

        peripherals = config.get('peripherals',{})
        joystick = peripherals.get('joystick',{})
        dampening = joystick.get('dampening',{})
        
        self.MOCK_MODE = config.get("mock_mode", False)
        self.JOY_DAMPENING_MODE: int = dampening.get('mode',1)
        self.JOY_DAMPENING_CURVE_FACTOR: float = dampening.get('curve_factor',0.5)
        
        self.TRAINING = TrainingConfig(config)

        self.VEHICLE = MecanumVehicle(
            min_rpm = config.get('vehicle').get('min_rpm',0),
            max_rpm = config.get('vehicle').get('max_rpm',205),
            wheel_radius = config.get('vehicle').get('wheel_radius'),
            wheel_base = config.get('vehicle').get('wheel_base',0),
            track_width = config.get('vehicle').get('track_width',0),
            gear_ratio = config.get('vehicle').get('gear_ratio',0),
            motor_voltage = config.get('vehicle').get('motor_voltage',0),
            yaboom_port=config.get('peripherals').get('yaboom')
        )   
        
        camera = config.get('camera',{})
        self.DEFAULT_SENSOR_MODE = CameraSensor.mode(camera.get('sensor_mode',3))
        self.CAMERA_FOV = camera.get('fov',160)
        
        self.DISTORTION_COEFFICIENTS = np.array(
            config.get('camera_calibration')
            .get('distortion_coefficients')
            .get('data')
        ).reshape(1,5)
        
        self.CAMERA_MATRIX = np.array(
            config.get('camera_calibration')
            .get('camera_matrix')
            .get('data')
        ).reshape(3,3)

        self.autodrive_linear = config.get('autodrive').get('linear')
        self.autodrive_angular = config.get('autodrive').get('angular')
        self.capture_when_driving = config.get('capture_when_driving', False)
        
        self.DEBUG: bool = config.get('debug')

        self.ROBOT: str = _ROBOT

        self.USE_RESNET50 = True

    
    def load_config(self, config_file) -> Dict:
        with open(config_file,'r') as f:
            return yaml.safe_load(f)


path = Path(__file__).parent.absolute()
settings = AppSettings(os.path.join(path,"..","config",f'{_ROBOT}.yml'))

