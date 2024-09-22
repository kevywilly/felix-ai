from nano_llm import NanoLLM

model = NanoLLM.from_pretrained(
   "Efficient-Large-Model/VILA1.5-3b",  # HuggingFace repo/model name, or path to HF model checkpoint
   api='mlc',                              # supported APIs are: mlc, awq, hf
   api_token='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',               # HuggingFace API key for authenticated models ($HUGGINGFACE_TOKEN)
   max_new_tokens=32,
   max_content_len=256
   # quantization='q4f16_ft'                 # q4f16_ft, q4f16_1, q8f16_0 for MLC, or path to AWQ weights
)

response = model.generate("Once upon a time")

for token in response:
   print(token, end='', flush=True)