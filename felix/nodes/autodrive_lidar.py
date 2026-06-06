"""
LiDAR-driven autodriver. Consumes LidarReading payloads from Topics.lidar
(published by LidarSensor) and emits smoothed Twist commands via cmd_vel.

This no longer owns the lidar device. Construct a LidarSensor in app.py
and spin it; this node subscribes automatically.
"""

import time
from typing import Optional

from felix.nodes.lidar_sensor import Direction, LidarReading
from felix.settings import settings
from felix.signals import Topics
from lib.interfaces import Twist, Vector3
from lib.motion import TwistSmoother
from lib.nodes.base import BaseNode


DEBUG = True


# Forward clearance needed to keep driving straight. Tuned vs. the 265mm track.
FORWARD_CLEAR_MM = 500

# "Obviously clear" threshold for sidestepping. We strafe ONLY when a side is
# this open (both the pure-side sector AND the forward-diagonal on that side),
# so the lateral move can't carry us into something. Anything less decisive and
# we turn in place instead. Deliberately well above FORWARD_CLEAR_MM.
STRAFE_CLEAR_MM = 700

# Hysteresis for committing to an avoidance maneuver. Once forward is blocked we
# latch ONE direction and hold it until forward is *clearly* open again, instead
# of re-deciding every tick (which makes the robot oscillate left/right/left).
# Resuming forward needs more room than triggered avoidance (RESUME > CLEAR) so
# we don't flip-flop right at the threshold.
FORWARD_RESUME_MM = 650
# A committed *strafe* aborts (and re-picks, possibly turning) if the side it is
# sliding toward closes to within this distance -- the only reason to break
# commitment is to avoid hitting something. A committed *turn* never translates
# the robot, so it is held unconditionally until forward opens.
STRAFE_ABORT_MM = 350

# Directional memory between separate turn maneuvers. In a corner each short
# rotation briefly clears forward, the robot nibbles ahead, re-blocks, and would
# otherwise re-pick the turn direction from scratch -- which flips every time
# (left, right, left) and never escapes. So when starting a NEW turn we keep the
# previous turn direction unless the opposite side is clearer by at least this
# margin, turning the ping-pong into a consistent sweep out of the corner.
TURN_SWITCH_MARGIN_MM = 250

SCAN_STALE_SEC = 1.0


