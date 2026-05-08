"""
Parrot AI — Centralized Configuration
All secrets and tunables are loaded from environment variables.
"""

import os
import torch
from dotenv import load_dotenv

# Force load the .env file from the root
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ============================================================================
# Supabase
# ============================================================================
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")

# ============================================================================
# CORS — allowed frontend origins (comma-separated)
# ============================================================================
FRONTEND_URLS: list[str] = [
    u.strip()
    for u in os.environ.get(
        "FRONTEND_URLS", "http://localhost:3000,http://127.0.0.1:3000,https://parrotai.madhur.me"
    ).split(",")
]

# ============================================================================
# Model
# ============================================================================
MODEL_MAP: dict[str, str] = {
    "base": "backend/model_cache/Qwen3-TTS-1.7B-Base",
    "design": "backend/model_cache/Qwen3-TTS-1.7B-VoiceDesign",
    "custom": "backend/model_cache/Qwen3-TTS-1.7B-CustomVoice",
}

CLOUD_SPACE_ID = "Qwen/Qwen3-TTS"

DEVICE: str = "cuda:0" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

# ============================================================================
# Storage
# ============================================================================
VOICE_AUDIO_BUCKET: str = "voices-audio"
VOICE_EMBEDDING_BUCKET: str = "voices-embeddings"
GENERATED_AUDIO_BUCKET: str = "generated-audio"

# Local cache dir (for downloaded embeddings during inference)
CACHE_DIR: str = os.environ.get("CACHE_DIR", os.path.join(os.getcwd(), ".cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
