import os
from felix.training.base import Trainer
from felix.vision.roi_utils import ROITransform
import torch
import torch.nn.functional as F
import torch.optim as optim
import torchvision.transforms as transforms
from torchvision.models import (
    alexnet,
    AlexNet_Weights,
    resnet50,
    ResNet50_Weights,
    mobilenet_v3_large,
    MobileNet_V3_Large_Weights,
    mobilenet_v3_small,
    MobileNet_V3_Small_Weights,
)
from PIL import Image
import logging

# Assuming these imports from your existing code
from felix.settings import settings, ModelType
from felix.training.datasets import CustomImageFolder
from felix.training.transformations import RandomLowLightTransform, AddGaussianNoise
from nav_trainer import NavImageFolder

logger = logging.getLogger("trainer")


class ROIObstacleTrainer(Trainer):
    """
    Enhanced ObstacleTrainer with Region of Interest (ROI) preprocessing
    for better focus on relevant obstacle detection areas
    """

    def __init__(
        self,
        random_flip: bool = False,
        target_flips=None,
        pct_low_light=0.2,
        pct_noise=0.2,
        early_stop_threshold=0.98,
        train_nav: bool = False,
        *args,
        **kwargs,
    ):
        """
        Args:
            images_path: Path to training images
            model_type: 'resnet50', 'alexnet', 'mobilenet_v3_large', 'mobilenet_v3_small'
            roi_type: 'ground', 'adaptive', or 'none' (disables ROI)
            roi_height_ratio: Fraction of image height to keep
            roi_width_ratio: Fraction of image width to keep
            roi_vertical_offset: Where to start vertical crop (0.0=top, 1.0=bottom)
            Other args: Same as ObstacleTrainer
        """
        super().__init__(*args, **kwargs)
        self.random_flip = random_flip
        self.target_flips = target_flips
        self.pct_low_light = pct_low_light
        self.pct_noise = pct_noise
        self.early_stop_threshold = early_stop_threshold
        self.train_nav = train_nav
        self.model_file = settings.nav_model_file if train_nav else settings.model_file
        self.num_targets = settings.model_nav_num_targets if train_nav else settings.model_num_targets

        logger.info(
            "ROI Obstacle Trainer Loaded with settings: "
            f"random_flip={self.random_flip}, "
            f"target_flips={self.target_flips}, "
            f"pct_low_light={self.pct_low_light}, "
            f"pct_noise={self.pct_noise}, "
            f"early_stop_threshold={self.early_stop_threshold}"
        )

    def _get_roi_transform(self):
        if settings.model_use_roi:
            return ROITransform(
                roi_height_ratio=settings.model_roi_height_ratio,
                roi_vertical_offset=settings.model_roi_vertical_offset,
                roi_width_ratio=settings.model_roi_width_ratio,
            )

    def _get_dataset(self):
        """
        Create dataset with ROI preprocessing integrated into transform pipeline
        """
        # Start with ROI transform if enabled
        transform_list = []

        roi_transform = self._get_roi_transform()
        if roi_transform is not None:
            transform_list.append(roi_transform)
            logger.info(f"Added ROI transform: {type(roi_transform).__name__}")

        # Add standard transforms
        transform_list.extend(
            [
                RandomLowLightTransform(
                    min_factor=0.3, max_factor=0.5, p=self.pct_low_light
                ),
                transforms.ColorJitter(0.1, 0.1, 0.1, 0.1),
                transforms.Resize(
                    (224, 224)
                ),  # Resize (potentially cropped) image to 224x224
                transforms.ToTensor(),
                transforms.RandomApply(
                    [AddGaussianNoise(0.0, 0.05, 0.08)], p=self.pct_noise
                ),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

        if self.train_nav:
            logger.info("Creating navigation dataset with ROI transforms")
            return NavImageFolder(
                settings.TRAINING.navigation_path,
                transforms.Compose(transform_list),
            )
        else:
            return CustomImageFolder(
                settings.model_images,
                transforms.Compose(transform_list),
                target_flips=self.target_flips,
                random_flip=self.random_flip,
            )

    def _get_model(self):
        """
        Create and configure the model based on model_type
        """
        if settings.model_type == ModelType.resnet_50:
            model = resnet50(weights=ResNet50_Weights.DEFAULT)
            num_ftrs = model.fc.in_features
            model.fc = torch.nn.Linear(num_ftrs, self.num_targets)

        elif settings.model_type == ModelType.mobilenet_large:
            model = mobilenet_v3_large(weights=MobileNet_V3_Large_Weights.DEFAULT)
            # MobileNetV3 classifier is a Sequential with Linear layer at index 3
            model.classifier[3] = torch.nn.Linear(
                model.classifier[3].in_features, self.num_targets
            )

        elif settings.model_type == ModelType.mobilenet_small:
            model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
            # MobileNetV3 classifier is a Sequential with Linear layer at index 3
            model.classifier[3] = torch.nn.Linear(
                model.classifier[3].in_features, self.num_targets
            )

        elif settings.model_type == ModelType.alexnet:
            model = alexnet(weights=AlexNet_Weights.DEFAULT)
            model.classifier[6] = torch.nn.Linear(
                model.classifier[6].in_features, self.num_targets
            )

        logger.info(f"Created model: {settings.model_type}")
        return model

    def train(self):
        """
        Training loop with ROI-enhanced dataset
        """
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

        model_exists = os.path.isfile(self.model_file)

        # Create model based on model_type
        model = self._get_model()

        if model_exists:
            model.load_state_dict(torch.load(self.model_file, weights_only=False))
            logger.info(f"Loaded existing model from {self.model_file}")

        device = torch.device("cuda" if torch.backends.cuda.is_built() else "cpu")
        model = model.to(device)
        logger.info(f"Using device: {device}")

        best_accuracy = 0.0
        optimizer = optim.SGD(
            model.parameters(), lr=self.lr, momentum=self.momentum, weight_decay=1e-4
        )

        logger.info(f"Starting training for {self.epochs} epochs...")

        for epoch in range(self.epochs):
            # Training phase
            model.train()
            running_loss = 0.0

            for batch_idx, (images, labels) in enumerate(train_loader):
                images = images.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()
                outputs = model(images)
                loss = F.cross_entropy(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item()

            # Evaluation phase
            model.eval()
            correct_predictions = 0
            total_predictions = 0

            with torch.no_grad():
                for images, labels in test_loader:
                    images = images.to(device)
                    labels = labels.to(device)
                    outputs = model(images)

                    # Get predicted classes
                    predicted = outputs.argmax(1)

                    # Count correct predictions
                    correct_predictions += (predicted == labels).sum().item()
                    total_predictions += labels.size(0)

            test_accuracy = correct_predictions / total_predictions
            avg_loss = running_loss / len(train_loader)

            logger.info(
                f"Epoch {epoch}: Accuracy={test_accuracy:.4f}, Loss={avg_loss:.4f}"
            )
            print(f"Epoch {epoch}: Accuracy={test_accuracy:.4f}, Loss={avg_loss:.4f}")

            # Save best model
            if test_accuracy >= best_accuracy:
                torch.save(model.state_dict(), self.model_file)
                best_accuracy = test_accuracy
                logger.info(f"New best accuracy: {best_accuracy:.4f} - Model saved")

            if best_accuracy >= self.early_stop_threshold:
                logger.info(
                    f"Early stopping as accuracy {best_accuracy:.4f} reached threshold {self.early_stop_threshold}"
                )
                break

        logger.info(f"Training completed! Best accuracy: {best_accuracy:.4f}")
        return best_accuracy

    def visualize_roi_samples(self, num_samples=5, save_path=None):
        """
        Visualize what the ROI transform is doing to sample images
        """
        try:
            import matplotlib.pyplot as plt

            # Get some sample images
            dataset = self._get_dataset()

            fig, axes = plt.subplots(num_samples, 3, figsize=(15, 3 * num_samples))
            fig.suptitle(
                f"ROI Visualization - ROI {settings.model_use_roi} ", fontsize=16
            )

            for i in range(min(num_samples, len(dataset))):
                # Get original image (before transforms)
                img_path = dataset.samples[i][0]
                original_img = Image.open(img_path)

                # Apply only ROI transform
                roi_transform = self._get_roi_transform()
                if roi_transform:
                    roi_img = roi_transform(original_img)
                else:
                    roi_img = original_img

                # Apply full transform pipeline
                transformed_tensor = dataset[i][0]

                # Convert tensor back to displayable image
                # Denormalize
                mean = torch.tensor([0.485, 0.456, 0.406])
                std = torch.tensor([0.229, 0.224, 0.225])
                transformed_img = (
                    transformed_tensor * std[:, None, None] + mean[:, None, None]
                )
                transformed_img = torch.clamp(transformed_img, 0, 1)
                transformed_img = transforms.ToPILImage()(transformed_img)

                # Plot
                axes[i, 0].imshow(original_img)
                axes[i, 0].set_title(f"Original ({original_img.size})")
                axes[i, 0].axis("off")

                axes[i, 1].imshow(roi_img)
                axes[i, 1].set_title(f"ROI Cropped ({roi_img.size})")
                axes[i, 1].axis("off")

                axes[i, 2].imshow(transformed_img)
                axes[i, 2].set_title("Final Transform (224x224)")
                axes[i, 2].axis("off")

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=150, bbox_inches="tight")
                logger.info(f"ROI visualization saved to {save_path}")

            plt.show()

        except ImportError:
            logger.warning("matplotlib not available for visualization")
        except Exception as e:
            logger.error(f"Error creating ROI visualization: {e}")
