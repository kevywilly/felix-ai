import os
import numpy as np
from pathlib import Path
from typing import Dict
from lib.vehicles import MecanumVehicle
from felix.vision.sensors import CameraSensor
import logging
import yaml
from enum import Enum

logger = logging.getLogger(__name__)

## define custom tag handler
def join(loader, node):
    seq = loader.construct_sequence(node)
    return ''.join([str(i) for i in seq])

## register the tag handler
yaml.add_constructor('!join', join)
yaml.SafeLoader.add_constructor(tag='!join', constructor=join) 

FELIX_CONFIG_FILE = "config.yml"

logger.info(f'🤖 Robot Config = {FELIX_CONFIG_FILE}')

class ModelType(str,Enum):
    mobilenet_large = 'mobilenet_v3_large'
    mobilenet_small = 'mobilenet_v3_small'
    resnet_50 = 'resnet50'
    alexnet = 'alexnet'

class TrainingCategories(int,Enum):
    binary = 2
    ternary = 3
    mecanum = 5

class TrainingConfig:
    def __init__(self, config):
        self.mode = config.get('training').get('mode')
        self.data_root = config.get('training').get('data_root')
        self.training_path = config.get('training').get('training_path')
        self.tags_path = config.get('training').get('tags_path')
        self.navigation_path = config.get('training').get('navigation_path')
        self.model_root = config.get('training').get('model_root')
        self.driving_data_path = config.get('training').get('driving_data_path')
        self.num_categories = TrainingCategories[self.mode].value

    @property
    def training_model_path(self):
        return os.path.join(self.model_root, f'checkpoints/{self.mode}_obstacle_avoidance.pth')
    
    @property
    def mecanum_model_path(self):
        return os.path.join(self.model_root, f'checkpoints/mecanum_resnet50.pth')
    
    @property
    def training_images_path(self):
        return os.path.join(self.data_root, f"training/{self.mode}")

    def training_folder(self,folder):
        return os.path.join(self.training_path,folder.lower())

