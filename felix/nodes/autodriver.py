from abc import abstractmethod

from felix.vision.roi_utils import apply_roi_crop
from lib.interfaces import Measurement, Twist
from lib.nodes.base import BaseNode
import torch
import torchvision
import cv2
import numpy as np
import torch.nn.functional as F
from felix.settings import settings
from felix.vision.image import ImageUtils
import os
from felix.signals import Topics
from enum import Enum

# Import your ModelType enum
from felix.settings import ModelType

# Import the additional models
from torchvision.models import (
    resnet50, ResNet50_Weights,
    alexnet, AlexNet_Weights,
    mobilenet_v3_large, MobileNet_V3_Large_Weights,
    mobilenet_v3_small, MobileNet_V3_Small_Weights
)

torch.hub.set_dir(settings.TRAINING.model_root)

class Direction(str,Enum):
    NA="NA"
    FORWARD="FORWARD"
    LEFT="LEFT"
    RIGHT="RIGHT"
    STRAFE_LEFT="STRAFLEFT"
    STRAFE_RIGHT="STRAFERIGHT"


class AutoDriver(BaseNode):

    def __init__(self, model_file=settings.TRAINING.training_model_path, **kwargs):
        super(AutoDriver, self).__init__(**kwargs)
        self.device = torch.device('cuda' if torch.backends.cuda.is_built() else 'cpu')
        self.model_file = model_file
        self.model_loaded = False
        self.is_active = False
        self.raw_image = None
        self.use_tof = settings.USE_TOF_IN_AUTODRIVE or False
        self.tof = {}
        
        Topics.raw_image.connect(self._on_raw_image)
        Topics.autodrive.connect(self._on_autodrive)
        Topics.stop.connect(self._on_stop)
        Topics.tof.connect(self._on_tof)

        self.logger.info(f"AutoDriver using device: {self.device}")

    def _on_tof(self, sender, payload: Measurement):
        self.tof[payload.id] = payload.value
        self.logger.debug(f"tof: {payload.id} = {payload.value}")

    def _on_raw_image(self, sender, payload):
        self.raw_image = payload
        self.logger.debug("Raw image received")

    def _on_autodrive(self, sender, **kwargs):
        self.logger.info("AutoDrive signal received")
        self.is_active = not self.is_active
        self.logger.info(f"AutoDrive is_active: {self.is_active}")

    def _on_stop(self, sender, **kwargs):
        self.logger.info("Stop signal received, deactivating autodrive.")
        self.is_active = False
        self.logger.info(f"AutoDrive is_active: {self.is_active}")

    @property
    def model_file_exists(self) -> bool:
        return os.path.isfile(self.model_file)
    
    @property
    def tof_prediction(self):
        if not self.use_tof:
            return Direction.FORWARD
        left = self.tof.get(0, 0)
        right = self.tof.get(1, 0)
        if left > 200 and right > 200:
            return Direction.FORWARD
        elif left < right:
            return Direction.RIGHT
        else:
            return Direction.LEFT
    
    def _create_model(self, model_type: ModelType, num_targets: int):
        """
        Create and configure the model based on ModelType enum
        """
        if model_type == ModelType.resnet_50:
            model = resnet50(weights=None)
            num_ftrs = model.fc.in_features
            model.fc = torch.nn.Linear(num_ftrs, num_targets)
            
        elif model_type == ModelType.mobilenet_large:
            model = mobilenet_v3_large(weights=None)
            # MobileNetV3 classifier is a Sequential with Linear layer at index 3
            model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, num_targets)
            
        elif model_type == ModelType.mobilenet_small:
            model = mobilenet_v3_small(weights=None)
            # MobileNetV3 classifier is a Sequential with Linear layer at index 3
            model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, num_targets)
            
        elif model_type == ModelType.alexnet:
            model = alexnet(weights=None)
            model.classifier[6] = torch.nn.Linear(model.classifier[6].in_features, num_targets)
            
        else:
            # Unknown model type - fallback to default
            self.logger.warning(f"Unknown model_type '{model_type}', falling back to MobileNet V3 Large")
            model = mobilenet_v3_large(weights=None)
            model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, num_targets)
        
        self.logger.info(f"Created model: {model_type.value}")
        return model
    
    def spinner(self):
            
        if self.is_active and self.raw_image is not None:
            try:
                cmd = self.predict(self.raw_image)
                self.logger.info(f"AutoDrive: {cmd}")
                Topics.cmd_vel.send("autodrive", payload=cmd)
            except Exception as ex:  # noqa: E722
                self.logger.info(f"Autodrive error: {ex}. Stopping")
                Topics.cmd_vel.send("autodrive", payload=Twist())
                Topics.stop.send("autodrive")
                raise ex
            
    
    def load_state_dict(self, model):
        try:
            if self.model_file_exists:
                model.load_state_dict(torch.load(self.model_file))
                self.model_loaded = True
            else:
                raise Exception("model file does not exist")
        except Exception as ex:
            self.logger.warning('======== WARNING: COULD NOT LOAD MODEL FILE. AUTODRIVE IS NOT SAFE. ============')
            self.logger.warning(ex.__str__())
            self.model_loaded = False

    def shutdown(self):
        self.is_active = False

    @abstractmethod
    def predict(self, input) -> Twist:
        pass

