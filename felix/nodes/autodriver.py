from abc import abstractmethod

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



torch.hub.set_dir(settings.TRAINING.model_root)

use_resnet50 = settings.USE_RESNET50

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
        if not self.is_active:
            Topics.cmd_vel.send("autodrive", payload=Twist())
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
        left = self.tof.get(0, 0)
        right = self.tof.get(1, 0)
        if left > 200 and right > 200:
            return Direction.FORWARD
        elif left < right:
            return Direction.RIGHT
        else:
            return Direction.LEFT
    
    
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
                 num_targets = settings.TRAINING.num_categories, 
                 linear = settings.autodrive_linear, 
                 angular = settings.autodrive_angular):
        super().__init__(model_file)
        self.linear = linear
        self.angular = angular
        self.num_targets = num_targets
  
        if self.model_file_exists:
            if use_resnet50:
                self.model =  torchvision.models.resnet50(weights=None)
                num_ftrs = self.model.fc.in_features
                self.model.fc = torch.nn.Linear(num_ftrs, self.num_targets)
            else:
                self.model = torchvision.models.alexnet(weights=None)
                self.model.classifier[6] = torch.nn.Linear(self.model.classifier[6].in_features, self.num_targets)
            self.load_state_dict(self.model)
            self.model = self.model.to(self.device)

        self._print_status()

    def _print_status(self):

        self.logger.info(
            f""" 
            model file: {self.model_file}
            model exists: {self.model_file_exists}
            model loaded: {self.model_loaded}
            targets: {self.num_targets}
            linear: {self.linear}
            angular: {self.angular}
            """
        )

    def preprocess(self, sensor_image):
        x = ImageUtils.bgr8_to_rgb8(sensor_image)
        x = cv2.resize(x, (224,224), cv2.INTER_LINEAR)
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

    def __init__(self, *args, **kwargs):
        super().__init__(
            model_file=settings.TRAINING.training_model_path,
            num_targets=2 
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

    def __init__(self):
        super().__init__(
            model_file=settings.TRAINING.training_model_path,
            num_targets=3,
        )
        self.direction = Direction.FORWARD
        
    def predict(self, input) -> Twist:
        cmd = Twist()

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
        

