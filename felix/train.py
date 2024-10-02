#!/usr/bin/python3
from felix.training.obstacle_trainer import ObstacleTrainer
from felix.settings import settings
import os

if __name__ == "__main__":
    if settings.TRAINING.mode == "ternary":
        target_flips = [0, 2, 1]
    else:
        target_flips = None

    trainer = ObstacleTrainer(
        images_path=settings.TRAINING.training_images_path,
        random_flip=True,
        target_flips=target_flips,
        model_file=settings.TRAINING.training_model_path
    )

    trainer.train()
