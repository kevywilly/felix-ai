#!/usr/bin/python3
from src.training.obstacle_trainer import ObstacleTrainer
from settings import settings
import os

if __name__ == "__main__":
    trainer = ObstacleTrainer(
        images_path=settings.TRAINING.tags_path, 
        model_file=os.path.join(settings.TRAINING.model_root,'checkpoints/binary_obstacle_avoidance.pth')
    )
    trainer.train()