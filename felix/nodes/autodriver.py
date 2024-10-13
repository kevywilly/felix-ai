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
from lib.log import logger
from felix.signals import sig_raw_image, sig_stop, sig_autodrive, sig_cmd_vel, sig_tof
from enum import Enum

torch.hub.set_dir(settings.TRAINING.model_root)

use_resnet50 = settings.USE_RESNET50

TOF_LEFT = -1
TOF_RIGHT = 1
TOF_FORWARD = 0

class Direction(str,Enum):
    NA="NA"
    FORWARD="FORWARD"
    LEFT="LEFT"
    RIGHT="RIGHT"
    STRAFE_LEFT="STRAFLEFT"
    STRAFE_RIGHT="STRAFERIGHT"


class AutoDriver(BaseNode):

    logger = logger

    def __init__(self, model_file=settings.TRAINING.training_model_path, **kwargs):
        super(AutoDriver, self).__init__(**kwargs)
        self.device = torch.device('cuda' if torch.backends.cuda.is_built() else 'cpu')
        self.model_file = model_file
        self.model_loaded = False
        self.is_active = False
        self.raw_image = None
        self.tof = {}
        
        sig_raw_image.connect(self._on_raw_image)
        sig_autodrive.connect(self._on_autodrive)
        sig_stop.connect(self._on_stop)
        sig_tof.connect(self._on_tof)

    def _on_tof(self, sender, payload: Measurement):
        self.tof[payload.id] = payload.value

    def _on_raw_image(self, sender, payload):
        self.raw_image = payload

    def _on_autodrive(self, sender, **kwargs):
        logger.info("AutoDrive signal received")
        self.is_active = not self.is_active
        if not self.is_active:
            sig_cmd_vel.send("autodrive", payload=Twist())
        logger.info(f"AutoDrive is_active: {self.is_active}")

    def _on_stop(self, sender, **kwargs):
        logger.info("Stop signal received")
        self.is_active = False
        logger.info(f"AutoDrive is_active: {self.is_active}")

    @property
    def model_file_exists(self) -> bool:
        return os.path.isfile(self.model_file)
    
    @property
    def tof_prediction(self):
        left = self.tof.get(0)
        right = self.tof.get(1)
        if left > 200 and right > 200:
            return TOF_FORWARD
        elif left < right:
            return TOF_RIGHT
        else:
            return TOF_LEFT
    
    @property
    def blocked_right(self):
        return self.tof.get(1) < settings.TOF_THRESHOLD
    
    def spinner(self):
        if self.is_active and self.raw_image is not None:
            try:
                cmd = self.predict(self.raw_image)
                logger.info(f"AutoDrive: {cmd}")
                sig_cmd_vel.send("autodrive", payload=cmd)
            except:  # noqa: E722
                sig_cmd_vel.send("autodrive", payload=Twist())
                sig_stop.send("autodrive")
            
    
    def load_state_dict(self, model):
        try:
            if self.model_file_exists:
                model.load_state_dict(torch.load(self.model_file))
                self.model_loaded = True
            else:
                raise Exception("model file does not exist")
        except Exception as ex:
            self.logger.warn('======== WARNING: COULD NOT LOAD MODEL FILE. AUTODRIVE IS NOT SAFE. ============')
            self.logger.warn(ex.__str__())
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

        print("-------------------------------------------------------------------")
        print(f"\t-- model file: {self.model_file}")
        print(f"\t-- model exists: {self.model_file_exists}")
        print(f"\t-- model loaded: {self.model_loaded}")
        print(f"\t-- targets: {self.num_targets}")
        print(f"\t-- linear: {self.linear}")
        print(f"\t-- angular: {self.angular}")
        print("--------------------------------------------------------------------")

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
        print("softmax", y)
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
            print("No predictions")
            return cmd
        
        forward = float(predictions[self.FORWARD])
        blocked = float(predictions[self.BLOCKED])
        print(predictions)

        if forward > 0.5:
            cmd.linear.x = self.linear
            cmd.angular.z = 0.0
            self.status = self.FORWARD
        elif blocked >= 0.5:
            cmd.linear.x = 0.0
            cmd.angular.z = self.angular
            self.status = self.BLOCKED
        
        print(f"predict: 0:{blocked:.4f}, 1:{forward:.4f} ({self.status})")
        return cmd

class TernaryObstacleAvoider(ObstacleAvoider):


    FORWARD = 0
    LEFT = 1
    RIGHT = 2

    def __init__(self):
        super().__init__(
            model_file=settings.TRAINING.training_model_path,
            num_targets=3,
        )
        
    def predict(self, input) -> Twist:
        cmd = Twist()

        predictions = self.get_predictions(input)

        if predictions is None:
            print("autodriver failed to get predictions, stopping.")
            return cmd
        
        forward = float(predictions[self.FORWARD])
        left = float(predictions[self.LEFT])
        right = float(predictions[self.RIGHT])
        tof = self.tof_prediction

        print("---------------------------------------------")
        print(f"l: {left}, f: {forward}, r:{right}, tof: {self.tof_prediction}")
        print("---------------------------------------------")

        if forward > 0.5:
            self.current_turn = None  # Reset turning state whenever forward is recommended
            cmd.linear.x = self.linear  # Set forward motion for all forward cases
            cmd.angular.z = 0.0  # No rotation for forward or diagonal movement
            
            if tof == TOF_FORWARD:
                cmd.linear.y = 0.0
            elif tof == TOF_RIGHT:
                cmd.linear.y = -self.linear*3/4# Move diagonally forward-right
                cmd.linear.x = self.linear/2
            elif tof == TOF_LEFT:
                cmd.linear.y = self.linear*3/4  # Move diagonally forward-left
                cmd.linear.x = self.linear/2
        else:
            cmd.linear.x = 0.0
            cmd.linear.y = 0.0  # Ensure no lateral movement during turns
            if self.current_turn is None:
                self.current_turn = "left" if left > right else "right"
            
            cmd.angular.z = self.angular if self.current_turn == "left" else -self.angular

        print("autodrive:", cmd)
        return cmd
            
        