class AppSettings:


    def __init__(self, config_file):
    
        config = self.load_config(config_file)

        peripherals = config.get('peripherals',{})
        joystick = peripherals.get('joystick',{})
        dampening = joystick.get('dampening',{})
        tof = config.get('tof', {})
        
        self.TOF_THRESHOLD = tof.get('threshold', 250)
        self.USE_TOF_IN_AUTODRIVE = tof.get('use_in_autodrive', False)
        self.MOCK_MODE = config.get('mock_mode', False)
        self.JOY_DAMPENING_MODE: int = dampening.get('mode',1)
        self.JOY_DAMPENING_CURVE_FACTOR: float = dampening.get('curve_factor',0.5)
        
        self.TRAINING = TrainingConfig(config)

        self.VEHICLE = MecanumVehicle(
            min_rpm = config.get('vehicle',{}).get('min_rpm',0),
            max_rpm = config.get('vehicle',{}).get('max_rpm',205),
            wheel_radius = config.get('vehicle',{}).get('wheel_radius'),
            wheel_base = config.get('vehicle',{}).get('wheel_base',0),
            track_width = config.get('vehicle',{}).get('track_width',0),
            gear_ratio = config.get('vehicle',{}).get('gear_ratio',0),
            motor_voltage = config.get('vehicle',{}).get('motor_voltage',0),
            yaboom_port=config.get('peripherals',{}).get('yaboom')
        )   
        
        camera = config.get('camera',{})
        self.DEFAULT_SENSOR_MODE = CameraSensor.mode(camera.get('sensor_mode',3))
        self.CAMERA_FOV = camera.get('fov',160)
        
        self.DISTORTION_COEFFICIENTS = np.array(
            config.get('camera_calibration',{})
            .get('distortion_coefficients')
            .get('data')
        ).reshape(1,5)
        
        self.CAMERA_MATRIX = np.array(
            config.get('camera_calibration',{})
            .get('camera_matrix')
            .get('data')
        ).reshape(3,3)

        autodrive = config.get('autodrive', {})
        self.autodrive_linear = autodrive.get('linear', 0.2)
        self.autodrive_angular = autodrive.get('angular', 0.5)
        # Output slew limits (units/sec) for AutoDrive's command stream, applied
        # via the shared lib.motion.TwistSmoother. Generous defaults keep the
        # response near-instant (~1-2 ticks at 20 Hz); lower them for a gentler,
        # less jerky ride. Stops (zero twist) always snap immediately.
        self.AUTODRIVE_SLEW_LINEAR = autodrive.get('slew_linear', 3.0)
        self.AUTODRIVE_SLEW_ANGULAR = autodrive.get('slew_angular', 12.0)
        self.nav_capture_frequency_seconds = config.get('nav_capture_frequency_seconds', 2)

        # Object-seek follow tuning. linear/angular fall back to the autodrive
        # gains so the seeker behaves as before when no `seek:` block is present.
        seek = config.get('seek', {})
        self.SEEK_LINEAR = seek.get('linear', self.autodrive_linear)
        self.SEEK_ANGULAR = seek.get('angular', self.autodrive_angular)
        self.SEEK_STRAFE = seek.get('strafe', 0.4)
        self.SEEK_DEADBAND = seek.get('deadband', 0.06)
        self.SEEK_EMA_ALPHA = seek.get('ema_alpha', 0.5)
        self.SEEK_YAW_CROSSOVER = seek.get('yaw_crossover', 0.35)
        self.SEEK_SLEW_LINEAR = seek.get('slew_linear', 1.5)
        self.SEEK_SLEW_ANGULAR = seek.get('slew_angular', 5.0)
        self.SEEK_MIN_CONFIDENCE = seek.get('min_confidence', 0.0)
        self.SEEK_LOCK_DIST = seek.get('lock_max_center_dist', 0.2)
        self.SEEK_COAST_FRAMES = seek.get('coast_frames', 3)
        self.SEEK_LOST_TIMEOUT = seek.get('lost_timeout', 0.5)
        self.SEEK_TOF_STOP_MM = self.TOF_THRESHOLD
        self.SEEK_TOF_SLOW_MM = self.TOF_THRESHOLD + seek.get('tof_slow_margin_mm', 300)
        self.SEEK_LIDAR_STOP_MM = seek.get('lidar_stop_mm', 300)
        self.SEEK_LIDAR_SLOW_MM = seek.get('lidar_slow_mm', 700)
        self.SEEK_LIDAR_STALE_SEC = seek.get('lidar_stale_sec', 0.5)
        
        self.DEBUG: bool = config.get('debug', False)

        self.USE_RESNET50 = True

        model_settings = config.get('model',{})
        self.model_num_targets = self.TRAINING.num_categories
        self.model_nav_num_targets = 3
        self.model_images = self.TRAINING.training_images_path
        self.model_type = ModelType(model_settings.get('type', ModelType.resnet_50))
        self.model_use_roi = model_settings.get('use_roi', True)
        self.model_roi_height_ratio = model_settings.get('roi_height_ratio', 0.6)
        self.model_roi_vertical_offset = model_settings.get('roi_vertical_offset', 0.4)
        self.model_roi_width_ratio = model_settings.get('roi_width_ratio', 1.0)
        if self.model_use_roi:
            file_path = Path(self.TRAINING.training_model_path)
            self.model_file = file_path.parent / f"roi_{file_path.name}"
        else:
            self.model_file = self.TRAINING.training_model_path

        logger.info("⚙️ Loaded App Settings")

    
    def load_config(self, config_file) -> Dict:
        try:
            with open(config_file,'r') as f:
                return yaml.safe_load(f)
        except Exception:
            with open(os.path.join("config.yml"),'r') as f:
                return yaml.safe_load(f)
    @property
    def training_labels(self):
        if self.TRAINING.mode == "binary":
            return ['clear','obstacle']
        elif self.TRAINING.mode == "ternary":
            return ['left','forward','right']
        elif self.TRAINING.mode == "mecanum":
            return ['sleft','left','forward','right','sright']
        else:
            raise ValueError(f"Unknown training mode: {self.TRAINING.mode}")


path = Path(__file__).parent.absolute()
print(path)
settings = AppSettings(f"/felix-ai/{FELIX_CONFIG_FILE}")

