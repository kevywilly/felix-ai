"""
Unit tests for the shared, hardware-free motion-control core (lib/motion).

These pin the control math that both ObjectSeeker and AutoDriver depend on, so a
gain/law refactor can be validated on a laptop in milliseconds.
"""

import pytest

from lib.motion import TwistSmoother, VisualServo, clamp, deadband, ema, slew


# ---- pure helpers ---------------------------------------------------------

def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(99, 0, 10) == 10


def test_deadband():
    assert deadband(0.03, 0.06) == 0.0
    assert deadband(-0.03, 0.06) == 0.0
    assert deadband(0.2, 0.06) == 0.2


def test_ema_seeds_then_blends():
    assert ema(None, 1.0, 0.5) == 1.0          # first sample seeds
    assert ema(0.0, 1.0, 0.5) == pytest.approx(0.5)
    assert ema(0.0, 1.0, 1.0) == 1.0           # alpha=1 -> no smoothing


def test_slew():
    assert slew(0.0, 1.0, 0.1) == pytest.approx(0.1)
    assert slew(0.0, -1.0, 0.1) == pytest.approx(-0.1)
    assert slew(0.0, 0.05, 0.1) == pytest.approx(0.05)


# ---- TwistSmoother --------------------------------------------------------

def test_smoother_ramps_toward_target():
    s = TwistSmoother()
    vx, vy, wz = s.smooth(1.0, 0.0, 0.0, dt=0.1, slew_linear=2.0, slew_angular=2.0)
    assert vx == pytest.approx(0.2)            # 2.0 * 0.1 step
    vx, _, _ = s.smooth(1.0, 0.0, 0.0, dt=0.1, slew_linear=2.0, slew_angular=2.0)
    assert vx == pytest.approx(0.4)            # keeps ramping
    assert s.last[0] == pytest.approx(0.4)


def test_smoother_zero_target_snaps_immediately():
    s = TwistSmoother()
    s.smooth(1.0, 1.0, 1.0, dt=0.1, slew_linear=0.5, slew_angular=0.5)
    # A full stop must not be slewed -- it snaps to zero so stops are never delayed.
    vx, vy, wz = s.smooth(0.0, 0.0, 0.0, dt=0.1, slew_linear=0.5, slew_angular=0.5)
    assert (vx, vy, wz) == (0.0, 0.0, 0.0)


def test_smoother_reset():
    s = TwistSmoother()
    s.smooth(1.0, 1.0, 1.0, dt=1.0, slew_linear=1.0, slew_angular=1.0)
    s.reset()
    assert s.last == (0.0, 0.0, 0.0)


# ---- VisualServo ----------------------------------------------------------

_GAINS = dict(linear=0.32, angular=1.0, strafe=0.4,
              deadband_width=0.06, ema_alpha=1.0, yaw_crossover=0.35)


def test_servo_centered_is_deadbanded():
    v = VisualServo()
    vx, vy, wz = v.compute(0.5, 0.4, **_GAINS)
    assert vy == 0.0 and wz == 0.0            # centred -> no lateral/yaw
    assert vx > 0.0                            # target above centre -> forward


def test_servo_small_offset_strafes_without_yaw():
    v = VisualServo()
    # cx=0.6 -> x_rel=0.2 (> deadband, < crossover): strafe only
    _, vy, wz = v.compute(0.6, 0.5, **_GAINS)
    assert vy < 0.0                            # toward right target
    assert wz == 0.0


def test_servo_large_offset_adds_yaw():
    v = VisualServo()
    _, vy, wz = v.compute(0.95, 0.5, **_GAINS)  # x_rel=0.9 > crossover
    assert wz < 0.0 and vy < 0.0


def test_servo_ema_smooths_across_calls():
    v = VisualServo()
    gains = {**_GAINS, "ema_alpha": 0.5, "deadband_width": 0.0}
    # First call seeds at the raw error; second call blends, so the smoothed
    # x error lands between the two raw inputs.
    v.compute(1.0, 0.5, **gains)               # x_rel seed = 1.0
    _, vy, _ = v.compute(0.5, 0.5, **gains)    # raw x_rel = 0.0 -> ema = 0.5
    assert vy == pytest.approx(-0.5 * gains["strafe"])
