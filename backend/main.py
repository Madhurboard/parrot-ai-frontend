"""
Parrot AI — FastAPI Backend (SaaS Edition)
==========================================
Connects a React/Next.js frontend to Qwen3-TTS models.
All persistence flows through Supabase (Postgres + Storage).

Run locally:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

import io
import json
import time
import uuid
# Reloading to pick up qwen_engine changes...
# Force reload 2 - Picking up corrected ref_audio parameter...
# Force reload 6 - Picking up mode consistency fix in qwen_engine.py...
import os
import re
import gc
import asyncio
import base64
import tempfile
import threading
from typing import AsyncGenerator, Optional, List, Tuple, Dict, Any

import torch
import numpy as np
import librosa
import soundfile as sf
import whisper

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from . import qwen_engine as engine_wrapper
from qwen_tts.inference.qwen3_tts_model import VoiceClonePromptItem

from .config import (
    MODEL_MAP, DEVICE, DTYPE, FRONTEND_URLS, CLOUD_SPACE_ID,
    VOICE_AUDIO_BUCKET, VOICE_EMBEDDING_BUCKET, CACHE_DIR,
)
from .auth import get_current_user
from .supabase_client import (
    insert_voice, list_voices, get_voice, delete_voice_record,
    update_voice_embedding,
    upload_to_storage, download_from_storage, delete_from_storage,
    download_to_cache,
)

# ============================================================================
# Model Manager (Hybrid Local/Cloud Orchestrator)
# ============================================================================

class ModelManager:
    _instance = None

    def __init__(self):
        # Cache for loaded models: {model_type: model_instance}
        self.model_cache: Dict[str, engine_wrapper.Qwen3TTSModel] = {}
        self.model_type: Optional[str] = None
        self.is_loading: bool = False
        self.use_cloud: bool = False 
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self, model_type: str) -> None:
        """Load model into cache if not present, then set as active. Thread-safe."""
        with self._lock:
            if self.model_type == model_type and model_type in self.model_cache:
                return

            if model_type not in MODEL_MAP:
                raise ValueError(f"Unknown model type: {model_type}")

            self.is_loading = True
            self.use_cloud = False
            
            # Check if already cached
            if model_type in self.model_cache:
                print(f"[ModelManager] Switching to cached model: {model_type}")
                self.model_type = model_type
                self.is_loading = False
                return

            print(f"[ModelManager] Loading NEW engine: {model_type}...")
            try:
                # If we have too many models, clear the oldest one to save VRAM
                if len(self.model_cache) >= 2:
                    oldest = next(iter(self.model_cache))
                    print(f"[ModelManager] VRAM management: Unloading {oldest}")
                    del self.model_cache[oldest]
                    gc.collect()
                    torch.cuda.empty_cache()

                new_model = engine_wrapper.Qwen3TTSModel.from_pretrained(
                    MODEL_MAP[model_type],
                    device="cuda",
                    dtype=DTYPE,
                )
                self.model_cache[model_type] = new_model
                self.model_type = model_type
                print(f"[ModelManager] {model_type} active on {DEVICE}.")
            except Exception as e:
                self.is_loading = False
                raise RuntimeError(f"Model load failed: {e}")
            finally:
                self.is_loading = False

    def get_engine(self):
        """Returns the active engine from cache."""
        if self.model_type not in self.model_cache:
            self.load_model(self.model_type or "base")
        
        if self.use_cloud:
            raise RuntimeError("Cloud model is not implemented.")
        return self.model_cache[self.model_type]

    def get_model(self):
        return self.get_engine()

# Initialise singleton
manager = ModelManager.get_instance()


# ============================================================================
# Whisper (Lazy Loading)
# ============================================================================

_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print("[SYSTEM] Initializing transcription engine (Whisper)...")
        _whisper_model = whisper.load_model("base", device=DEVICE)
        print("[OK] Transcription engine ready.")
    return _whisper_model


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Parrot AI — Voice Cloning API",
    description="SaaS backend for voice cloning powered by Qwen3-TTS",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helpers
# ============================================================================

async def _load_audio_bytes(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Load audio bytes using a temp file for robust format detection (WebM/OGG/WAV)."""
    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(None, lambda: whisper.load_audio(tmp_path))
        return audio.astype(np.float32), 16000
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Flatten, normalize to -1dB peak, and clamp to [-1, 1]."""
    audio = audio.flatten()
    max_val = np.abs(audio).max()
    if max_val > 0:
        audio = audio * (0.9 / max_val)
    audio = np.clip(audio, -1.0, 1.0)
    print(f"[Audio Monitor] Peak: {max_val:.4f} -> Normalized to 0.9")
    return audio.astype(np.float32)


async def _create_voice_profile(
    model: Any,
    audio_bytes: bytes,
    transcript: Optional[str] = None,
) -> Any:
    """Unified helper to create a voice profile from audio bytes."""
    # We pass the raw bytes to the engine so it can handle temp file creation internally
    if transcript and transcript.strip():
        return model.create_voice_clone_prompt(
            audio_content=audio_bytes, transcript=transcript.strip()
        )
    else:
        return model.create_voice_clone_prompt(
            audio_content=audio_bytes, x_vector_only_mode=True
        )


def smart_split_text(text: str, max_chars: int = 500) -> List[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current_chunk = ""
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chars:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

            while len(current_chunk) > max_chars:
                split_point = current_chunk.rfind(',', 0, max_chars)
                if split_point == -1:
                    split_point = current_chunk.rfind(' ', 0, max_chars)
                if split_point != -1:
                    chunks.append(current_chunk[:split_point + 1].strip())
                    current_chunk = current_chunk[split_point + 1:]
                else:
                    chunks.append(current_chunk[:max_chars].strip())
                    current_chunk = current_chunk[max_chars:]

    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


# ============================================================================
# Public Endpoints (no auth)
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Parrot AI — Voice Cloning API",
        "status": "running",
        "device": DEVICE,
        "version": "2.0.0",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "cuda_available": torch.cuda.is_available()}


# ============================================================================
# Transcription
# ============================================================================

@app.post("/api/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    _user_id: str = Depends(get_current_user),
):
    try:
        audio_bytes = await audio_file.read()
        ext = os.path.splitext(audio_file.filename or ".wav")[1] or ".wav"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            result = whisper_model.transcribe(
                tmp_path,
                language="en",
                fp16=(DEVICE != "cpu"),
            )
            text = result["text"].strip()
            return {"text": text, "language": result.get("language", "en")}
        finally:
            os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Voice Management
# ============================================================================

@app.get("/api/voices")
async def api_list_voices(user_id: str = Depends(get_current_user)):
    try:
        voices = list_voices(user_id)
        return voices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voices")
async def api_save_voice(
    name: str = Form(...),
    transcript: str = Form(""),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    try:
        voice_id = str(uuid.uuid4())
        file_content = await file.read()

        # 1. Upload audio to Supabase Storage
        audio_remote = f"{user_id}/{voice_id}.wav"
        upload_to_storage(
            VOICE_AUDIO_BUCKET, audio_remote, file_content, "audio/wav"
        )

        # 2. Generate embedding
        voice_prompt = await _create_voice_profile(
            manager.get_engine(), file_content, transcript or None
        )

        # 3. Serialise embedding and upload
        emb_buffer = io.BytesIO()
        torch.save(voice_prompt, emb_buffer)
        emb_buffer.seek(0)
        emb_remote = f"{user_id}/{voice_id}.pt"
        upload_to_storage(
            VOICE_EMBEDDING_BUCKET,
            emb_remote,
            emb_buffer.read(),
        )

        # 4. Insert DB row
        insert_voice(
            user_id=user_id,
            voice_id=voice_id,
            name=name,
            transcript=transcript,
            audio_path=audio_remote,
            embedding_path=emb_remote,
        )

        return {"id": voice_id, "message": "Voice profile saved successfully"}
    except Exception as e:
        import traceback
        print(f"[ERROR] POST /api/voices failed: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/voices/{voice_id}")
async def api_delete_voice(
    voice_id: str,
    user_id: str = Depends(get_current_user),
):
    try:
        voice = get_voice(voice_id, user_id)
        if not voice:
            raise HTTPException(status_code=404, detail="Voice not found")

        # Remove storage objects
        if voice.get("audio_path"):
            delete_from_storage(VOICE_AUDIO_BUCKET, voice["audio_path"])
        if voice.get("embedding_path"):
            delete_from_storage(VOICE_EMBEDDING_BUCKET, voice["embedding_path"])

        # Remove DB row
        delete_voice_record(voice_id, user_id)

        return {"message": "Voice deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/voices/{voice_id}/rename")
async def api_rename_voice(
    voice_id: str,
    payload: dict,
    user_id: str = Depends(get_current_user),
):
    try:
        new_name = payload.get("name")
        if not new_name:
            raise HTTPException(status_code=400, detail="Name required")
        
        from backend.supabase_client import update_voice_name
        success = update_voice_name(voice_id, user_id, new_name)
        if not success:
            raise HTTPException(status_code=404, detail="Voice not found")
            
        return {"message": "Voice renamed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Voice Resolution Helpers
# ============================================================================

async def _resolve_voice_prompt(
    voice_id: Optional[str],
    audio_content: Optional[bytes],
    transcript: str,
    use_transcript: bool,
    user_id: str,
    return_raw: bool = False
) -> Tuple[Any, str]:
    """Load or compute a voice clone prompt."""
    print(f"[DEBUG] _resolve_voice_prompt entering with voice_id='{voice_id}' (type: {type(voice_id)})")

    if voice_id == "test-voice":
        print("[DEBUG] Bypassing UUID check for 'test-voice', will use uploaded audio if present")
        voice_id = None

    if voice_id:
        # ---- Saved voice ----
        voice = get_voice(voice_id, user_id)
        if not voice:
            raise ValueError("Voice not found")
        
        t = voice.get("transcript") or ""
        
        if return_raw:
             # Download raw audio from Supabase
             data = download_from_storage(VOICE_AUDIO_BUCKET, voice["audio_path"])
             if not data:
                 raise ValueError("Voice audio missing from storage")
             
             with io.BytesIO(data) as bio:
                 audio_array, _ = librosa.load(bio, sr=16000)
                 return audio_array, t

        # Standard path (Pre-computed embedding)
        local_path = download_to_cache(VOICE_EMBEDDING_BUCKET, voice["embedding_path"])
        if not local_path:
             raise ValueError("Voice embedding missing from storage")
        
        prompt = torch.load(local_path, map_location=DEVICE, weights_only=False)
        
        # ── PERMANENT REPAIR LOGIC ──
        # If the loaded prompt is 'dirty' (contains raw audio), we fix it once and save it back.
        is_dirty = False
        if isinstance(prompt, dict) and "audio_values" in prompt:
            is_dirty = True
        elif isinstance(prompt, VoiceClonePromptItem) and prompt.ref_spk_embedding is not None:
             # Legacy check for wrongly mapped raw audio in embedding field
             if isinstance(prompt.ref_spk_embedding, torch.Tensor) and prompt.ref_spk_embedding.numel() > 4096:
                 is_dirty = True

        if is_dirty:
            print(f"[REPAIR] Fixing legacy voice asset permanently: {voice_id}")
            try:
                # 1. Download raw audio
                raw_data = download_from_storage(VOICE_AUDIO_BUCKET, voice["audio_path"])
                if raw_data:
                    # 2. Extract clean embedding
                    clean_prompt = await _create_voice_profile(
                        manager.get_engine(), raw_data, voice.get("transcript")
                    )
                    
                    # 3. Save optimized embedding to buffer
                    emb_buffer = io.BytesIO()
                    torch.save(clean_prompt, emb_buffer)
                    emb_buffer.seek(0)
                    
                    # 4. Upload back to Supabase (Overwrite)
                    upload_to_storage(VOICE_EMBEDDING_BUCKET, voice["embedding_path"], emb_buffer.read(), upsert=True)
                    print(f"[SUCCESS] Voice {voice_id} repaired and optimized in cloud.")
                    
                    # Use the clean prompt for current generation
                    prompt = clean_prompt
            except Exception as repair_err:
                print(f"[REPAIR FAILED] Could not auto-fix asset: {repair_err}")

        return prompt, "saved voice"

    elif audio_content:
        # ---- Uploaded content ----
        t = transcript if (use_transcript and transcript.strip()) else ""
        
        if return_raw:
            audio_array, _ = librosa.load(io.BytesIO(audio_content), sr=16000)
            return audio_array, t

        print(f"[DEBUG] Creating prompt from uploaded content (Transcript info: {bool(t)})")
        prompt = manager.get_engine().create_voice_clone_prompt(
            audio_content=audio_content,
            transcript=t
        )
        return prompt, "newly computed"

    else:
        raise ValueError("No voice provided (voice_id or audio_file required)")


# ============================================================================
# Generation — Streaming (SSE)
# ============================================================================

async def _generate_sse(
    prompt_text: str,
    voice_id: Optional[str],
    audio_content: Optional[bytes],
    reference_text: str,
    use_transcript: bool,
    user_id: str,
    temperature: float = 1.0,
    top_p: float = 1.0,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
):
    def sse(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    yield sse("progress", {"stage": "init", "percent": 0, "message": "Initializing..."})

    try:
        yield sse("progress", {"stage": "analyzing", "percent": 10, "message": "Analyzing voice..."})

        engine = manager.get_engine()
        engine_type = "Cloud" if manager.use_cloud else "Local"
        
        # Resolve voice prompt ONCE
        if manager.use_cloud:
            audio_data, mode = await _resolve_voice_prompt(
                voice_id, audio_content, reference_text, use_transcript, user_id, return_raw=True
            )
            voice_prompt = None
        else:
            voice_prompt, mode = await _resolve_voice_prompt(
                voice_id, audio_content, reference_text, use_transcript, user_id, return_raw=False
            )
            audio_data = None

        yield sse("progress", {"stage": "extracted", "percent": 30, "message": f"Voice ready ({mode})"})

        yield sse("progress", {"stage": "generating", "percent": 40, "message": f"Initialising {engine_type} engine..."})

        # Prepare Temp Audio file if using Cloud
        temp_audio_path = None
        if manager.use_cloud:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                sf.write(tf.name, audio_data, 16000)
                temp_audio_path = tf.name

        text_chunks = smart_split_text(prompt_text)
        all_wavs: list = []
        output_sr = 24000
        loop = asyncio.get_event_loop()
        t0 = time.time()

        for i, chunk in enumerate(text_chunks):
            pct = 40 + int((i / len(text_chunks)) * 50)
            yield sse("progress", {"stage": "generating", "percent": pct, "message": f"Part {i+1}/{len(text_chunks)} ({engine_type})..."})

            if manager.use_cloud:
                # Cloud generation
                wavs, sr = await loop.run_in_executor(
                    None,
                    lambda c=chunk: engine.generate_voice_clone(
                        text=c,
                        audio_path=temp_audio_path,
                        ref_text=reference_text,
                        use_xvector_only=(not use_transcript)
                    )
                )
            else:
                # Local generation
                wavs, sr = await loop.run_in_executor(
                    None,
                    lambda c=chunk: engine.generate_voice_clone(
                        text=c,
                        voice_clone_prompt=voice_prompt,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        repetition_penalty=repetition_penalty,
                    ),
                )
            all_wavs.append(wavs[0])
            output_sr = sr

        if temp_audio_path:
            os.unlink(temp_audio_path)

        elapsed = time.time() - t0
        yield sse("progress", {"stage": "generated", "percent": 90, "message": f"Generated via {engine_type} in {elapsed:.1f}s"})

        yield sse("progress", {"stage": "encoding", "percent": 95, "message": "Encoding audio..."})

        combined = np.concatenate([w.flatten() for w in all_wavs])
        combined = _normalize_audio(combined)
        buf = io.BytesIO()
        sf.write(buf, combined, output_sr, format="WAV", subtype="PCM_16")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")

        yield sse("progress", {"stage": "complete", "percent": 100, "message": "Done!"})
        yield sse("complete", {"audio": b64, "format": "wav"})
        yield sse("stream-end", {"status": "complete"})

    except Exception as e:
        import traceback
        err_msg = str(e)
        print(f"[ERROR] Generation failed: {err_msg}")
        print(traceback.format_exc())
        yield sse("error", {"message": err_msg})


@app.post("/api/generate-stream")
async def generate_voice_stream(
    prompt: str = Form(...),
    use_transcript: str = Form("false"),
    reference_text: str = Form(""),
    audio_file: UploadFile = File(None),
    voice_id: str = Form(None),
    temperature: float = Form(0.8),
    top_p: float = Form(0.8),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1),
    user_id: str = Depends(get_current_user),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    audio_content = await audio_file.read() if audio_file else None

    return StreamingResponse(
        _generate_sse(
            prompt, voice_id, audio_content, reference_text,
            use_transcript.lower() == "true", user_id,
            temperature, top_p, top_k, repetition_penalty,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


# ============================================================================
# Generation — Simple (non-streaming)
# ============================================================================

@app.post("/api/generate")
async def generate_voice(
    prompt: str = Form(...),
    use_transcript: str = Form("false"),
    reference_text: str = Form(""),
    audio_file: UploadFile = File(None),
    voice_id: str = Form(None),
    user_id: str = Depends(get_current_user),
):
    try:
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        audio_content = await audio_file.read() if audio_file else None

        voice_prompt, mode = await _resolve_voice_prompt(
            voice_id, audio_content, reference_text,
            use_transcript.lower() == "true", user_id,
        )

        loop = asyncio.get_event_loop()
        wavs, output_sr = await loop.run_in_executor(
            None,
            lambda: manager.get_engine().generate_voice_clone(
                text=prompt,
                voice_clone_prompt=voice_prompt,
            )
        )

        buf = io.BytesIO()
        sf.write(buf, wavs[0], output_sr, format="WAV")
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=generated.wav"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Model Management
# ============================================================================

@app.get("/api/model/status")
async def get_model_status(_user_id: str = Depends(get_current_user)):
    return {
        "current_model": manager.model_type,
        "is_loading": manager.is_loading,
        "supported_models": MODEL_MAP,
    }


@app.post("/api/model/switch")
async def switch_model(
    target_model: str = Form(...),
    _user_id: str = Depends(get_current_user),
):
    if target_model not in MODEL_MAP:
        raise HTTPException(status_code=400, detail="Invalid model type")
    try:
        if manager.model_type != target_model:
            manager.load_model(target_model)
        return {"status": "success", "current_model": target_model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Voice Design Endpoint
# ============================================================================

@app.post("/api/generate-design")
async def generate_design(
    text: str = Form(...),
    instruct: str = Form(...),
    temperature: float = Form(0.8),
    top_p: float = Form(0.8),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1),
    _user_id: str = Depends(get_current_user),
):
    if manager.model_type != "design":
        raise HTTPException(status_code=400, detail="Switch to 'design' model first.")

    try:
        text_chunks = smart_split_text(text)
        loop = asyncio.get_event_loop()
        all_wavs = []
        output_sr = 24000

        for chunk in text_chunks:
            wavs, sr = await loop.run_in_executor(
                None,
                lambda c=chunk: manager.get_model().generate_voice_design(
                    text=c,
                    instruct=instruct,
                    language="Auto",
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                ),
            )
            all_wavs.append(wavs[0])
            output_sr = sr

        combined = np.concatenate([w.flatten() for w in all_wavs])
        combined = _normalize_audio(combined)
        buf = io.BytesIO()
        sf.write(buf, combined, output_sr, format="WAV")
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=design_generated.wav"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Preset / Custom Voice Endpoint
# ============================================================================

@app.post("/api/generate-preset")
async def generate_preset(
    text: str = Form(...),
    speaker: str = Form(...),
    temperature: float = Form(0.8),
    top_p: float = Form(0.8),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1),
    _user_id: str = Depends(get_current_user),
):
    if manager.model_type != "custom":
        raise HTTPException(status_code=400, detail="Switch to 'custom' model first.")

    try:
        text_chunks = smart_split_text(text)
        loop = asyncio.get_event_loop()
        all_wavs = []
        output_sr = 24000

        for chunk in text_chunks:
            wavs, sr = await loop.run_in_executor(
                None,
                lambda c=chunk: manager.get_model().generate_custom_voice(
                    text=c,
                    speaker=speaker,
                    language="Auto",
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                ),
            )
            all_wavs.append(wavs[0])
            output_sr = sr

        combined = np.concatenate([w.flatten() for w in all_wavs])
        combined = _normalize_audio(combined)
        buf = io.BytesIO()
        sf.write(buf, combined, output_sr, format="WAV")
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=preset_generated.wav"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dialogue Generation
# ============================================================================

class DialogueLine(BaseModel):
    text: str
    speaker: str
    type: str  # "preset" or "cloned"
    temperature: float = 0.8
    top_p: float = 0.8
    top_k: int = 50
    repetition_penalty: float = 1.1


class DialogueRequest(BaseModel):
    lines: List[DialogueLine]


@app.post("/api/generate-dialogue")
async def generate_dialogue(
    request: DialogueRequest,
    user_id: str = Depends(get_current_user),
):
    if not request.lines:
        raise HTTPException(status_code=400, detail="Script cannot be empty")

    loop = asyncio.get_event_loop()
    all_audio: list = []
    output_sr = 24000
    silence = np.zeros(int(output_sr * 0.3))
    
    # Cache resolved prompts to prevent redundant OOM-heavy repairs
    prompt_cache: Dict[str, Any] = {}

    try:
        for i, line in enumerate(request.lines):
            needed = "custom" if line.type == "preset" else "base"
            if manager.model_type != needed:
                print(f"[Dialogue] Switching engine: {manager.model_type} -> {needed}")
                await loop.run_in_executor(None, lambda: manager.load_model(needed))

            wavs = None
            
            # Use torch.inference_mode for memory efficiency
            with torch.inference_mode():
                if line.type == "preset":
                    wavs, sr = await loop.run_in_executor(
                        None,
                        lambda l=line: manager.get_model().generate_custom_voice(
                            text=l.text, speaker=l.speaker, language="Auto",
                            temperature=l.temperature, top_p=l.top_p,
                            top_k=l.top_k, repetition_penalty=l.repetition_penalty,
                        ),
                    )
                    output_sr = sr
                else:
                    # Resolve or fetch from cache
                    if line.speaker in prompt_cache:
                        voice_prompt = prompt_cache[line.speaker]
                    else:
                        print(f"[Dialogue] Resolving voice: {line.speaker}")
                        voice_prompt, _ = await _resolve_voice_prompt(
                            line.speaker, None, "", False, user_id,
                        )
                        prompt_cache[line.speaker] = voice_prompt

                    wavs, sr = await loop.run_in_executor(
                        None,
                        lambda l=line: manager.get_model().generate_voice_clone(
                            text=l.text, language="Auto",
                            voice_clone_prompt=voice_prompt,
                            temperature=l.temperature, top_p=l.top_p,
                            top_k=l.top_k, repetition_penalty=l.repetition_penalty,
                        ),
                    )
                    output_sr = sr

            if wavs is not None:
                all_audio.append(wavs[0])
                if i < len(request.lines) - 1:
                    all_audio.append(silence)
            
            # Explicitly clear VRAM after each segment
            del wavs
            gc.collect()
            torch.cuda.empty_cache()
    except Exception as e:
        print(f"[ERROR] Dialogue generation interrupted: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not all_audio:
        raise HTTPException(status_code=500, detail="No audio generated")

    combined = np.concatenate([a.flatten() for a in all_audio])
    combined = _normalize_audio(combined)
    buf = io.BytesIO()
    sf.write(buf, combined, output_sr, format="WAV")
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")


# ============================================================================
# Background Startup & Warmup
# ============================================================================

def warmup_engines():
    """Warms up the most common models in the background."""
    print("[SYSTEM] Background warmup initiated...")
    try:
        m = ModelManager.get_instance()
        m.load_model("base")
        print("[SYSTEM] Warmup complete. Synthesis engine is HOT.")
    except Exception as e:
        print(f"[SYSTEM] Warmup skipped (models will load on first use): {e}")

@app.on_event("startup")
async def startup_event():
    # Start warmup in a separate thread so FastAPI can finish starting up
    threading.Thread(target=warmup_engines, daemon=True).start()
    print("[SYSTEM] Parrot AI Studio is ONLINE.")

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 50)
    print("[Parrot AI] FastAPI Backend — SaaS Edition")
    print("=" * 50)
    print(f"Device: {DEVICE}")
    print(f"Models: {list(MODEL_MAP.keys())}")
    print("=" * 50 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
