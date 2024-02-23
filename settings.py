import numpy as np
from typing import List, Dict
import os
from src.motion.vehicle import MecanumVehicle
from src.utils.format import comment_block

from src.vision.sensors import CameraSensor

import yaml

## define custom tag handler
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

## register the tag handler
yaml.add_constructor('!join', join)
yaml.SafeLoader.add_constructor(tag='!join', constructor=join) 

ROBOT = os.getenv('ROBOT')
print(comment_block(f'Robot = {ROBOT}'))

if not(ROBOT):
    raise Exception("Environment variable ROBOT not set, use either ROBOT=felixV1 or ROBOT=felixV2")
    exit()

class TrainingConfig:
    def __init__(self, config):
        self.data_root = config.get('training').get('data_root')
        self.training_path = config.get('training').get('training_path')
        self.tags_path = config.get('training').get('tags_path')
        self.navigation_path = config.get('training').get('navigation_path')
        self.model_root = config.get('training').get('model_root')
        self.driving_data_path = config.get('training').get('driving_data_path')

    def training_folder(self,folder):
        return os.path.join(self.training_path,folder.lower())

class AppSettings:


    def __init__(self, config_file):

        print(comment_block('Loading App Settings'))
    
        config = self.load_config(config_file)

        self.JOY_DAMPENING_MODE = config.get('peripherals').get('joy_dampening_mode')
        
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
        
        self.DEFAULT_SENSOR_MODE = CameraSensor.mode(config.get('camera_sensor_mode',3))
        
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
        
        DEBUG: bool = config.get('debug')

    
    def load_config(self, config_file) -> Dict:
        with open(config_file,'r') as f:
            return yaml.safe_load(f)

settings = AppSettings(f'config/{ROBOT}.yml')

