import torch
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel
import dataclasses

print("Qwen3TTSModel Attributes:")
for attr in dir(Qwen3TTSModel):
    if not attr.startswith("__"):
        print(f" - {attr}")
