import os

import torch

from felix.settings import settings
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("trainer")

if not os.path.exists(settings.TRAINING.model_root):
    os.makedirs(settings.TRAINING.model_root)

torch.hub.set_dir(settings.TRAINING.model_root)

use_resnet50 = settings.USE_RESNET50

    
class Trainer(ABC):

    def __init__(self, test_pct=50, epochs=50, lr=0.001, momentum=0.9):
        self.test_pct = test_pct
        self.lr = lr
        self.test_pct = test_pct
        self.epochs = epochs
        self.momentum = momentum

        logger.info(
            f"""
            Loaded Trainer:
            \tepochs: {self.epochs}
            \tlr: {self.lr}
            \tmomentum: {self.momentum}
            \ttest-pct: {self.test_pct}
            """
        )


    @abstractmethod
    def train(self):
        pass