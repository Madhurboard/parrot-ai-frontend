"""
Download Qwen3-TTS models from Hugging Face Hub
"""

import os
from huggingface_hub import snapshot_download

# Models to download
MODELS = {
    "base": "Qwen/Qwen3-TTS-1.7B-Base",
    "design": "Qwen/Qwen3-TTS-1.7B-VoiceDesign",
    "custom": "Qwen/Qwen3-TTS-1.7B-CustomVoice",
}

CACHE_DIR = "backend/model_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

print("🤖 Starting model download from Hugging Face Hub...")
print(f"Cache directory: {CACHE_DIR}\n")

for model_type, repo_id in MODELS.items():
    local_path = os.path.join(CACHE_DIR, f"Qwen3-TTS-1.7B-{model_type.capitalize()}" if model_type != "base" else os.path.join(CACHE_DIR, "Qwen3-TTS-1.7B-Base"))
    
    print(f"⏳ Downloading {model_type} model: {repo_id}")
    print(f"   Path: {local_path}")
    
    try:
        snapshot_download(
            repo_id,
            cache_dir=CACHE_DIR,
            repo_type="model",
            local_dir=local_path,
        )
        print(f"✅ {model_type} model downloaded successfully\n")
    except Exception as e:
        print(f"❌ Failed to download {model_type} model: {e}\n")

print("🎉 Model download complete!")
