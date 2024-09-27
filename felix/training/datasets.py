from typing import Tuple, Any, Optional, Callable

import numpy as np
from torchvision import transforms
from torchvision.datasets import ImageFolder
from torchvision.datasets.folder import default_loader


class CustomImageFolder(ImageFolder):

    def __init__(
            self,
            root: str,
            transform: Optional[Callable] = None,
            target_transform: Optional[Callable] = None,
            loader: Callable[[str], Any] = default_loader,
            is_valid_file: Optional[Callable[[str], bool]] = None,
            random_flip=False,
            target_flips=None
    ):
        super().__init__(root, transform, target_transform, loader, is_valid_file)
        self.target_flips = target_flips
        self.random_flip = random_flip

    def __getitem__(self, index: int) -> Tuple[Any, Any]:
        """
                Args:
                    index (int): Index

                Returns:
                    tuple: (sample, target) where target is class_index of the target class.
                """
        path, target = self.samples[index]
        sample = self.loader(path)

        if self.random_flip and (float(np.random.rand(1)) > 0.5):
            sample = transforms.functional.hflip(sample)
            if self.target_flips:
                tf = self.target_flips.get(target,None)
                if tf:
                    target = tf

        if self.transform is not None:
            sample = self.transform(sample)
        if self.target_transform is not None:
            target = self.target_transform(target)

        return sample, target