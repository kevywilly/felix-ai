import random
import torchvision.transforms.functional as F
import torch

class RandomLowLightTransform:
    def __init__(self, min_factor=0.1, max_factor=0.5, p=0.7):
        self.min_factor = min_factor
        self.max_factor = max_factor
        self.p = p

    def __call__(self, img):
        if random.random() < self.p:
            brightness_factor = random.uniform(self.min_factor, self.max_factor)
            img = F.adjust_brightness(img, brightness_factor)
        return img
    
class AddGaussianNoise:
    def __init__(self, mean=0.0, std_min=0.05, std_max=0.08):
        self.mean = mean
        self.std_min = std_min
        self.std_max = std_max

    def __call__(self, tensor):
        std = random.uniform(self.std_min, self.std_max)
        noise = torch.randn(tensor.size()) * std + self.mean
        tensor = tensor + noise
        tensor = torch.clamp(tensor, 0., 1.)
        return tensor