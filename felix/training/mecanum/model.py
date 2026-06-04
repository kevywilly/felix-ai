import os
import torch
import torch.nn as nn
from torchvision import models
from felix.settings import settings

if not os.path.exists(settings.TRAINING.model_root):
    os.makedirs(settings.TRAINING.model_root)

torch.hub.set_dir(settings.TRAINING.model_root)

class MecanumSensorFusionNet(nn.Module):
    def __init__(self, dropout=0.3):
        super().__init__()
        
        # ResNet50 backbone
        self.vision = models.resnet50(pretrained=True)
        vision_features = self.vision.fc.in_features  # 2048
        self.vision.fc = nn.Identity()
        
        # ToF sensor branch
        self.sensor_fc = nn.Sequential(
            nn.Linear(2, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(dropout * 0.5),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64)
        )
        
        # Fusion layers
        self.fusion = nn.Sequential(
            nn.Linear(vision_features + 64, 512),
            nn.ReLU(),
            nn.BatchNorm1d(512),
            nn.Dropout(dropout),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, 3)
        )
        
    def forward(self, image, tof):
        vis_feat = self.vision(image)
        sensor_feat = self.sensor_fc(tof)
        combined = torch.cat([vis_feat, sensor_feat], dim=1)
        output = self.fusion(combined)
        return torch.tanh(output)