import os
import time

from lib.nodes.base import BaseNode
from lib.interfaces import Detection, DetectionFrame
from felix.settings import settings
from felix.signals import Topics

# Ultralytics is only present in the runtime container. Import defensively so the
# module can still be imported (e.g. in tests on the host) without it installed.
try:
    from ultralytics import YOLO
except Exception as ex:  # noqa: BLE001
    YOLO = None
    _IMPORT_ERROR = ex
else:
    _IMPORT_ERROR = None


def _default_model_file() -> str:
    """
    Prefer a prebuilt TensorRT engine, fall back to the .pt weights.

    Export the engine once on-device with:
        yolo export model=yolov8n.pt format=engine half=True device=0
    and drop the result next to the other checkpoints under model_root.
    """
    root = settings.TRAINING.model_root
    engine = os.path.join(root, "yolov8n.engine")
    weights = os.path.join(root, "yolov8n.pt")
    return engine if os.path.isfile(engine) else weights


class Detector(BaseNode):
    """
    Object detector. Subscribes to raw_image, runs YOLO at its own (slower than
    capture) frequency, and publishes a DetectionFrame on Topics.detections.

    This node only *perceives*. It never issues cmd_vel — downstream consumers
    (the UI overlay, an object-seek behavior) decide what to do with the boxes.
    """

    def __init__(
        self,
        model_file: str | None = None,
        conf: float = 0.4,
        classes: list[int] | None = None,
        **kwargs,
    ):
        super(Detector, self).__init__(**kwargs)

        self.model_file = model_file or _default_model_file()
        self.conf = conf
        self.classes = classes  # restrict to COCO class ids, or None for all
        self.raw_image = None
        self.model = None
        self.model_loaded = False

        Topics.raw_image.connect(self._on_raw_image)

        if YOLO is None:
            self.logger.warning(
                f"ultralytics not importable, Detector disabled: {_IMPORT_ERROR}"
            )
        elif not os.path.isfile(self.model_file):
            self.logger.warning(
                f"Detector model '{self.model_file}' not found, detector disabled. "
                "Export a TensorRT engine on-device (see _default_model_file)."
            )
        else:
            self.model = YOLO(self.model_file, task="detect")
            self.model_loaded = True
            self.logger.info(f"Detector loaded model: {self.model_file}")

        self.loaded()

    def _on_raw_image(self, sender, payload):
        self.raw_image = payload

    def spinner(self):
        if not self.model_loaded or self.raw_image is None:
            return

        frame = self.raw_image
        h, w = frame.shape[:2]

        try:
            results = self.model.predict(
                frame,
                conf=self.conf,
                classes=self.classes,
                verbose=False,
            )
        except Exception as ex:  # noqa: BLE001
            self.logger.warning(f"Detector inference error: {ex}")
            return

        detections: list[Detection] = []
        if results:
            r = results[0]
            names = r.names
            # xyxyn = box corners normalized to [0,1] — resolution-independent,
            # so the UI overlay and any seek behavior don't care about frame size.
            for box, cls, conf in zip(r.boxes.xyxyn, r.boxes.cls, r.boxes.conf):
                x1, y1, x2, y2 = (float(v) for v in box)
                detections.append(
                    Detection(
                        label=names[int(cls)],
                        confidence=float(conf),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )

        Topics.detections.send(
            "detector",
            payload=DetectionFrame(
                detections=detections, width=w, height=h, ts=int(time.time())
            ),
        )

    def shutdown(self):
        self.raw_image = None
