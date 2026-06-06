"""
LiDAR sensor node, pyrplidar backend.

Owns the RPLidar device, reads measurements in a background thread,
groups them into scans on the start_flag boundary, and publishes
LidarReading payloads via Topics.lidar.

Install:
    pip install pyrplidar
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pyrplidar import PyRPlidar
from pyrplidar_protocol import PyRPlidarProtocolError, PyRPlidarConnectionError

from felix.signals import Topics
from lib.nodes.base import BaseNode


class Direction(str, Enum):
    NA = "NA"
    FORWARD = "FORWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    STRAFE_LEFT = "STRAFLEFT"
    STRAFE_RIGHT = "STRAFERIGHT"


SECTORS = {
    # FORWARD half_width meets the RIGHT/LEFT sectors (centered +-45, hw 15 ->
    # start at 30) with no gap, so a wall approached at a slight angle can't slip
    # into a blind wedge and read as "clear" while we drive into it.
    Direction.FORWARD:      {'center':   0, 'half_width': 30},
    Direction.RIGHT:        {'center':  45, 'half_width': 15},
    Direction.STRAFE_RIGHT: {'center':  90, 'half_width': 25},
    Direction.STRAFE_LEFT:  {'center': 270, 'half_width': 25},
    Direction.LEFT:         {'center': 315, 'half_width': 15},
}


@dataclass
class LidarReading:
    """One full scan, processed into robot-relative coordinates."""
    points: list = field(default_factory=list)
    clearances: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def clearance(self, direction: Direction) -> float:
        return self.clearances.get(direction, float('inf'))

    def is_safe(self, direction: Direction, min_mm: float) -> bool:
        return self.clearance(direction) >= min_mm

    def closest(self, half_width_deg: float = 180) -> Optional[tuple]:
        if not self.points:
            return None
        in_window = [
            (a, d) for (a, d) in self.points
            if (a <= half_width_deg) or (a >= 360 - half_width_deg)
        ]
        return min(in_window, key=lambda p: p[1]) if in_window else None


def _angle_in_sector(angle_deg, center, half_width):
    diff = ((angle_deg - center + 180) % 360) - 180
    return abs(diff) <= half_width


def compute_clearances(points):
    clearances = {}
    for direction, sec in SECTORS.items():
        in_sector = [
            d for (a, d) in points
            if _angle_in_sector(a, sec['center'], sec['half_width'])
        ]
        clearances[direction] = min(in_sector) if in_sector else float('inf')
    return clearances


# Resilience tuning
RESTART_DELAY_SEC = 1.0
MAX_CONSECUTIVE_FAILS = 8
HEALTHY_UPTIME_SEC = 30.0
# Motor PWM for A1: 660 is typical (~10 Hz), 1023 is max. 0 = off.
MOTOR_PWM = 660
# Minimum points per scan to consider healthy. A1 should give 250-500.
MIN_HEALTHY_POINTS = 200
# Bail if a single scan grows unrealistically large (indicates we never saw
# a start_flag, which means byte-level desync).
MAX_SCAN_POINTS = 1500


class LidarSensor(BaseNode):
    """
    Reads the RPLidar continuously and publishes LidarReading via Topics.lidar.

    Reader thread auto-restarts on protocol/connection errors. Spinner
    is a watchdog that warns if scans stop arriving.
    """

    def __init__(
        self,
        device_path: str = '/dev/rplidar',
        baud_rate: int = 115200,
        forward_offset_deg: float = 0.0,
        motor_pwm: int = MOTOR_PWM,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.device_path = device_path
        self.baud_rate = baud_rate
        self.forward_offset_deg = forward_offset_deg
        self.motor_pwm = motor_pwm

        self._lidar: Optional[PyRPlidar] = None
        self._latest: Optional[LidarReading] = None
        self._lock = threading.Lock()
        self._reader_stop = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._started = False
        self._scan_count = 0
        self._last_rate_check = time.monotonic()
        self._stale_warned = False

        # Motor/reader enable gate, toggled from the UI via Topics.lidar_motor.
        # Default ON. When cleared, the reader loop exits and the supervisor
        # closes the device (which spins the motor down) and parks until re-set.
        # We cannot just call set_motor_pwm(0) mid-scan: the scan generator would
        # block forever waiting for measurements that stop arriving.
        self._motor_enabled = threading.Event()
        self._motor_enabled.set()
        Topics.lidar_motor.connect(self._on_lidar_motor)

        # IMPORTANT: do NOT open the device or spawn the reader here.
        # NiceGUI re-imports this module in its server process, which
        # instantiates LidarSensor twice. Only the instance whose spin()
        # is actually awaited by on_startup should touch the hardware.
        # See _ensure_started() below.
        self.logger.info("LidarSensor instance created (reader deferred until spin)")

    def _on_lidar_motor(self, sender, payload: bool = True):
        """UI toggle for the spin motor. payload True=on, False=off."""
        if payload:
            self._motor_enabled.set()
            self.logger.info("Lidar motor enabled (will spin up on next supervisor pass)")
        else:
            self._motor_enabled.clear()
            self.logger.info("Lidar motor disabled (reader will stop and motor spin down)")

    def _ensure_started(self):
        """Spawn the reader thread on first spinner() call. Called only on
        the spun instance, which is the one we want to own the device."""
        if self._started:
            return
        self._started = True
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_supervisor,
            name="LidarReader",
            daemon=True,
        )
        self._reader_thread.start()
        self.logger.info("LidarSensor reader thread started (this is the spun instance)")

    def _open_device(self) -> bool:
        """Open serial, spin up motor, query health."""
        try:
            self._lidar = PyRPlidar()
            self._lidar.connect(
                port=self.device_path,
                baudrate=self.baud_rate,
                timeout=3,
            )
            # Spin up the motor. 0 = off, 1023 = max. Default 660 ~ 10Hz on A1.
            self._lidar.set_motor_pwm(self.motor_pwm)
            time.sleep(2.0)  # motor needs ~1-2s to reach steady speed

            info = self._lidar.get_info()
            health = self._lidar.get_health()
            self.logger.info(f"Lidar opened. info={info} health={health}")
            return True
        except Exception as ex:
            self.logger.error(f"Failed to open lidar: {ex!r}")
            self._close_device()
            return False

    def _close_device(self):
        if self._lidar is not None:
            try:
                self._lidar.stop()
                self._lidar.set_motor_pwm(0)
                time.sleep(0.2)
                self._lidar.disconnect()
            except Exception as ex:
                self.logger.warning(f"Error closing lidar: {ex!r}")
            self._lidar = None

    def _reader_supervisor(self):
        consecutive_fails = 0
        while not self._reader_stop.is_set():
            # Pause point: when the motor is disabled from the UI, keep the
            # device closed (motor off) and wait. The timeout lets us notice a
            # _reader_stop (shutdown) or re-enable promptly.
            if not self._motor_enabled.is_set():
                self._close_device()
                self._motor_enabled.wait(timeout=0.5)
                continue

            if not self._open_device():
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    self.logger.critical(
                        f"Lidar failed to open {consecutive_fails} times; giving up. "
                        f"Check {self.device_path}, USB cable, power."
                    )
                    return
                self._reader_stop.wait(RESTART_DELAY_SEC)
                continue

            loop_started = time.monotonic()
            try:
                self._reader_loop()
                consecutive_fails = 0
            except (PyRPlidarProtocolError, PyRPlidarConnectionError) as ex:
                uptime = time.monotonic() - loop_started
                if uptime >= HEALTHY_UPTIME_SEC:
                    self.logger.warning(
                        f"Lidar reader hiccup after {uptime:.0f}s healthy: {ex!r}. "
                        f"Restarting (fail counter reset)."
                    )
                    consecutive_fails = 0
                else:
                    consecutive_fails += 1
                    self.logger.error(
                        f"Lidar reader crashed after {uptime:.1f}s: {ex!r}. "
                        f"Restarting (fail {consecutive_fails}/{MAX_CONSECUTIVE_FAILS})."
                    )
            except Exception as ex:
                uptime = time.monotonic() - loop_started
                consecutive_fails += 1
                self.logger.error(
                    f"Lidar reader crashed ({type(ex).__name__}) after {uptime:.1f}s: "
                    f"{ex!r}. Restarting."
                )
            finally:
                self._close_device()

            if self._reader_stop.is_set():
                break
            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                self.logger.critical(
                    f"Lidar reader failed {consecutive_fails} times rapidly; giving up. "
                    f"Likely root cause: USB power, cable, or CPU starvation. "
                    f"Try a powered USB hub."
                )
                return
            self._reader_stop.wait(RESTART_DELAY_SEC)

    def _reader_loop(self):
        """Consume measurements, group into scans on start_flag, publish."""
        if self._lidar is None:
            return
        self.logger.info("Lidar reader loop entering start_scan...")
        scan_generator_factory = self._lidar.start_scan()
        scan_generator = scan_generator_factory()

        current_scan = []
        scans_emitted = 0
        low_count_warnings = 0

        for measurement in scan_generator:
            # Break while measurements are still flowing (motor still spinning),
            # so the loop can exit cleanly; the supervisor's finally then closes
            # the device and spins the motor down. Checking the flag here (not
            # after stopping the motor) is what avoids the generator deadlock.
            if self._reader_stop.is_set() or not self._motor_enabled.is_set():
                break

            # start_flag marks the first measurement of a new rotation.
            # Emit the previous scan if we have one.
            if measurement.start_flag and current_scan:
                self._publish_scan(current_scan)
                n = len(current_scan)
                scans_emitted += 1
                if scans_emitted == 1:
                    self.logger.info(f"First scan received: {n} points")
                if n < MIN_HEALTHY_POINTS:
                    low_count_warnings += 1
                    if low_count_warnings % 5 == 1:
                        self.logger.warning(
                            f"Low scan point count: {n} < {MIN_HEALTHY_POINTS}. "
                            f"Possible USB/cable/power issue."
                        )
                else:
                    low_count_warnings = 0
                current_scan = []

            # Drop bad measurements (quality 0 means no valid return).
            if measurement.quality > 0 and measurement.distance > 0:
                current_scan.append(measurement)

            # Sanity check: if we never see a start_flag, the stream is
            # desynced. Bail to trigger a restart.
            if len(current_scan) > MAX_SCAN_POINTS:
                raise PyRPlidarProtocolError(
                    f"No start_flag in {MAX_SCAN_POINTS}+ measurements; stream desynced"
                )

    def _publish_scan(self, measurements):
        """Convert pyrplidar measurements into LidarReading and broadcast."""
        points = []
        for m in measurements:
            adj = (m.angle - self.forward_offset_deg) % 360
            points.append((adj, m.distance))

        reading = LidarReading(
            points=points,
            clearances=compute_clearances(points),
            timestamp=time.monotonic(),
        )
        with self._lock:
            self._latest = reading
            self._scan_count += 1
            self._stale_warned = False
        Topics.lidar.send("lidar_sensor", payload=reading)

    def latest(self) -> Optional[LidarReading]:
        with self._lock:
            return self._latest

    def spinner(self):
        # Start the reader thread on first tick. This guarantees only the
        # spun instance opens the device (NiceGUI creates a second instance
        # via module re-import; that one never spins).
        self._ensure_started()

        with self._lock:
            reading = self._latest
            scans = self._scan_count

        now = time.monotonic()
        elapsed = now - self._last_rate_check
        if elapsed >= 5.0:
            rate = scans / elapsed if elapsed > 0 else 0.0
            self.logger.info(f"Lidar throughput: {rate:.1f} scans/sec")
            with self._lock:
                self._scan_count = 0
            self._last_rate_check = now

        if reading is None:
            return

        age = now - reading.timestamp
        if age > 1.0 and not self._stale_warned:
            self.logger.warning(
                f"Stale lidar reading (age={age:.2f}s). "
                f"Reader alive: {self._reader_thread.is_alive() if self._reader_thread else False}"
            )
            self._stale_warned = True

    def shutdown(self):
        if not self._started:
            return  # nothing to clean up on the non-spun instance
        self._reader_stop.set()
        # Wake the supervisor if it's parked in the motor-disabled wait so it
        # sees _reader_stop and exits promptly instead of after the timeout.
        self._motor_enabled.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=3.0)
        self._close_device()
        self.logger.info("LidarSensor shutdown complete")