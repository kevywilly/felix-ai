"""
Hardware-free tests for the ObjectSeeker smoothness/consistency control layer.

ObjectSeeker touches no hardware in __init__, so we drive it by feeding
DetectionFrames through its signal handler and capturing the Twists it publishes
on Topics.cmd_vel. These pin the follow behaviour (deadband, strafe-to-centre,
sticky lock, coast-through-dropouts, staleness watchdog, graduated ToF) so a
future gain refactor can't silently regress it.
"""

import time

import pytest

from felix.settings import settings
from felix.signals import Topics
from felix.nodes.object_seeker import ObjectSeeker
from lib.interfaces import Detection, DetectionFrame, SensorReading


def _frame(*dets):
    return DetectionFrame(detections=list(dets), width=640, height=480, ts=int(time.time()))


def _det(label="person", conf=0.9, cx=0.5, cy=0.5, w=0.1, h=0.1):
    return Detection(label=label, confidence=conf,
                     x1=cx - w / 2, y1=cy - h / 2, x2=cx + w / 2, y2=cy + h / 2)


class CmdVelSink:
    """Captures cmd_vel Twists sent by the seeker (strong ref keeps it subscribed)."""
    def __init__(self):
        self.twists = []
        Topics.cmd_vel.connect(self._on, weak=False)

    def _on(self, sender, payload):
        self.twists.append(payload)

    @property
    def last(self):
        return self.twists[-1] if self.twists else None

    def close(self):
        Topics.cmd_vel.disconnect(self._on)


@pytest.fixture
def sink():
    s = CmdVelSink()
    yield s
    s.close()


def _active_seeker():
    sk = ObjectSeeker(target_label="person")
    sk._last_spin = time.monotonic()  # make _dt() small/deterministic
    Topics.seek.send("test", payload=True)
    return sk


def test_centered_target_is_in_deadband_no_lateral_command(sink):
    sk = _active_seeker()
    sk._on_detections("d", _frame(_det(cx=0.5, cy=0.4)))
    sk.spinner()
    t = sink.last
    assert t is not None
    assert t.linear.y == 0.0          # deadband: no strafe when centred
    assert t.angular.z == 0.0         # and no yaw
    assert t.linear.x > 0.0           # but still drives forward (target above centre)


def test_offcenter_target_strafes_toward_it_without_yaw(sink):
    sk = _active_seeker()
    # target to the right (cx>0.5) but within yaw_crossover -> strafe only.
    # x_rel = 2*0.6-1 = 0.2, which is > deadband (0.06) and < crossover (0.35).
    sk._on_detections("d", _frame(_det(cx=0.60, cy=0.5)))
    sk.spinner()
    t = sink.last
    assert t.linear.y < 0.0           # x_rel>0 -> linear.y negative = toward right
    assert t.angular.z == 0.0         # below crossover: no rotation


def test_far_offcenter_target_adds_yaw(sink):
    sk = _active_seeker()
    sk._on_detections("d", _frame(_det(cx=0.98, cy=0.5)))
    sk.spinner()
    t = sink.last
    assert t.angular.z < 0.0          # well past crossover -> re-aim by yawing
    assert t.linear.y < 0.0


def test_sticky_lock_prefers_previous_target_over_larger_box(sink):
    sk = _active_seeker()
    # Acquire a small target on the left.
    sk._on_detections("d", _frame(_det(cx=0.3, cy=0.5, w=0.08, h=0.08)))
    sk.spinner()
    assert sk._lock_cx == pytest.approx(0.3)
    # Now a much larger person appears on the right; sticky lock should keep the
    # original (close to last lock) instead of jumping to the bigger box.
    sk._on_detections("d", _frame(
        _det(cx=0.32, cy=0.5, w=0.08, h=0.08),   # same target, drifted slightly
        _det(cx=0.85, cy=0.5, w=0.40, h=0.40),   # larger distractor
    ))
    sk.spinner()
    assert sk._lock_cx == pytest.approx(0.32)


def test_confidence_gate_rejects_low_confidence(monkeypatch, sink):
    monkeypatch.setattr(settings, "SEEK_MIN_CONFIDENCE", 0.5)
    sk = _active_seeker()
    sk._on_detections("d", _frame(_det(cx=0.7, cy=0.5, conf=0.2)))
    sk.spinner()
    # Below the gate -> treated as no target -> a stop (zero) command.
    assert sk._best_target() is None


def test_coast_through_single_dropout_then_stop(sink):
    sk = _active_seeker()
    sk._on_detections("d", _frame(_det(cx=0.7, cy=0.5)))
    sk.spinner()
    driving = sink.last
    assert driving.linear.x != 0.0 or driving.linear.y != 0.0
    # Empty frame (YOLO miss) but detections still fresh -> coast (keep driving).
    sk._on_detections("d", _frame())
    sk.spinner()
    assert sk._driving is True
    assert sk._miss == 1


def test_staleness_watchdog_stops_when_detections_dry_up(sink):
    sk = _active_seeker()
    sk._on_detections("d", _frame(_det(cx=0.7, cy=0.5)))
    sk.spinner()
    assert sk._driving is True
    # Simulate detector stall: last receipt far in the past.
    sk._last_rx = time.monotonic() - (settings.SEEK_LOST_TIMEOUT + 1.0)
    sk.spinner()
    assert sk._driving is False
    assert sink.last.is_zero


def test_graduated_tof_scales_forward_speed(sink):
    sk = _active_seeker()
    # ToF mid-way between stop and slow thresholds -> partial forward speed.
    mid = (settings.SEEK_TOF_STOP_MM + settings.SEEK_TOF_SLOW_MM) // 2
    sk._on_pico_sensors("p", SensorReading(id=0, type="tof", value=mid, ts=0))
    sk._on_pico_sensors("p", SensorReading(id=1, type="tof", value=9999, ts=0))
    assert 0.0 < sk._tof_scale() < 1.0
    # Obstacle inside the stop threshold -> zero forward.
    sk._on_pico_sensors("p", SensorReading(id=0, type="tof", value=settings.SEEK_TOF_STOP_MM - 10, ts=0))
    assert sk._tof_scale() == 0.0


def test_slew_limits_command_step():
    from lib.motion import slew
    assert slew(0.0, 1.0, 0.1) == pytest.approx(0.1)
    assert slew(0.0, -1.0, 0.1) == pytest.approx(-0.1)
    assert slew(0.0, 0.05, 0.1) == pytest.approx(0.05)  # within step -> exact
