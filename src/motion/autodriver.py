from abc import ABC, abstractmethod
from src.interfaces.msg import Twist
import torch
import torchvision
import cv2
import numpy as np
import torch.nn.functional as F
import time
from src.settings import settings
from src.vision.image import ImageUtils
import logging
import os
torch.hub.set_dir(settings.TRAINING.model_root)

class AutoDriver(ABC):

    logger = logging.getLogger('AUTODRIVE')

    def __init__(self, model_file):
        self.device = torch.device('cuda' if torch.has_cuda else 'cpu')
        self.model_file = model_file
        self.model_loaded = False
    
    def model_file_exists(self) -> bool:
        return os.path.isfile(self.model_file)
    
    def load_state_dict(self, model):
        try:
            if self.model_file_exists():
                model.load_state_dict(torch.load(self.model_file))
                self.model_loaded = True
            else:
                raise Exception("model file does not exist")
        except Exception as ex:
            self.logger.warn(f'======== WARNING: COULD NOT LOAD MODEL FILE. AUTODRIVE IS NOT SAFE. ============')
            self.logger.warn(ex.__str__())
            self.model_loaded = False

    @abstractmethod
    def predict(self, input) -> Twist:
        pass

class ObstacleAvoider(AutoDriver):
    mean = 255.0 * np.array([0.485, 0.456, 0.406])
    stdev = 255.0 * np.array([0.229, 0.224, 0.225])
    normalize = torchvision.transforms.Normalize(mean, stdev)

    def __init__(self, model_file, num_targets, linear = settings.autodrive_linear, angular = settings.autodrive_angular):
        super().__init__(model_file)
        self.linear = linear
        self.angular = angular
        self.num_targets = num_targets
  
        if self.model_file_exists:
            self.model = torchvision.models.alexnet(pretrained=False)
            self.model.classifier[6] = torch.nn.Linear(self.model.classifier[6].in_features, num_targets)
            self.load_state_dict(self.model)
            self.model = self.model.to(self.device)

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
        print(y)
        return y.flatten()

class BinaryObstacleAvoider(ObstacleAvoider):

    def __init__(self, *args, **kwargs):
        super().__init__(num_targets=2, *args, **kwargs)

    def predict(self, input) -> Twist:

        t = Twist()

        predictions = self.get_predictions(input)

        if predictions is None:
            return t
        
        prob_blocked = float(predictions[0])

        if prob_blocked < 0.5:
            t.linear.x = self.linear
            t.angular.z = 0.0
        else:
            t.angular.z = self.angular
            t.linear.x = 0.0

        return prob_blocked, t

class TernaryObstacleAvoider(ObstacleAvoider):

    NA = -1
    FORWARD = 0
    LEFT = 1
    RIGHT = 2

    def __init__(self, *args, **kwargs):
        super().__init__(num_targets=3, *args, **kwargs)

        self.status = self.NA
        

    def predict(self, input) -> Twist:

        cmd = Twist()

        predictions = self.get_predictions(input)

        if predictions is None:
            return cmd
        
        forward = float(predictions[self.FORWARD])
        left = float(predictions[self.LEFT])
        right = float(predictions[self.RIGHT])

        if forward > 0.5:
            cmd.linear.x = self.linear
            cmd.angular.z = 0.0
            self.status = self.FORWARD
        elif left > 0.5 and self.status != self.RIGHT:
            cmd.linear.x = 0.0
            cmd.angular.z = self.angular
            self.status = self.LEFT
        elif right > 0.5 and self.status != self.LEFT:
            cmd.linear.x = 0.0
            cmd.angular.z = -self.angular
            self.status = self.RIGHT

        return cmd
            
        

