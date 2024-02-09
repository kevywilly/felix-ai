import numpy as np
from typing import List, Dict
import os
from src.motion.vehicle import MecanumVehicle

from src.vision.sensors import CameraSensor

import yaml

## define custom tag handler
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

## register the tag handler
yaml.add_constructor('!join', join)
yaml.SafeLoader.add_constructor(tag='!join', constructor=join) 

 

POPPA = MecanumVehicle(
    wheel_radius=0.0485,
    wheel_base=0.15,
    track_width=0.229,
    max_rpm=350,
    gear_ratio=1/56,
    yaboom_port='/dev/myserial',
    motor_voltage=12
)

JUNIOR = MecanumVehicle(
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

SYS_USER = os.getenv('ROBOT_PLATFORM','POPPA').upper()

if SYS_USER == 'POPPA':
    curr_robot = POPPA
    dist_coefficients = DISTORTION_COEFFICIENTS_POPPA
    camera_matrix = CAMERA_MATRIX_POPPA
else:
    curr_robot = JUNIOR
    dist_coefficients = DISTORTION_COEFFICIENTS_NANO
    camera_matrix = CAMERA_MATRIX_NANO


class AppSettings:

    class Training:
        data_root = '/felix-ai/data'
        model_root = os.path.join(data_root,"models")
        navigation_path = os.path.join(data_root,"training/navigation")
        tags_path = os.path.join(data_root,"training/tags")
        driving_data_path = os.path.join(data_root, "driving_data")

    def __init__(self):
        config = self.load_config()

        self.Training.data_root = config.get('training').get('data_root')
        self.Training.tags_path = config.get('training').get('tags_path')
        self.Training.navigation_path = config.get('training').get('navigation_path')
        self.Training.model_root = config.get('training').get('model_root')
        self.Training.driving_data_path = config.get('training').get('driving_data_path')
        print(self.Training.model_root)

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

        debug: bool = config.get('debug')

    

    def load_config(self) -> Dict:
        with open('config/orin.yml','r') as f:
            return yaml.safe_load(f)

settings = AppSettings()

