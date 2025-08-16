import logging
logging.basicConfig(level=logging.ERROR)
import asyncio
import atexit
from datetime import datetime
import os
import click
from felix.settings import settings
from felix.service.base import BaseService
from nano_llm import Agent
from nano_llm.plugins import VideoSource, VideoOutput
import cv2

from jetson_utils import (
    cudaToNumpy,
)

from felix.topics import Topics
import logging


class VideoStream(Agent):
    
    def __init__(
        self,
        service: BaseService = None,
    ):

        super().__init__()

        self.image_tensor = None
        self.image = None

        self.service = service

        self.video_source = VideoSource(
            video_input="csi://0",
            video_input_width=1280,
            video_input_height=720,
            video_input_framerate=60
        )


        filename = os.path.join(
            settings.TRAINING.data_root, "videos", f"{datetime.now().timestamp()}.mp4"
        )
        filename = f"file://{filename}"


        self.video_output = VideoOutput(
            "webrtc://@:8554/output", video_output_codec="h264" , video_output_save=filename
        )

        self.video_source.add(self.on_video, threaded=False)
        self.video_source.add(self.video_output)

        self.pipeline = [self.video_source]

        atexit.register(self.shutdown)

    def on_video(self, image):
        # print(f"captured {image.width}x{image.height} frame from {self.video_source.resource}")

        if image:
            self.image_tensor = image
            self._convert_image(image)

    def _convert_image(self, rgb_img):
        cv_image = cudaToNumpy(rgb_img)
        self.image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGR)
        # Publish as binary ndarray over ZeroMQ (fast, zero-copy send)
        if self.service:
            self.service.publish_ndarray(Topics.RAW_IMAGE, self.image)

    def shutdown(self):
        self.video_output.stop()
        self.video_source.stop()

    def run(self, timeout=None):
        """
        Run the agent forever or return after the specified timeout (in seconds)
        """
        self.start()
        
        if self.save_mermaid:
            self.to_mermaid(save=self.save_mermaid)
            
        logging.info(f"{type(self).__name__} - system ready")
        self.pipeline[0].join(timeout)
        return self

class VideoService(BaseService):
    def __init__(
        self,
    ):
        super().__init__()

        self.agent = VideoStream(self)
        

    def start(self):
        """Start the service"""
        super().start()
        self.agent.run()

    def on_stop(self):
        """Handle stop event"""
        self.agent.shutdown()

async def run(frequency: int = 10):
    video_service = VideoService()
    video_service.start()
    
    await video_service.spin(frequency)

    
@click.command()
@click.option('--frequency', default=10, help='Frequency in Hz')
@click.option('--log-level', default='INFO', help='Logging level')
def cli(frequency, log_level):
    logging.basicConfig(level=getattr(logging, log_level.upper()))
    asyncio.run(run(frequency))
        
        
if __name__ == "__main__":
    cli()
