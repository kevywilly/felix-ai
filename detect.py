import time
import termcolor

from nano_llm import NanoLLM, ChatHistory
from nano_llm.utils import ArgParser, load_prompts
from nano_llm.plugins import VideoSource

from jetson_utils import cudaMemcpy, cudaToNumpy

import os
from felix.settings import settings

os.environ["HF_HOME"]=os.path.join(settings.TRAINING.model_root,"huggingface")
os.environ["TRANSFORMERS_CACHE"]=os.path.join(settings.TRAINING.model_root,"huggingface")

# parse args and set some defaults
args = ArgParser(extras=ArgParser.Defaults + ['prompt', 'video_input']).parse_args()
prompts = load_prompts(args.prompt)

if not prompts:
    prompts = ["Describe the image.", "Are there people in the image?"]
    
if not args.model:
    args.model = "Efficient-Large-Model/VILA1.5-3b"

if not args.video_input:
    args.video_input = "csi://0" # "/dev/video0"
    
print(args)

# load vision/language model
model = NanoLLM.from_pretrained(
    args.model, 
    api=args.api,
    quantization=args.quantization, 
    max_context_len=args.max_context_len,
    vision_model=args.vision_model,
    vision_scaling=args.vision_scaling, 
)

assert(model.has_vision)

# create the chat history
chat_history = ChatHistory(model, args.chat_template, args.system_prompt)

# open the video stream
video_source = VideoSource(**vars(args), cuda_stream=0, return_copy=False)

# apply the prompts to each frame
while True:
    img = video_source.capture()
    
    if img is None:
        continue

    chat_history.append('user', image=img)
    time_begin = time.perf_counter()
    
    for prompt in prompts:
        chat_history.append('user', prompt, use_cache=True)
        embedding, _ = chat_history.embed_chat()
        
        print('>>', prompt)
        
        reply = model.generate(
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

        chat_history.append('bot', reply)
      
    time_elapsed = time.perf_counter() - time_begin
    print(f"time:  {time_elapsed*1000:.2f} ms  rate:  {1.0/time_elapsed:.2f} FPS")
    
    chat_history.reset()
    
    if video_source.eos:
        break