import termcolor
from lib.nodes import BaseNode
from felix.signals import Topics
from nano_llm import NanoLLM, ChatHistory
from nano_llm.utils import ArgParser, load_prompts
import logging

logger = logging.getLogger("chat")

# os.environ["HF_HOME"]=os.path.join(settings.TRAINING.model_root,"huggingface")
# os.environ["TRANSFORMERS_CACHE"]=os.path.join(settings.TRAINING.model_root,"huggingface")

system_prompt = """
You are an intelligant assistant. 
You will receive an image as input. Your job is to describe the objects and specify where they are found in relation to an imagined
vertical line running through the center of the image.
"""
# parse args and set some defaults
args = ArgParser(extras=ArgParser.Defaults + ["prompt", "video_input"]).parse_args()
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

assert llm.has_vision

logger.info(f"{vars(args)}")

chat_history = ChatHistory(
    llm, args.chat_template, system_prompt
)

class ChatNode(BaseNode):
    def __init__(self, frequency=1, **kwargs):
        super(ChatNode, self).__init__(**kwargs)

        self.image_tensor = None

        Topics.image_tensor.connect(self._on_image_tensor)

    def _on_image_tensor(self, sender, payload):
        self.image_tensor = payload

    def chat(self) -> str:
        if self.image_tensor is None:
            return "No image found"
        
        chat_history.append("user", image=self.image_tensor)
        embedding, _ = chat_history.embed_chat()

        reply_parts = []

        # print('>>', prompt)
        reply = llm.generate(
            embedding,
            kv_cache=chat_history.kv_cache,
            max_new_tokens=args.max_new_tokens,
            min_new_tokens=args.min_new_tokens,
            streaming=True,
            do_sample=args.do_sample,
            repetition_penalty=args.repetition_penalty,
            temperature=args.temperature,
            top_p=args.top_p,
        )

        for token in reply:
            reply_parts.append(token if not reply.eos else "\n\n")
            termcolor.cprint(
                token, "green", end="\n\n" if reply.eos else "", flush=True
            )

        full_reply = ''.join(reply_parts)
        #for token in reply:
        #    termcolor.cprint(
        #        token, "green", end="\n\n" if reply.eos else "", flush=True
        #    )
           

        
        chat_history.append("bot", reply)

        return full_reply

        # chat_history.append('bot', reply)
        # time_elapsed = time.perf_counter() - time_begin
        # print(f"time:  {time_elapsed*1000:.2f} ms  rate:  {1.0/time_elapsed:.2f} FPS")

    def spinner(self):
        if self.image_tensor is not None:
            self.chat()

    def shutdown(self):
        chat_history.reset()
