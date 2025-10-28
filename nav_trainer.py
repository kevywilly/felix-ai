import os
import glob
from pathlib import Path
from felix.settings import settings
from typing import Dict, List, Tuple, Any, Optional, Callable, Union

import numpy as np
from lib.interfaces import Twist
from lib.vehicles.vehicle import VehicleTrajectory
from torchvision import transforms
from torchvision.datasets import ImageFolder
from torchvision.datasets.folder import default_loader
import torch


#nav_root = "~"
#nav_path = os.path.join("/home/orin", settings.TRAINING.navigation_path.lstrip("/"))
nav_path = settings.TRAINING.navigation_path
print(nav_path)

class Dir:
    Forward = 0
    Left = 1
    LeftHard = 2
    Right = 3
    RightHard = 4

class ModelInput:
    def __init__(self, image: str, x: float, y: float, z: float, ts: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.ts: float = ts
        self.image: str = image
        self.angular_to_linear_ratio = settings.VEHICLE.max_linear_velocity / settings.VEHICLE.max_angular_velocity
    
    @classmethod
    def from_file(cls, filepath: str) -> "ModelInput":
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        parts = name.split("_")

        x = float(parts[1])/100.0
        y = float(parts[2])/100.0
        z = float(parts[3])/100.0
        ts = float(parts[4])/1000.0
        return cls(image=filepath, x=x, y=y, z=z, ts=ts)
    
    @property
    def trajectory(self) -> VehicleTrajectory:
        return settings.VEHICLE.get_relative_motion(self.x, self.y, self.z)
    
    @property
    def abs_degrees_per_sec(self) -> float:
        return abs(self.trajectory.degrees_per_sec) 
    
    @property
    def label(self) -> int:
        return self.trajectory.direction.value
        

    def __repr__(self):
        return f"ModelInput(x={self.x}, y={self.y}, z={self.z}, ts={self.ts}, label={self.label}, image='{self.image}', trajectory={self.trajectory})"

def _get_nav_files(path):
    for root, dirs, filenames in os.walk(path):
        for filename in filenames:
            if filename.lower().endswith('.jpg'):
                full_path = os.path.join(root, filename)
                yield full_path

class NavImageFolder(ImageFolder):
    @staticmethod  
    def make_dataset(
        directory: Union[str, Path],
        class_to_idx: Dict[str, int],
        extensions: Optional[Tuple[str, ...]] = None,
        is_valid_file: Optional[Callable[[str], bool]] = None,
        allow_empty: bool = False,
    ) -> List[Tuple[str, int]]:
        result: list[Tuple[str, int]] = []
        for full_path in _get_nav_files(directory):
            sample = ModelInput.from_file(full_path)
            if sample.label >= 0 and sample.label <=2:
                if sample.abs_degrees_per_sec >=2.1 and sample.abs_degrees_per_sec <=5.0:
                    label = Dir.Left if sample.trajectory.degrees_per_sec > 0 else Dir.Right
                elif sample.abs_degrees_per_sec >5.0:
                    label = Dir.LeftHard if sample.trajectory.degrees_per_sec > 0 else Dir.RightHard
                else:
                    label = Dir.Forward
                result.append((full_path, label))
        for r in result:
            print(r)
        return result
 


if __name__ == "__main__":
    max_degrees_per_sec = 0.0
    for file in _get_nav_files(nav_path):
        sample = ModelInput.from_file(file)
        max_degrees_per_sec = sample.trajectory.degrees_per_sec if sample.trajectory.degrees_per_sec > max_degrees_per_sec else max_degrees_per_sec  
        if sample.label >=0:
            print(sample.trajectory.degrees_per_sec, sample.label)

