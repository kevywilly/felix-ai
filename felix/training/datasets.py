from typing import Tuple, Any, Optional, Callable

import numpy as np
from torchvision import transforms
from torchvision.datasets import ImageFolder
from torchvision.datasets.folder import default_loader
import torch

class CustomImageFolder(ImageFolder):
    def __init__(self, root, transform=None, target_transform=None, loader=default_loader, random_flip=False, target_flips = None):
        super(CustomImageFolder, self).__init__(root, transform=transform, target_transform=target_transform, loader=loader)
        self.random_flip = random_flip
        if self.random_flip:
            self.flip_transform = transforms.RandomHorizontalFlip(1.0)  # Always flip the image
            self.target_flips = target_flips
    
    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        """
        Args:
            index (int): Index

        Returns:
            tuple: (sample, target) where target is class_index of the target class.
        """
        path, target = self.samples[index]
        sample = self.loader(path)
        if self.random_flip:
            if torch.rand(1).item() > 0.5:
                sample = self.flip_transform(sample)
                target = self.target_flips[target]  if self.target_flips is not None else target
        if self.transform is not None:
            sample = self.transform(sample)
        if self.target_transform is not None:
            target = self.target_transform(target)

        return sample, target
    
