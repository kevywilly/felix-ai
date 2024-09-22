#!/usr/bin/python3
from src.training.obstacle_trainer import ObstacleTrainer
from src.settings import settings
import os


def train_binary_obstacles():
    return ObstacleTrainer(
        images_path=settings.TRAINING.tags_path,
        random_flip=True,
        model_file=os.path.join(settings.TRAINING.model_root, 'checkpoints/binary_obstacle_avoidance.pth')
    )


def train_ternary_obstacles():
    return ObstacleTrainer(
        images_path=os.path.join(settings.TRAINING.data_root, "training/ternary"),
        random_flip=True,
        target_flips={1: 2, 2: 1},
        model_file=os.path.join(settings.TRAINING.model_root, 'checkpoints/ternary_obstacle_avoidance.pth')
    )


if __name__ == "__main__":
    train_ternary_obstacles().train()

