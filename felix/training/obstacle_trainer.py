


import os
from felix.training.base import Trainer
import torch
import torch.nn.functional as F
import torch.optim as optim
import torchvision.transforms as transforms
from torchvision.models import alexnet, AlexNet_Weights, resnet50, ResNet50_Weights

from felix.settings import settings
from felix.training.datasets import CustomImageFolder
from felix.training.transformations import RandomLowLightTransform, AddGaussianNoise
import logging


logger = logging.getLogger(__name__)

class ObstacleTrainer(Trainer):
    def __init__(
        self, 
        random_flip: bool = False, 
        target_flips=None, 
        pct_low_light=0.2,
        pct_noise=0.2,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.random_flip = random_flip
        self.target_flips = target_flips
        self.pct_low_light = pct_low_light
        self.pct_noise = pct_noise

        logger.info(
            f"Obstacle Trainer Loaded\n"
            f"\trandom_flip: {self.random_flip}\n"
            f"\ttarget_flips: {self.target_flips}\n"
            f"\tpct_low_light: {self.pct_low_light}\n"
            f"\tpct_noise: {self.pct_noise}\n"
        )

    def _get_dataset(self):

        items = [
            RandomLowLightTransform(min_factor=0.3, max_factor=0.5, p=self.pct_low_light),
            transforms.ColorJitter(0.1, 0.1, 0.1, 0.1),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.RandomApply([AddGaussianNoise(0.0, 0.05, 0.08)], p=self.pct_noise),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]

        return CustomImageFolder(
            settings.model_images,
            transforms.Compose(items),
            target_flips=self.target_flips,
            random_flip=self.random_flip,
        )

    def train(self):
        dataset = self._get_dataset()
        test_size = int(len(dataset) * self.test_pct / 100.0)
        train_dataset, test_dataset = torch.utils.data.random_split(
            dataset, [len(dataset) - test_size, test_size]
        )

        train_loader = torch.utils.data.DataLoader(
            train_dataset,
            batch_size=8,
            shuffle=True,
            num_workers=0,
        )

        test_loader = torch.utils.data.DataLoader(
            test_dataset,
            batch_size=8,
            shuffle=True,
            num_workers=0,
        )

        model_exists = os.path.isfile(settings.model_file)

        if use_resnet50:
            model = resnet50(weights=ResNet50_Weights.DEFAULT)
            num_ftrs = model.fc.in_features
            model.fc = torch.nn.Linear(num_ftrs, settings.model_num_targets)
        else:
            model = alexnet(weights=AlexNet_Weights.DEFAULT)
            model.classifier[6] = torch.nn.Linear(
                model.classifier[6].in_features, settings.model_num_targets
            )
        if model_exists:
            model.load_state_dict(torch.load(settings.model_file, weights_only=False))

        device = torch.device("cuda" if torch.backends.cuda.is_built() else "cpu")
        model = model.to(device)

        best_accuracy = 0.0
        optimizer = optim.SGD(model.parameters(), lr=self.lr, momentum=self.momentum, weight_decay=1e-4)

        for epoch in range(self.epochs):
            for images, labels in iter(train_loader):
                images = images.to(device)
                labels = labels.to(device)
                optimizer.zero_grad()
                outputs = model(images)
                loss = F.cross_entropy(outputs, labels)
                loss.backward()
                optimizer.step()

            test_error_count = 0.0
            for images, labels in iter(test_loader):
                images = images.to(device)
                labels = labels.to(device)
                outputs = model(images)
                test_error_count += float(
                    torch.sum(torch.abs(labels - outputs.argmax(1)))
                )

            test_accuracy = 1.0 - float(test_error_count) / float(len(test_dataset))
            print("%d: %f" % (epoch, test_accuracy))
            if test_accuracy > best_accuracy:
                torch.save(model.state_dict(), settings.model_file)
                best_accuracy = test_accuracy
