# Try to just see the keys in a real prompt item
import torch
import numpy as np
from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel, VoiceClonePromptItem
import tempfile
import os

# Create a dummy model or just check the fields
from dataclasses import fields
print("VoiceClonePromptItem fields:", [f.name for f in fields(VoiceClonePromptItem)])

# Try to mock the prompt creation and see what comes out
# We can't really mock it without the model, but we can check if there's an extractor
print("Has speaker_encoder:", hasattr(Qwen3TTSModel, 'speaker_encoder') or hasattr(Qwen3TTSModel, 'model') and hasattr(Qwen3TTSModel.model, 'speaker_encoder'))
