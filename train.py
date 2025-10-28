#!/usr/bin/python3
from felix.training.roi_trainer import ROIObstacleTrainer
from felix.settings import settings
from felix.utils.file import move_file_with_timestamp
import logging
import click

logger = logging.getLogger("train")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@click.command()
@click.argument("epochs", type=int, default=5)
@click.option(
    "--pct-low-light", type=float, default=0.2, help="Low light sample percentage"
)
@click.option("--pct-noise", type=float, default=0.2, help="Noise sample percentage")
@click.option("--lr", type=float, default=0.001, help="Learning rate")
@click.option("--test-pct", type=int, default=30, help="Percentage of data for testing")
@click.option("--iterations", type=int, default=1, help="Number of iterations")
@click.option(
    "--threshold",
    type=float,
    default=0.98,
    help="Accuracy threshold for early stopping",
)
@click.option("--start-clean", is_flag=True, help="Start with a clean model")
@click.option("--train-nav", is_flag=True, help="Train navigation model")
def cli(
    epochs,
    pct_low_light,
    pct_noise,
    lr,
    test_pct,
    iterations,
    threshold,
    start_clean,
    train_nav
):
    """
    This script trains Felix's Brain.
    """

    logger.info(f"Starting trainer with args: {locals()}")

    if settings.TRAINING.mode == "ternary":
        target_flips = [0, 2, 1]
    else:
        target_flips = None

    if start_clean:
        if train_nav:
            move_file_with_timestamp(settings.nav_model_file)
        else:
            move_file_with_timestamp(settings.model_file)

    
    trainer = ROIObstacleTrainer(
        epochs=epochs,
        lr=lr,
        test_pct=test_pct,
        early_stop_threshold=threshold,
        pct_low_light=pct_low_light,
        pct_noise=pct_noise,
        train_nav=train_nav,
    )

    for i in range(iterations):
        logger.info(f"Iteration {i + 1} of {iterations}")
        result = trainer.train()
        if result >= threshold:
            logger.info(
                f"Reached accuracy threshold of {threshold}. Stopping training."
            )
            break


if __name__ == "__main__":
    cli()
