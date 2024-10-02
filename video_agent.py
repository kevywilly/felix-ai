#!/usr/bin/env python3
import logging

from nano_llm import Agent

from nano_llm.plugins import VideoSource, VideoOutput
from nano_llm.utils import ArgParser
from jetson.utils import cudaToNumpy, cudaConvertColor, cudaDeviceSynchronize, cudaAllocMapped
from felix.signals import sig_raw_image
import cv2

class VideoStream(Agent):
    """
    Relay, view, or test a video stream.  Use the ``--video-input`` and ``--video-output`` arguments
    to set the video source and output protocols used from `jetson_utils <https://github.com/dusty-nv/jetson-inference/blob/master/docs/aux-streaming.md>`_
    like V4L2, CSI, RTP/RTSP, WebRTC, or static video files.

    For example, this will capture a V4L2 camera and serve it via WebRTC with H.264 encoding:
    
    .. code-block:: text
    
        python3 -m nano_llm.agents.video_stream \ 
           --video-input /dev/video0 \ 
           --video-output webrtc://@:8554/output
    
    It's also used as a basic test of video streaming before using more complex agents that rely on it.
    """
    def __init__(self, video_input=None, video_output=None, **kwargs):
        """
        Args:
          video_input (Plugin|str): the VideoSource plugin instance, or URL of the video stream or camera device.
          video_output (Plugin|str): the VideoOutput plugin instance, or output stream URL / device ID.
        """
        super().__init__()

        self.image_tensor = None
        self.image = None

        self.video_source = VideoSource(video_input, 
        video_input_width=640, 
        video_input_height=320, 
        video_input_framerate=30, **kwargs
        )
        self.video_output = VideoOutput(video_output, **kwargs)
        
        self.video_source.add(self.on_video, threaded=True)
        self.video_source.add(self.video_output)
        
        self.pipeline = [self.video_source]
        
    def on_video(self, image):
        # print(f"captured {image.width}x{image.height} frame from {self.video_source.resource}")
        
        if image:
            self.image_tensor = image

            self._convert_image(image)


    def _convert_image(self, rgb_img):        
        cv_image = cudaToNumpy(rgb_img)

        self.image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGR)
    
        sig_raw_image.send(self, payload=self.image)

         
if __name__ == "__main__":
    parser = ArgParser(extras=['video_input', 'video_output', 'log'])
    args = parser.parse_args()
    print(args)
    
    args = {
        'video_input': 'csi://0', 
        'video_output': 'webrtc://@:8554/output', 
        'log_level': "info"
    }
    
    #agent = VideoStream(**args).run()
  
    agent = VideoStream(**vars(args)).run() 
