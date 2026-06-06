import time

from lib.nodes.base import BaseNode
from lib.interfaces import Twist, Vector3, SensorReading, DetectionFrame
from lib.motion import TwistSmoother, VisualServo
from felix.settings import settings
from felix.signals import Topics


class ObjectSeeker(BaseNode):
    """
    Object-seeking behavior. Subscribes to Topics.detections, locks onto a box
    matching ``target_label``, and steers toward it via Topics.cmd_vel.

    Steering mirrors the convention in controller.NavRequest.target:
        x_rel = 2*cx - 1   ( + => target is to the right )
        y_rel = 1 - cy     ( 1 => target high in frame / far away )
    so it inherits the same (already-correct) turn direction as click-to-navigate.

    Smoothness / consistency layer (all tunable under ``seek:`` in config.yml):
      * EMA low-pass on the image error + a centre deadband, so YOLO box jitter
        and tiny offsets don't translate into motor twitch.
      * Strafe-to-centre: small lateral error is corrected with ``linear.y`` on
        the mecanum base (keeps the camera pointed -> steadier detections);
        rotation is only added past ``yaw_crossover`` to re-aim on large errors.
      * Sticky, confidence-gated target selection: stay locked on the same object
        frame-to-frame instead of flipping to whatever box is largest right now.
      * Coast through brief detection dropouts (``coast_frames``) instead of
        lurching to a stop on every single missed frame.
      * Staleness watchdog: if detections stop arriving (detector/camera stall),
        hard-stop within ``lost_timeout`` instead of chasing a frozen box.
      * Graduated ToF slowdown: forward speed ramps to zero as an obstacle nears,
        replacing the old all-or-nothing veto.
      * Slew limiting on the emitted command for smooth accel/decel.

    Safety is preserved: it never *adds* motion when there is no target (one stop
    command), the ToF only ever reduces forward speed, and activation/target
    arrive as signals (Topics.seek / Topics.seek_target) so they reach the spun
    instance (app.py constructs nodes twice). See test/test_object_seeker_signal.py.
    """

    def __init__(
        self,
        target_label: str = "person",
        use_tof_safety: bool = True,
        **kwargs,
    ):
        super(ObjectSeeker, self).__init__(**kwargs)
        self.target_label = target_label
        self.use_tof_safety = use_tof_safety
        self.is_active = False

        self.latest: DetectionFrame | None = None
        self.tof: dict[int, int] = {}
        self._driving = False  # so we only emit one stop when the target is lost

        # smoothing / tracking / output state. The error->twist mapping and the
        # output slew limiting live in the shared lib.motion core so AutoDriver
        # (and any future driver) reuse the same tested control law.
        self.servo = VisualServo()
        self.smoother = TwistSmoother()
        self._lock_cx: float | None = None
        self._lock_cy: float | None = None
        self._miss = 0
        self._last_rx: float | None = None   # monotonic receipt time of last frame
        self._last_spin: float | None = None

        Topics.detections.connect(self._on_detections)
        Topics.pico_sensors.connect(self._on_pico_sensors)
        Topics.stop.connect(self._on_stop)
        # Activation/target arrive as signals so they reach the instance that is
        # actually being spun (app.py constructs nodes twice; a direct method
        # call would only reach the UI-side copy and never drive). See
        # test/test_object_seeker_signal.py.
        Topics.seek.connect(self._on_seek)
        Topics.seek_target.connect(self._on_seek_target)

        self.loaded()

    # ---- signal handlers ------------------------------------------------

    def _on_detections(self, sender, payload: DetectionFrame):
        self.latest = payload
        # Wall-clock receipt time at the seeker. DetectionFrame.ts is only
        # second-resolution, too coarse to gate an 8 Hz loop, so we stamp our own.
        self._last_rx = time.monotonic()

    def _on_pico_sensors(self, sender, payload: SensorReading):
        if payload.type == "tof":
            self.tof[payload.id] = int(payload.value)

    def _on_stop(self, sender, **kwargs):
        self.is_active = False
        self._coast_to_stop()

    def _on_seek(self, sender, payload: bool):
        self.activate(bool(payload))

    def _on_seek_target(self, sender, payload: str):
        self.set_target(payload)

    # ---- control surface (driven via Topics.seek / Topics.seek_target) --

    def set_target(self, label: str):
        self.target_label = label
        self._reset_tracking()
        self.logger.info(f"ObjectSeeker target set to '{label}'")

    def activate(self, on: bool):
        self.is_active = on
        self.logger.info(f"ObjectSeeker is_active: {self.is_active}")
        if not on:
            self._coast_to_stop()

    # ---- helpers --------------------------------------------------------

    def _reset_tracking(self):
        """Forget the current lock and smoothing state (fresh re-acquisition)."""
        self.servo.reset()
        self._lock_cx = None
        self._lock_cy = None
        self._miss = 0

    def _tof_scale(self) -> float:
        """Graduated forward-speed factor in [0,1] from the nearest ToF reading."""
        stop = settings.SEEK_TOF_STOP_MM
        slow = settings.SEEK_TOF_SLOW_MM
        mm = min(self.tof.get(0, 9999), self.tof.get(1, 9999))
        if mm <= stop:
            return 0.0
        if mm >= slow:
            return 1.0
        return (mm - stop) / max(slow - stop, 1)

    def _best_target(self):
        if self.latest is None:
            return None
        matches = [
            d for d in self.latest.detections
            if d.label == self.target_label
            and d.confidence >= settings.SEEK_MIN_CONFIDENCE
        ]
        if not matches:
            return None
        # Stickiness: prefer the match closest to the current lock so we don't
        # ping-pong between two same-class objects. Only switch when the nearest
        # match has drifted beyond lock_max_center_dist (lock genuinely lost).
        if self._lock_cx is not None:
            def dist(d):
                return ((d.cx - self._lock_cx) ** 2 + (d.cy - self._lock_cy) ** 2) ** 0.5
            nearest = min(matches, key=dist)
            if dist(nearest) <= settings.SEEK_LOCK_DIST:
                return nearest
        # No lock yet (or lock lost): acquire the most prominent (largest) target.
        return max(matches, key=lambda d: d.area)

    def _dt(self) -> float:
        now = time.monotonic()
        prev = self._last_spin
        self._last_spin = now
        if prev is None:
            return 1.0 / max(self.frequency, 1)
        return min(max(now - prev, 1e-3), 0.5)

    def _emit(self, vx: float, vy: float, wz: float):
        """Slew-limit toward (vx,vy,wz), remember it, and publish as cmd_vel."""
        vx, vy, wz = self.smoother.smooth(
            vx, vy, wz, self._dt(),
            settings.SEEK_SLEW_LINEAR, settings.SEEK_SLEW_ANGULAR,
        )
        self._driving = True
        Topics.cmd_vel.send(
            "seek",
            payload=Twist(linear=Vector3(vx, vy, 0.0), angular=Vector3(0.0, 0.0, wz)),
        )

    def _coast_to_stop(self):
        if self._driving:
            self._driving = False
            Topics.cmd_vel.send(
                "seek", payload=Twist(linear=Vector3(0, 0, 0), angular=Vector3(0, 0, 0))
            )
        self.smoother.reset()
        self._reset_tracking()

    # ---- main loop ------------------------------------------------------

    def _log_throttled(self, msg):
        # spinner runs at 8 Hz; log ~1/sec so the reason for (not) driving is
        # visible without flooding the console.
        self._log_ctr = getattr(self, "_log_ctr", 0) + 1
        if self._log_ctr % 8 == 1:
            self.logger.info(msg)

    def spinner(self):
        if not self.is_active:
            return

        # Watchdog: if detections have gone stale (detector/camera stalled),
        # stop rather than steering toward a frozen box.
        now = time.monotonic()
        if self._last_rx is None or (now - self._last_rx) > settings.SEEK_LOST_TIMEOUT:
            self._log_throttled("seek: detections stale -> stop")
            self._coast_to_stop()
            return

        target = self._best_target()
        if target is None:
            # Coast through brief dropouts: keep easing the last command down for
            # a few frames instead of slamming to a stop on a single missed frame.
            self._miss += 1
            if self._driving and self._miss <= settings.SEEK_COAST_FRAMES:
                lvx, lvy, lwz = self.smoother.last
                self._emit(lvx * 0.7, lvy * 0.7, lwz * 0.7)
                return
            n = len(self.latest.detections) if self.latest else 0
            labels = sorted({d.label for d in self.latest.detections}) if self.latest else []
            self._log_throttled(
                f"seek[{self.target_label}]: NO TARGET — {n} detections in view: {labels}"
            )
            self._coast_to_stop()
            return

        self._miss = 0
        self._lock_cx, self._lock_cy = target.cx, target.cy

        # Shared visual-servo law: EMA + deadband + strafe/yaw/forward mapping.
        vx, vy, wz = self.servo.compute(
            target.cx, target.cy,
            linear=settings.SEEK_LINEAR,
            angular=settings.SEEK_ANGULAR,
            strafe=settings.SEEK_STRAFE,
            deadband_width=settings.SEEK_DEADBAND,
            ema_alpha=settings.SEEK_EMA_ALPHA,
            yaw_crossover=settings.SEEK_YAW_CROSSOVER,
        )

        # Graduated ToF slowdown (never adds speed).
        veto_scale = self._tof_scale() if self.use_tof_safety else 1.0
        vx *= veto_scale

        self._log_throttled(
            f"seek[{self.target_label}]: cx={target.cx:.2f} cy={target.cy:.2f} "
            f"-> vx={vx:.3f} vy={vy:.3f} wz={wz:.3f} "
            f"tof_scale={veto_scale:.2f} tof={self.tof}"
        )

        self._emit(vx, vy, wz)

    def shutdown(self):
        self.is_active = False
        self._coast_to_stop()
