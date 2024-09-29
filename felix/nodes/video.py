from enum import Enum
from lib.nodes import BaseNode
from felix.signals import sig_raw_image, sig_image_tensor
from nano_llm.plugins import VideoSource
from jetson_utils import cudaToNumpy, cudaConvertColor, cudaDeviceSynchronize, cudaAllocMapped


class FlipMode(int, Enum):
    NONE=-1
    HORIZONTAL=0
    VERTICAL=1

class VideoNode(BaseNode):

    class FLIP_AXIS(int, Enum):
        NONE=-1
        HORIZONTAL=0
        VERTICAL=1

    def __init__(self, input: str = "csi://0", width: int = 1280, height: int = 720, framerate: int = 30, flip: FLIP_AXIS=FLIP_AXIS.NONE):
        super(VideoNode, self).__init__(frequency=framerate)
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
        bgr_img = cudaAllocMapped(width=rgb_img.width,
                          height=rgb_img.height,
						  format='bgr8')
    
        cudaConvertColor(rgb_img, bgr_img)
        cudaDeviceSynchronize()
        cv_image = cudaToNumpy(bgr_img)
        #if self.flip is not FlipMode.NONE:
        #    cv_image = cv2.flip(cv_image, self.flip)
        self.image = cv_image

        # Convert from RGBA (default from jetson.utils) to BGR format for OpenCV
        #self.image = cv2.cvtColor(img_flipped, cv2.COLOR_RGBA2BGR)

        sig_raw_image.send(self, payload=self.image)

    def _read_image(self):
        img = self.cap.capture()
        if img is None:
            return
        
        self.image_tensor = img

        sig_image_tensor.send(self, payload=self.image_tensor)

        self._convert_image(img)

    def spinner(self):
        self._read_image()

    def shutdown(self):
        self.cap.destroy()

