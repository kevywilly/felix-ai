#!/usr/bin/python3
from felix.training.obstacle_trainer import ObstacleTrainer
from felix.settings import settings
import os
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="This scripts trains Felix's Brain.")
    parser.add_argument("epochs", type=int, help='Number of epochs', default=30)
    
    args = parser.parse_args()

    epochs = args.epochs or 30
    
    if settings.TRAINING.mode == "ternary":
        target_flips = [0, 2, 1]
    else:
        target_flips = None

    trainer = ObstacleTrainer(
        epochs=epochs,
        images_path=settings.TRAINING.training_images_path,
        random_flip=True,
        target_flips=target_flips,
        model_file=settings.TRAINING.training_model_path
    )

    trainer.train()
