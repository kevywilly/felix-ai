from enum import Enum
import time
from typing import Optional
import termcolor
import cv2
from cv2 import VideoCapture
from felix.settings import settings
from lib.nodes import BaseNode
from felix.signals import sig_raw_image, sig_image_tensor
from nano_llm.plugins import VideoSource
from jetson.utils import cudaMemcpy, cudaToNumpy, cudaConvertColor, cudaDeviceSynchronize, cudaAllocMapped
from nano_llm import NanoLLM, ChatHistory
from nano_llm.utils import ArgParser, load_prompts
from nano_llm.plugins import VideoSource

from jetson_utils import cudaMemcpy, cudaToNumpy

import os
from felix.settings import settings

obstacle_prompt = """
                You are a mobile robot with a camera that has take a picture of the space in front of you.
                Your goal is to drive without hitting any obstacles that are close to you.  Based on what you see in the image should you
                go forward, turn left or turn right. You should prefer to go forward unless there are obstacles in your way.
                """
# os.environ["HF_HOME"]=os.path.join(settings.TRAINING.model_root,"huggingface")
# os.environ["TRANSFORMERS_CACHE"]=os.path.join(settings.TRAINING.model_root,"huggingface")

# parse args and set some defaults
args = ArgParser(extras=ArgParser.Defaults + ['prompt', 'video_input']).parse_args()
prompts = load_prompts(args.prompt)

if not prompts:
    prompts = ["Describe the image.", "Are there people in the image?"]
    
if not args.model:
    args.model = "Efficient-Large-Model/VILA1.5-3b"

llm = NanoLLM.from_pretrained(
            args.model, 
            api=args.api,
            quantization=args.quantization, 
            max_context_len=args.max_context_len,
            vision_model=args.vision_model,
            vision_scaling=args.vision_scaling, 
        )

assert(llm.has_vision)

chat_history = ChatHistory(llm, args.chat_template, args.system_prompt)

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
        if self.flip is not None:
            cv_image = cv2.flip(cv_image, self.flip)
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

    def query_image(self, prompt: str):
        chat_history.append('user', image=self.image_tensor)
        chat_history.append('user', prompt, use_cache=True)
        embedding, _ = chat_history.embed_chat()
        # print('>>', prompt)
        reply = llm.generate(
                embedding,
                kv_cache=chat_history.kv_cache,
                max_new_tokens=args.max_new_tokens,
                min_new_tokens=args.min_new_tokens,
                do_sample=args.do_sample,
                repetition_penalty=args.repetition_penalty,
                temperature=args.temperature,
                top_p=args.top_p,
            )
        for token in reply:
            termcolor.cprint(token, 'blue', end='\n\n' if reply.eos else '', flush=True)

        print("\n")
        chat_history.reset()
        # chat_history.append('bot', reply)
        # time_elapsed = time.perf_counter() - time_begin
        # print(f"time:  {time_elapsed*1000:.2f} ms  rate:  {1.0/time_elapsed:.2f} FPS")

    def spinner(self):
        self._read_image()
        if self.image_tensor is not None:
            self.query_image("""
                             Describe the image which represents the space directly in front of you.  Do you see any obstacles?
                             """)

    def shutdown(self):
        chat_history.reset()
        self.cap.destroy()

