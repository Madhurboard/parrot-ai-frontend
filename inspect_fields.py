import torch
from qwen_tts.inference.qwen3_tts_model import VoiceClonePromptItem
import dataclasses

print("VoiceClonePromptItem fields:")
for field in dataclasses.fields(VoiceClonePromptItem):
    print(f" - {field.name}: {field.type}")