class LidarAutoDriver(BaseNode):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_active = False
        self._latest: Optional[LidarReading] = None
        self.smoother = TwistSmoother()
        self._last_spin: Optional[float] = None
        # Latched avoidance direction (LEFT/RIGHT/STRAFE_*), or None when driving
        # forward. Held across ticks so we commit to one maneuver. See
        # _pick_direction.
        self._evade_dir: Optional[Direction] = None
        # Last turn direction (LEFT/RIGHT), remembered across maneuvers so we
        # keep sweeping the same way out of a corner instead of zigzagging.
        self._last_turn: Optional[Direction] = None

        Topics.autodrive.connect(self._on_autodrive)
        Topics.stop.connect(self._on_stop)
        Topics.lidar.connect(self._on_lidar)

        self.logger.info("LidarAutoDriver initialized (consumer mode)")

    # Signal handlers

    def _on_lidar(self, sender, payload: LidarReading):
        self._latest = payload

    def _on_autodrive(self, sender, **kwargs):
        self.is_active = not self.is_active
        if not self.is_active:
            self.smoother.reset()
            self._evade_dir = None
            self._last_turn = None
            # The spinner just stops emitting cmd_vel, but the controller holds
            # the last motor command until a new one arrives -- so without an
            # explicit zero here the wheels keep spinning after toggling off.
            # Goes over the signal bus, which is what reaches the spun controller
            # (a direct controller.stop() hits the non-spun UI-side instance).
            Topics.cmd_vel.send("lidar_autodrive", payload=Twist())
        self.logger.info(f"LidarAutoDrive is_active: {self.is_active}")

    def _on_stop(self, sender, **kwargs):
        self.logger.info("Stop signal received, deactivating autodrive.")
        self.is_active = False
        self.smoother.reset()
        self._evade_dir = None
        self._last_turn = None

    # Decision

    def _pick_direction(self, reading: LidarReading) -> Direction:
        fwd = reading.clearance(Direction.FORWARD)

        # --- Honor an in-progress avoidance maneuver (anti-oscillation) ---
        # Once forward is blocked we COMMIT to one direction and hold it rather
        # than re-deciding from scratch every tick -- otherwise the robot waffles
        # left/right/left as the scan marginally favors first one side then the
        # other. We only break commitment to resume forward, or to avoid hitting
        # something while strafing.
        if self._evade_dir is not None:
            if fwd >= FORWARD_RESUME_MM:
                # Forward clearly open again (needs MORE room than triggered the
                # maneuver, so we don't flip-flop at the edge) -> end avoidance.
                self._evade_dir = None
            elif self._evade_dir in (Direction.LEFT, Direction.RIGHT):
                # Turning in place never translates the robot, so it can't drive
                # into anything -- keep turning the SAME way until forward opens.
                # This is the core fix for the L/R/L/R oscillation.
                return self._evade_dir
            elif reading.clearance(self._evade_dir) >= STRAFE_ABORT_MM:
                # Committed strafe still has room on the side it's sliding toward.
                return self._evade_dir
            else:
                # Strafe path is closing -> drop commitment and re-pick below
                # (which will most likely switch us to a turn).
                self._evade_dir = None

        # --- Drive forward when the path is clear and we're not mid-maneuver ---
        if self._evade_dir is None and fwd >= FORWARD_CLEAR_MM:
            return Direction.FORWARD

        # --- Forward blocked: start a new maneuver and latch it ---
        # Strafe ONLY if a side is obviously clear (both the side sector AND the
        # forward-diagonal on that side); otherwise turn toward the more open
        # side. A lateral move into a non-obvious gap is how we hit walls.
        left_open = (
            reading.is_safe(Direction.STRAFE_LEFT, STRAFE_CLEAR_MM)
            and reading.is_safe(Direction.LEFT, STRAFE_CLEAR_MM)
        )
        right_open = (
            reading.is_safe(Direction.STRAFE_RIGHT, STRAFE_CLEAR_MM)
            and reading.is_safe(Direction.RIGHT, STRAFE_CLEAR_MM)
        )
        if left_open or right_open:
            if left_open and right_open:
                # Both obvious -> sidestep toward the more open side.
                chosen = (
                    Direction.STRAFE_LEFT
                    if reading.clearance(Direction.STRAFE_LEFT)
                    >= reading.clearance(Direction.STRAFE_RIGHT)
                    else Direction.STRAFE_RIGHT
                )
            else:
                chosen = Direction.STRAFE_LEFT if left_open else Direction.STRAFE_RIGHT
        else:
            # No obvious sidestep -> turn in place toward the more open side,
            # but bias toward the last turn direction so we sweep consistently
            # out of a corner instead of flipping left/right every maneuver.
            left_space = min(
                reading.clearance(Direction.LEFT),
                reading.clearance(Direction.STRAFE_LEFT),
            )
            right_space = min(
                reading.clearance(Direction.RIGHT),
                reading.clearance(Direction.STRAFE_RIGHT),
            )
            if self._last_turn == Direction.LEFT and left_space + TURN_SWITCH_MARGIN_MM >= right_space:
                chosen = Direction.LEFT
            elif self._last_turn == Direction.RIGHT and right_space + TURN_SWITCH_MARGIN_MM >= left_space:
                chosen = Direction.RIGHT
            else:
                chosen = Direction.LEFT if left_space >= right_space else Direction.RIGHT
            self._last_turn = chosen

        self._evade_dir = chosen
        return chosen

    def decide(self) -> tuple[Direction, dict, bool]:
        reading = self._latest
        if reading is None:
            return Direction.NA, {}, False
        age = time.monotonic() - reading.timestamp
        if age > SCAN_STALE_SEC:
            self.logger.warning(f"Stale lidar reading (age={age:.2f}s)")
            return Direction.NA, reading.clearances, False
        return self._pick_direction(reading), reading.clearances, True

    def _direction_to_twist(self, direction: Direction, fresh: bool) -> Twist:
        cmd = Twist()
        if not fresh:
            return cmd

        linear = settings.autodrive_linear
        angular = settings.autodrive_angular

        if direction == Direction.FORWARD:
            cmd.linear.x = linear
        elif direction == Direction.STRAFE_LEFT:
            # Pure lateral sidestep. No forward x: forward is blocked (that's why
            # we're here), so advancing would drive into the obstacle. We only
            # strafe when the side is obviously clear, so pure-lateral is safe.
            cmd.linear.y = linear
        elif direction == Direction.STRAFE_RIGHT:
            cmd.linear.y = -linear
        elif direction == Direction.LEFT:
            cmd.angular.z = angular
        elif direction == Direction.RIGHT:
            cmd.angular.z = -angular
        else:
            # NA with fresh scan: nowhere viable, spin slowly to look for opening
            cmd.angular.z = angular * 0.5
        return cmd

    # Spinner

    def _dt(self) -> float:
        now = time.monotonic()
        prev = self._last_spin
        self._last_spin = now
        if prev is None:
            return 1.0 / max(self.frequency, 1)
        return min(max(now - prev, 1e-3), 0.5)

    def spinner(self):
        if not self.is_active:
            return

        try:
            direction, clearances, fresh = self.decide()

            if DEBUG and clearances:
                clr = ", ".join(
                    f"{d.value}={c:.0f}" if c != float('inf') else f"{d.value}=inf"
                    for d, c in clearances.items()
                )
                print(f"lidar -> {direction.value}  [{clr}]")

            raw = self._direction_to_twist(direction, fresh)
            vx, vy, wz = self.smoother.smooth(
                raw.linear.x, raw.linear.y, raw.angular.z,
                self._dt(),
                settings.AUTODRIVE_SLEW_LINEAR, settings.AUTODRIVE_SLEW_ANGULAR,
            )
            cmd = Twist(
                linear=Vector3(vx, vy, 0.0),
                angular=Vector3(0.0, 0.0, wz),
            )
            self.logger.info(f"LidarAutoDrive: {direction.value} -> {cmd}")
            Topics.cmd_vel.send("lidar_autodrive", payload=cmd)
        except Exception as ex:
            self.logger.error(f"LidarAutoDrive error: {ex}. Stopping.")
            self.smoother.reset()
            Topics.cmd_vel.send(
                "lidar_autodrive",
                payload=Twist(linear=Vector3(0, 0, 0), angular=Vector3(0, 0, 0)),
            )
            Topics.stop.send("lidar_autodrive")

    def shutdown(self):
        self.is_active = False