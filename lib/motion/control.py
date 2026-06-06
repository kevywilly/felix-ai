"""
Pure, dependency-free motion-control primitives shared by the driving nodes
(``ObjectSeeker``, ``AutoDriver``).

Deliberately imports nothing from torch/cv2/settings/hardware so the control
math is unit-testable off-robot. Nodes pass their own (config-sourced) gains in
per call, keeping this module configuration-agnostic.
"""


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def deadband(v: float, width: float) -> float:
    """Zero out small values so noise near setpoint doesn't drive the actuator."""
    return 0.0 if abs(v) < width else v


def ema(prev, value: float, alpha: float) -> float:
    """Exponential moving average. ``prev=None`` seeds with the first sample;
    ``alpha=1.0`` disables smoothing."""
    return value if prev is None else alpha * value + (1.0 - alpha) * prev


def slew(cur: float, target: float, max_step: float) -> float:
    """Move ``cur`` toward ``target`` by at most ``max_step``."""
    d = target - cur
    if d > max_step:
        return cur + max_step
    if d < -max_step:
        return cur - max_step
    return target


class TwistSmoother:
    """
    Slew-limits a stream of body-velocity targets ``(vx, vy, wz)`` for smooth
    acceleration/deceleration. Holds the last emitted command as state.

    Safety rule: a fully-zero target snaps to zero immediately (stops are never
    delayed by the ramp); any non-zero target is approached gradually.
    """

    def __init__(self):
        self.vx = 0.0
        self.vy = 0.0
        self.wz = 0.0

    @property
    def last(self) -> tuple[float, float, float]:
        return (self.vx, self.vy, self.wz)

    def reset(self):
        self.vx = self.vy = self.wz = 0.0

    def smooth(
        self,
        vx: float,
        vy: float,
        wz: float,
        dt: float,
        slew_linear: float,
        slew_angular: float,
    ) -> tuple[float, float, float]:
        if vx == 0.0 and vy == 0.0 and wz == 0.0:
            self.reset()
            return self.last
        self.vx = slew(self.vx, vx, slew_linear * dt)
        self.vy = slew(self.vy, vy, slew_linear * dt)
        self.wz = slew(self.wz, wz, slew_angular * dt)
        return self.last


class VisualServo:
    """
    Maps a normalized target centre ``(cx, cy)`` in ``[0,1]`` to a body twist
    ``(vx forward, vy strafe, wz yaw)`` using the click-to-navigate convention:

        x_rel = 2*cx - 1   ( + => target to the right )
        y_rel = 1 - cy     ( 1 => target high in frame / far )

    The horizontal error is EMA-smoothed and deadbanded; lateral error is then
    corrected with strafe for fine offsets (keeps the camera pointed) and yaw is
    added only once the target is past ``yaw_crossover`` (re-aim on large error).
    Forward speed is proportional to ``y_rel``. Holds EMA state across calls.
    """

    def __init__(self):
        self.x_ema = None
        self.y_ema = None

    def reset(self):
        self.x_ema = None
        self.y_ema = None

    def compute(
        self,
        cx: float,
        cy: float,
        *,
        linear: float,
        angular: float,
        strafe: float,
        deadband_width: float,
        ema_alpha: float,
        yaw_crossover: float,
    ) -> tuple[float, float, float]:
        self.x_ema = ema(self.x_ema, 2.0 * cx - 1.0, ema_alpha)
        self.y_ema = ema(self.y_ema, 1.0 - cy, ema_alpha)
        x_rel, y_rel = self.x_ema, self.y_ema

        x_cmd = deadband(x_rel, deadband_width)
        # Sign convention (REP-103, matches autodriver.py): +y = left, -y = right;
        # +wz = CCW/left turn. A target on the right (x_rel > 0) strafes right
        # (vy < 0) and yaws right (wz < 0).
        vy = -x_cmd * strafe
        wz = -x_cmd * angular if abs(x_cmd) > yaw_crossover else 0.0
        vx = y_rel * linear
        return vx, vy, wz
