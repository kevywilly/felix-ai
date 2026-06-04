from lib.nodes.base import BaseNode
from lib.interfaces import Twist, SensorReading, DetectionFrame
from felix.settings import settings
from felix.signals import Topics


class ObjectSeeker(BaseNode):
    """
    Object-seeking behavior. Subscribes to Topics.detections, locks onto the
    largest box matching ``target_label`` (largest area ~= closest/most
    prominent), and steers toward it via Topics.cmd_vel.

    Steering mirrors the convention in controller.NavRequest.target:
        x_rel = 2*cx - 1   ( + => target is to the right )
        y_rel = 1 - cy     ( 1 => target high in frame / far away )
        linear.x  =  y_rel  * autodrive_linear
        angular.z = -x_rel  * autodrive_angular
    so it inherits the same (already-correct) turn direction as click-to-navigate,
    just scaled by the autodrive gains for a safe seek speed.

    Safety: an optional ToF veto zeroes forward velocity when an obstacle is
    close, so the robot will rotate to keep the target centered but won't drive
    into something. It never *adds* motion — when there is no target it commands
    a single stop.
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

        Topics.detections.connect(self._on_detections)
        Topics.pico_sensors.connect(self._on_pico_sensors)
        Topics.stop.connect(self._on_stop)

        self.loaded()

    # ---- signal handlers ------------------------------------------------

    def _on_detections(self, sender, payload: DetectionFrame):
        self.latest = payload

    def _on_pico_sensors(self, sender, payload: SensorReading):
        if payload.type == "tof":
            self.tof[payload.id] = int(payload.value)

    def _on_stop(self, sender, **kwargs):
        self.is_active = False
        self._driving = False

    # ---- control surface (called directly by the UI) -------------------

    def set_target(self, label: str):
        self.target_label = label
        self.logger.info(f"ObjectSeeker target set to '{label}'")

    def activate(self, on: bool):
        self.is_active = on
        self.logger.info(f"ObjectSeeker is_active: {self.is_active}")
        if not on:
            self._coast_to_stop()

    # ---- helpers --------------------------------------------------------

    @property
    def _obstacle_ahead(self) -> bool:
        threshold = settings.TOF_THRESHOLD
        left = self.tof.get(0, 9999)
        right = self.tof.get(1, 9999)
        return left < threshold or right < threshold

    def _best_target(self):
        if self.latest is None:
            return None
        matches = [d for d in self.latest.detections if d.label == self.target_label]
        if not matches:
            return None
        return max(matches, key=lambda d: d.area)

    def _coast_to_stop(self):
        if self._driving:
            self._driving = False
            Topics.cmd_vel.send("seek", payload=Twist())

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

        target = self._best_target()
        if target is None:
            n = len(self.latest.detections) if self.latest else 0
            labels = sorted({d.label for d in self.latest.detections}) if self.latest else []
            self._log_throttled(
                f"seek[{self.target_label}]: NO TARGET — {n} detections in view: {labels}"
            )
            self._coast_to_stop()
            return

        x_rel = 2.0 * target.cx - 1.0
        y_rel = 1.0 - target.cy

        twist = Twist()
        twist.angular.z = -x_rel * settings.autodrive_angular

        veto = self.use_tof_safety and self._obstacle_ahead
        if veto:
            twist.linear.x = 0.0  # keep target centered, but don't advance
        else:
            twist.linear.x = y_rel * settings.autodrive_linear

        self._log_throttled(
            f"seek[{self.target_label}]: target cx={target.cx:.2f} cy={target.cy:.2f} "
            f"-> linear={twist.linear.x:.3f} angular={twist.angular.z:.3f} "
            f"tof_veto={veto} tof={self.tof}"
        )

        self._driving = True
        Topics.cmd_vel.send("seek", payload=twist)

    def shutdown(self):
        self.is_active = False
        self._coast_to_stop()
