import os
from felix.settings import settings
from felix.motion.joystick import JoystickNonLinearDampener
from felix.vision.image import ImageUtils
from lib.nodes import BaseNode
import time
from felix.vision.image_collector import ImageCollector
from felix.signals import Topics

class Robot(BaseNode):
    def __init__(self, **kwargs):
        super(Robot, self).__init__(**kwargs)

        # initialize objects
        self.session_id = str(int(time.time()))

        self.drive_data_path = os.path.join(
            settings.TRAINING.driving_data_path, self.session_id
        )

        self.dampener = JoystickNonLinearDampener(0.25)

        self.image = None
        self.cmd_zero = True
        self._image_collector = ImageCollector()

        Topics.raw_image.connect(self.handle_raw_image)

        self.last_capture_time = time.time()

        self.loaded()

    def handle_raw_image(self, sender, payload):
        self.image = ImageUtils.bgr8_to_jpeg(payload)

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
            try:
                image = self.get_image()
                if image is not None:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + image + b"\r\n"
                    )
            except Exception:
                pass
