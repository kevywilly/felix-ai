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


# Minimum clearance per direction. Tuned vs. the 265mm track width.
MIN_CLEARANCE_MM = {
    Direction.FORWARD:      500,
    Direction.LEFT:         350,
    Direction.RIGHT:        350,
    Direction.STRAFE_LEFT:  400,
    Direction.STRAFE_RIGHT: 400,
}

# Preference order when multiple directions are viable.
PREFERENCE = [
    Direction.FORWARD,
    Direction.STRAFE_LEFT,
    Direction.STRAFE_RIGHT,
    Direction.LEFT,
    Direction.RIGHT,
]

SCAN_STALE_SEC = 1.0


class LidarAutoDriver(BaseNode):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_active = False
        self._latest: Optional[LidarReading] = None
        self.smoother = TwistSmoother()
        self._last_spin: Optional[float] = None

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
        self.logger.info(f"LidarAutoDrive is_active: {self.is_active}")

    def _on_stop(self, sender, **kwargs):
        self.logger.info("Stop signal received, deactivating autodrive.")
        self.is_active = False
        self.smoother.reset()

    # Decision

    def _pick_direction(self, reading: LidarReading) -> Direction:
        viable = [
            d for d in MIN_CLEARANCE_MM
            if reading.is_safe(d, MIN_CLEARANCE_MM[d])
        ]
        if not viable:
            return Direction.NA
        for d in PREFERENCE:
            if d in viable:
                return d
        return Direction.NA

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
            cmd.linear.x = linear * 0.75
            cmd.linear.y = linear * 0.75
        elif direction == Direction.STRAFE_RIGHT:
            cmd.linear.x = linear * 0.75
            cmd.linear.y = -linear * 0.75
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