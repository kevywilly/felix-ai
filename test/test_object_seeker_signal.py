"""
Regression test for the "Seek mode never drives" bug.

Root cause: app.py is evaluated twice (NiceGUI re-imports the module), so every
node is constructed twice. ``felix.signals.Topics`` is a singleton, so signals
are shared across both copies -- but the Seek control toggled the seeker with a
*direct method call* (``object_seeker.activate(...)``) instead of a signal. That
flipped only the UI-side instance; the instance actually being spun never had
``is_active`` set, so its spinner returned at the ``is_active`` gate every tick
and never issued a ``cmd_vel``. AutoDrive worked because it toggles via the
shared ``Topics.autodrive`` signal, which reaches the spun instance.

These tests lock the fix: Seek activation and target selection MUST travel over
``Topics.seek`` / ``Topics.seek_target`` so any instance (including the spun one)
receives them -- never a direct call that only one of the duplicate instances
sees. ObjectSeeker touches no hardware in __init__, so this runs as a plain unit
test.
"""

from felix.signals import Topics
from felix.nodes.object_seeker import ObjectSeeker


def test_seek_signal_activates_a_separately_constructed_instance():
    # Two instances, mirroring the double-instantiation. The signal must reach
    # whichever instance is "the spun one" -- here, both -- regardless of which
    # one any UI code happens to hold a direct reference to.
    spun = ObjectSeeker(target_label="person")
    other = ObjectSeeker(target_label="person")
    assert spun.is_active is False

    Topics.seek.send("felix", payload=True)
    assert spun.is_active is True
    assert other.is_active is True

    Topics.seek.send("felix", payload=False)
    assert spun.is_active is False


def test_seek_target_signal_retargets_the_spun_instance():
    spun = ObjectSeeker(target_label="person")
    Topics.seek_target.send("felix", payload="chair")
    assert spun.target_label == "chair"
