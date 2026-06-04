"""
Regression test for the autodrive "spins continuously" bug.

Root cause: the trainer wrote weights to ``settings.model_file`` (which carries a
``roi_`` prefix when ``model_use_roi`` is on), but the inference drivers loaded
``settings.TRAINING.training_model_path`` instead. With ROI enabled the two paths
diverge, so autodrive loaded a stale, pre-ROI model and fed it ROI-cropped frames,
producing garbage predictions that locked the robot into a continuous turn.

These tests lock the invariant: the path the drivers load MUST equal the path the
trainer writes, and that path must track the ``model_use_roi`` flag.
"""

from felix.settings import settings
from felix.nodes.autodriver import BinaryObstacleAvoider, TernaryObstacleAvoider


def test_ternary_driver_loads_trainer_output_path():
    driver = TernaryObstacleAvoider()
    # The trainer writes to settings.model_file; inference must read the same file.
    assert driver.model_file == settings.model_file


def test_binary_driver_loads_trainer_output_path():
    driver = BinaryObstacleAvoider()
    assert driver.model_file == settings.model_file


def test_model_file_tracks_roi_flag():
    # The bug was only visible because settings.model_file and training_model_path
    # diverge when ROI is enabled. Pin that relationship so a future change that
    # silently re-converges them (or breaks the prefix) is caught here.
    import os

    base = settings.TRAINING.training_model_path
    if settings.model_use_roi:
        assert settings.model_file != base
        assert os.path.basename(settings.model_file).startswith("roi_")
    else:
        assert settings.model_file == base
