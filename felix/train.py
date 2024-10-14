#!/usr/bin/python3
from felix.training.obstacle_trainer import ObstacleTrainer
from felix.settings import settings
import os
import argparse
from datetime import datetime
from felix.utils.file import move_file_with_timestamp

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="This scripts trains Felix's Brain.")
    parser.add_argument("epochs", type=int, help='Number of epochs', default=50)
    parser.add_argument("--pct-low-light", type=float, help='Low light sample percentage', default=0.2)
    parser.add_argument("--pct-noise", type=float, help='Noise sample percentage', default=0.2)
    parser.add_argument("--iterations", type=int, help='Number of iterations', default=1)
    parser.add_argument("--start-clean", type=bool, help="Start with a clean model", default=False)
    
    args = parser.parse_args()

    epochs = args.epochs
    pct_noise = args.pct_noise
    pct_low_light = args.pct_low_light
    iterations = args.iterations
    start_clean = args.start_clean

    print("-------------------------------------------")
    print("Starting trainer with args")
    print("-------------------------------------------")
    print(args)
    print("-------------------------------------------")
    

    if settings.TRAINING.mode == "ternary":
        target_flips = [0, 2, 1]
    else:
        target_flips = None

    if start_clean:
        move_file_with_timestamp(settings.TRAINING.training_model_path)

    trainer = ObstacleTrainer(
        epochs=epochs,
        images_path=settings.TRAINING.training_images_path,
        random_flip=True,
        target_flips=target_flips,
        model_file=settings.TRAINING.training_model_path,
        pct_noise=pct_noise,
        pct_low_light=pct_low_light
    )

    for i in range(iterations):
        print("----------------------------------------------------------")
        print(f"\tIteration {i+1} of {iterations}")
        print("----------------------------------------------------------")
        trainer.train()
