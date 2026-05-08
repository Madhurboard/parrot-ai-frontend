"""
Download Qwen3-TTS models from ModelScope
Alternative download source if HuggingFace Hub is unavailable
"""

import os
from modelscope import snapshot_download

# Models to download - using ModelScope IDs
MODELS = {
    "base": "Qwen/Qwen3-TTS-1.7B-Base",
    "design": "Qwen/Qwen3-TTS-1.7B-VoiceDesign", 
    "custom": "Qwen/Qwen3-TTS-1.7B-CustomVoice",
}

CACHE_DIR = "backend/model_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

print("🤖 Starting model download from ModelScope...")
print(f"Cache directory: {CACHE_DIR}\n")

for model_type, model_id in MODELS.items():
    local_path = os.path.join(CACHE_DIR, f"Qwen3-TTS-1.7B-{model_type.capitalize()}" if model_type != "base" else os.path.join(CACHE_DIR, "Qwen3-TTS-1.7B-Base"))
    
    print(f"⏳ Downloading {model_type} model: {model_id}")
    print(f"   Path: {local_path}")
    
    try:
        snapshot_download(
            model_id,
            cache_dir=local_path,
        )
        print(f"✅ {model_type} model downloaded successfully\n")
    except Exception as e:
        print(f"❌ Failed to download {model_type} model: {e}\n")

print("🎉 Model download complete!")
