import os
from felix.bus import SimpleEventBus
from felix.service.base import BaseService
from felix.settings import settings
from felix.topics import Topics
from felix.vision.image import ImageUtils
import time
from felix.vision.image_collector import ImageCollector
import numpy as np

class RobotService(BaseService):
    def __init__(self, event_bus: SimpleEventBus):
        super().__init__(event_bus)

        # initialize objects
        self.session_id = str(int(time.time()))

        self.drive_data_path = os.path.join(
            settings.TRAINING.driving_data_path, self.session_id
        )

        self.image = None
        self.cmd_zero = True
        self._image_collector = ImageCollector()

        self.subscribe_to_topic(Topics.RAW_IMAGE, self.handle_raw_image)

        self.last_capture_time = time.time()


    def handle_raw_image(self, sender, payload: dict):
        self.image = ImageUtils.bgr8_to_jpeg(np.array(payload.get("message"), dtype=np.uint8))

    def save_tag(self, tag):
        saved = self._image_collector.save_tag(self.get_image(), tag)
        return saved

    def get_tags(self):
        return self._image_collector.get_tags()

    def create_snapshot(self, folder, label):
        return self._image_collector.create_snapshot(self.get_image(), folder, label)

    def get_snapshots(self, folder):
        return self._image_collector.get_snapshots(folder)

    def _motion_changed(self, changed):
        self.logger.info("motion")
        if changed.new != changed.old:
            self.logger.info(changed.new)

    def get_image(self):
        return self.image

    def get_stream(self):
        while True:
            # ret, buffer = cv2.imencode('.jpg', frame)
            try:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + self.get_image() + b"\r\n"
                )  # concat frame one by one and show result
            except Exception:
                pass