class ObstacleAvoider(AutoDriver):
    mean = 255.0 * np.array([0.485, 0.456, 0.406])
    stdev = 255.0 * np.array([0.229, 0.224, 0.225])
    normalize = torchvision.transforms.Normalize(mean, stdev)

    def __init__(self, 
                 model_file = settings.TRAINING.training_model_path, 
                 model_type = settings.model_type,  # NEW: Accept model_type parameter
                 use_roi = settings.use_roi,     # NEW: Enable ROI preprocessing
                 roi_height_ratio = settings.roi_height_ratio,  # NEW: ROI parameters
                 roi_vertical_offset = settings.roi_vertical_offset,
                 num_targets = settings.TRAINING.num_categories, 
                 linear = settings.autodrive_linear, 
                 angular = settings.autodrive_angular):
        super().__init__(model_file)
        self.linear = linear
        self.angular = angular
        self.num_targets = num_targets
        
        # ROI Configuration
        self.use_roi = use_roi
        self.roi_height_ratio = roi_height_ratio
        self.roi_vertical_offset = roi_vertical_offset
        
        # Determine model type - priority: parameter > settings > fallback
        if model_type is not None:
            self.model_type = model_type
        elif hasattr(settings, 'MODEL_TYPE'):
            self.model_type = settings.model_type
        else:
            # Default to MobileNet V3 Large for indoor robots (good balance of speed/accuracy)
            self.model_type = ModelType.mobilenet_large
            
        self.logger.info(f"Using model type: {self.model_type}")
        self.logger.info(f"ROI enabled: {self.use_roi}")
  
        if self.model_file_exists:
            self.model = self._create_model(self.model_type, self.num_targets)
            self.load_state_dict(self.model)
            self.model = self.model.to(self.device)

        self._print_status()

    def _print_status(self):
        self.logger.info(
            f""" 
            model type: {self.model_type}
            model file: {self.model_file}
            model exists: {self.model_file_exists}
            model loaded: {self.model_loaded}
            targets: {self.num_targets}
            linear: {self.linear}
            angular: {self.angular}
            ROI enabled: {self.use_roi}
            ROI height ratio: {self.roi_height_ratio}
            ROI vertical offset: {self.roi_vertical_offset}
            """
        )

    def _apply_roi_crop(self, image):
        if not self.use_roi:
            return image
        
        return apply_roi_crop(
            image,
            roi_height_ratio=self.roi_height_ratio,
            roi_vertical_offset=self.roi_vertical_offset
            # roi_width_ratio defaults to 1.0 in the central method
        )

    def preprocess(self, sensor_image):
        # Convert from BGR to RGB
        x = ImageUtils.bgr8_to_rgb8(sensor_image)
        
        # Apply ROI cropping if enabled (CRITICAL for matching training!)
        x = self._apply_roi_crop(x)
        
        # Resize to 224x224 (now resizing the ROI-cropped image)
        x = cv2.resize(x, (224, 224), cv2.INTER_LINEAR)
        
        # Standard PyTorch preprocessing
        x = x.transpose((2, 0, 1))
        x = torch.from_numpy(x).float()
        x = self.normalize(x)
        x = x.to(self.device)
        x = x[None, ...]
        return x

    def get_predictions(self, input):
        if not self.model_loaded:
            return None
        
        x = self.preprocess(input)
        y = self.model(x)
        
        # we apply the `softmax` function to normalize the output vector so it sums to 1 (which makes it a probability distribution)
        y = F.softmax(y, dim=1)
        self.logger.debug("softmax", y)
        return y.flatten()

