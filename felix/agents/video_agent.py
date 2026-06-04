import os
import logging
from datetime import datetime

import cv2
from jetson_utils import videoSource, videoOutput, cudaToNumpy

from felix.settings import settings
from felix.signals import Topics


class VideoStream:
    """
    CSI camera -> WebRTC (port 8554) + mp4 recording, and publishes each frame
    as a BGR numpy array on ``Topics.raw_image`` for the rest of the system
    (autodrive classifier, object detector, snapshot collector).

    Uses ``jetson_utils`` directly (videoSource/videoOutput) rather than the
    nano_llm plugin wrappers, so the runtime no longer depends on the nano_llm
    LLM stack. The base image only needs jetson-inference.
    """

    def __init__(
        self,
        video_input: str = "csi://0",
        video_output: str = "webrtc://@:8554/output",
        video_output_width: int = 960,
        video_output_height: int = 540,
        video_input_width: int = 1280,
        video_input_height: int = 720,
        video_input_framerate: int = 60,
    ):
        videos_dir = os.path.join(settings.TRAINING.data_root, "videos")
        os.makedirs(videos_dir, exist_ok=True)
        save_path = os.path.join(videos_dir, f"{datetime.now().timestamp()}.mp4")

        self.source = videoSource(
            video_input,
            options={
                "width": video_input_width,
                "height": video_input_height,
                "framerate": video_input_framerate,
            },
        )

        self.output = videoOutput(
            video_output,
            options={
                "codec": "h264",
                "save": f"file://{save_path}",
                "width": video_output_width,
                "height": video_output_height,
            },
        )

        self._running = False

    def _publish(self, cuda_img):
        cv_image = cudaToNumpy(cuda_img)
        Topics.raw_image.send(self, payload=cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGR))

    def run(self, timeout=None):
        """Capture/render loop. Runs until the source or output stops streaming."""
        self._running = True
        logging.info(f"{type(self).__name__} - system ready")

        while self._running:
            # capture timeout is in milliseconds; None blocks until a frame
            cuda_img = self.source.Capture(timeout=1000)

            if cuda_img is None:  # timeout / transient, keep going
                continue

            self.output.Render(cuda_img)
            self._publish(cuda_img)

            if not self.source.IsStreaming() or not self.output.IsStreaming():
                break

        return self

    def shutdown(self):
        self._running = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    VideoStream().run()
