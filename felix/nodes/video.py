from enum import Enum
from lib.nodes import BaseNode
from felix.signals import sig_raw_image, sig_image_tensor
from nano_llm.plugins import VideoSource
from jetson.utils import cudaToNumpy, cudaConvertColor, cudaDeviceSynchronize, cudaAllocMapped

import cv2

class FLIP_AXIS(int, Enum):
    NONE=-1
    HORIZONTAL=0
    VERTICAL=1


class VideoNode(BaseNode):

    def __init__(self, input: str = "csi://0", width: int = 1280, height: int = 720, framerate: int = 30, flip: FLIP_AXIS=FLIP_AXIS.NONE):
        super(VideoNode, self).__init__(frequency=framerate)

        self.logger.info("Starting Video Node")

        self.input = input
        self.width = width
        self.height = height
        self.framerate = framerate
        self.flip = flip

        self.cap = VideoSource(
            video_input=input, 
            video_input_framerate=self.framerate,
            video_input_height=height,
            video_input_width=width,
            cuda_stream=0, 
            return_copy=False,
            )
       
        
        self.image_tensor = None
        self.image = None

    
    def _convert_image(self, rgb_img):        
        cv_image = cudaToNumpy(rgb_img)

        if self.flip is not FLIP_AXIS.NONE:
            cv_image = cv2.flip(cv_image, self.flip)

        self.image = cv2.cvtColor(cv_image, cv2.COLOR_RGBA2BGR)
    
        sig_raw_image.send(self, payload=self.image)

    def _read_image(self):
        img = self.cap.capture()
        if img is None:
            return
        
        self.image_tensor = img

        sig_image_tensor.send(self, payload=img)

        self._convert_image(img)

    def spinner(self):
        self._read_image()

    def shutdown(self):
        self.cap.destroy()

