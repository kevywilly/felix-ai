import termcolor
from lib.nodes import BaseNode
from felix.signals import sig_image_tensor
from nano_llm import NanoLLM, ChatHistory
from nano_llm.utils import ArgParser, load_prompts


obstacle_prompt = """
                You are a mobile robot with a camera that has take a picture of the space in front of you.
                Your goal is to drive without hitting any obstacles that are close to you.  Based on what you see in the image should you
                go forward, turn left or turn right. You should prefer to go forward unless there are obstacles in your way.
                """
# os.environ["HF_HOME"]=os.path.join(settings.TRAINING.model_root,"huggingface")
# os.environ["TRANSFORMERS_CACHE"]=os.path.join(settings.TRAINING.model_root,"huggingface")

# parse args and set some defaults
args = ArgParser(extras=ArgParser.Defaults + ["prompt", "video_input"]).parse_args()
prompts = load_prompts(args.prompt)

if not prompts:
    prompts = ["Describe the image.", "Are there people in the image?"]

if not args.model:
    args.model = "Efficient-Large-Model/VILA1.5-3b"


class ChatNode(BaseNode):
    def __init__(self, frequency=1, **kwargs):
        super(ChatNode, self).__init__(**kwargs)

        self.llm = NanoLLM.from_pretrained(
            args.model,
            api=args.api,
            quantization=args.quantization,
            max_context_len=args.max_context_len,
            vision_model=args.vision_model,
            vision_scaling=args.vision_scaling,
        )

        assert self.llm.has_vision

        self.chat_history = ChatHistory(
            self.llm, args.chat_template, args.system_prompt
        )

        self.image_tensor = None

        sig_image_tensor.connect(self._on_image_tensor)

    def _on_image_tensor(self, sender, payload):
        self.image_tensor = payload

    def chat(self, prompt: str):
        self.chat_history.append("user", image=self.image_tensor)
        self.chat_history.append("user", prompt, use_cache=True)
        embedding, _ = self.chat_history.embed_chat()

        # print('>>', prompt)
        reply = self.llm.generate(
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
            termcolor.cprint(
                token, "green", end="\n\n" if reply.eos else "", flush=True
            )

        print("\n")

        self.chat_history.reset()
        # chat_history.append('bot', reply)
        # time_elapsed = time.perf_counter() - time_begin
        # print(f"time:  {time_elapsed*1000:.2f} ms  rate:  {1.0/time_elapsed:.2f} FPS")

    def spinner(self):
        if self.image_tensor is not None:
            self.chat(
                """
                    Describe the image which represents the space directly in front of you.  Do you see any obstacles?
                """
            )

    def shutdown(self):
        self.chat_history.reset()