class BinaryObstacleAvoider(ObstacleAvoider):

    NA = -1
    BLOCKED = 0
    FORWARD = 1

    def __init__(self, **kwargs):
        super().__init__(
            num_targets=2,
            **kwargs
        )
        self.status = self.NA

    def predict(self, input) -> Twist:
        cmd = Twist()

        predictions = self.get_predictions(input)

        if predictions is None:
            self.logger.info("No predictions")
            return cmd
        
        forward = float(predictions[self.FORWARD])
        blocked = float(predictions[self.BLOCKED])

        if forward > 0.5:
            cmd.linear.x = self.linear
            cmd.angular.z = 0.0
            self.status = self.FORWARD
        elif blocked >= 0.5:
            cmd.linear.x = 0.0
            cmd.angular.z = self.angular
            self.status = self.BLOCKED
        
        self.logger.debug(f"predict: 0:{blocked:.4f}, 1:{forward:.4f} ({self.status})")
        return cmd

class TernaryObstacleAvoider(ObstacleAvoider):
    # indexes for predictions
    _forward = 0
    _left = 1
    _right = 2

    def __init__(self, **kwargs):
        super().__init__(
            num_targets=3,
            **kwargs
        )
        self.direction = Direction.FORWARD
        
    def predict(self, input) -> Twist:
        cmd = Twist()

        if not self.is_active:
            return cmd

        predictions = self.get_predictions(input)

        if predictions is None:
            self.logger.error("autodriver failed to get predictions, stopping.")
            return cmd
        
        forward = float(predictions[self._forward])
        left = float(predictions[self._left])
        right = float(predictions[self._right])
        
        tof = self.tof_prediction

        self.logger.info(f"l: {left}, f: {forward}, r:{right}, tof: {self.tof_prediction}")

        if forward > 0.5:
            self.direction = Direction.FORWARD
            cmd.angular.z = 0.0
            cmd.linear.y = 0.0
            if tof == Direction.FORWARD:
                cmd.linear.x = self.linear  # Set forward motion for all forward cases
            else:
                cmd.linear.x = self.linear*3/4
                cmd.linear.y = self.linear*(3/4 if tof == Direction.LEFT else -3/4)
        else:
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0
            if self.direction is Direction.FORWARD:
                self.direction = Direction.LEFT if left > right else Direction.RIGHT

            cmd.angular.z = self.angular if self.direction == Direction.LEFT else -self.angular
        
        self.logger.debug("autodrive:", cmd)
        return cmd

# Convenience factory functions for easy instantiation
def create_fast_binary_avoider(model_file=None, use_roi=True):
    """Create a fast binary obstacle avoider using MobileNet for indoor use"""
    return BinaryObstacleAvoider(
        model_type=ModelType.mobilenet_large,
        model_file=model_file or settings.TRAINING.training_model_path,
        use_roi=use_roi
    )

def create_accurate_binary_avoider(model_file=None, use_roi=True):
    """Create a high-accuracy binary obstacle avoider using ResNet-50"""
    return BinaryObstacleAvoider(
        model_type=ModelType.resnet_50,
        model_file=model_file or settings.TRAINING.training_model_path,
        use_roi=use_roi
    )

def create_fast_ternary_avoider(model_file=None, use_roi=True):
    """Create a fast ternary obstacle avoider using MobileNet for indoor use"""
    return TernaryObstacleAvoider(
        model_type=ModelType.mobilenet_large,
        model_file=model_file or settings.TRAINING.training_model_path,
        use_roi=use_roi
    )

def create_accurate_ternary_avoider(model_file=None, use_roi=True):
    """Create a high-accuracy ternary obstacle avoider using ResNet-50"""
    return TernaryObstacleAvoider(
        model_type=ModelType.resnet_50,
        model_file=model_file or settings.TRAINING.training_model_path,
        use_roi=use_roi
    )