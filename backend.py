"""
Parrot AI - FastAPI Backend
Connects the Next.js frontend to Qwen3-TTS model

Run with: uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
"""

import io
import json
import time
import torch
import librosa
import asyncio
import numpy as np
import soundfile as sf
import sqlite3
import uuid
import os
import shutil
from datetime import datetime
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import gc
from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem

# ============================================================================
# Configuration
# ============================================================================

MODEL_MAP = {
    "base": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "custom": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
}

DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32
VOICES_DIR = "saved_voices"
DB_PATH = "voices.db"

# Ensure voices directory exists
os.makedirs(VOICES_DIR, exist_ok=True)

# ============================================================================
# Model Manager
# ============================================================================

class ModelManager:
    _instance = None
    
    def __init__(self):
        self.model = None
        self.model_type = None
        self.is_loading = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self, model_type: str):
        """Dynamic model loading with memory management."""
        if self.model_type == model_type and self.model is not None:
             print(f"[ModelManager] {model_type} already loaded.")
             return

        if model_type not in MODEL_MAP:
            raise ValueError(f"Unknown model type: {model_type}")

        self.is_loading = True
        print(f"[ModelManager] Switching to {model_type} ({MODEL_MAP[model_type]})...")

        # 1. Unload existing model
        if self.model:
            print("[ModelManager] Unloading current model...")
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
        
        # 2. Load new model
        try:
            print(f"[ModelManager] Loading {MODEL_MAP[model_type]} on {DEVICE}...")
            self.model = Qwen3TTSModel.from_pretrained(
                MODEL_MAP[model_type],
                device_map=DEVICE,
                dtype=DTYPE
            )
            self.model_type = model_type
            print(f"[ModelManager] Successfully loaded {model_type}")
        except Exception as e:
            print(f"[ModelManager] Failed to load {model_type}: {e}")
            self.model_type = None # Reset state on failure
            raise e
        finally:
            self.is_loading = False

    def get_model(self):
        if not self.model:
            raise RuntimeError("Model is not loaded. Call load_model() first.")
        return self.model

# Initialize Model Manager (Default to Base)
manager = ModelManager.get_instance()
manager.load_model("base")

# ============================================================================
# Database Setup
# ============================================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS voices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            transcript TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# Initialize FastAPI
# ============================================================================

app = FastAPI(
    title="Parrot AI - Voice Cloning API",
    description="API for voice cloning using Qwen3-TTS",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Whisper Model for Transcription
# ============================================================================

import whisper

print("[Parrot AI] Loading Whisper model...")
whisper_model = whisper.load_model("base", device=DEVICE)
print("[OK] Whisper loaded successfully!")

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "message": "Parrot AI - Voice Cloning API",
        "status": "running",
        "device": DEVICE,
        "model": MODEL_NAME
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "cuda_available": torch.cuda.is_available()}


@app.post("/api/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Transcribe audio using OpenAI Whisper.
    """
    try:
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Save to temp file (Whisper needs a file path)
        import tempfile
        
        audio_bytes = await audio_file.read()
        
        # Get file extension
        ext = os.path.splitext(audio_file.filename)[1] or ".wav"
        
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            print(f"Transcribing audio: {audio_file.filename}")
            
            # Transcribe with Whisper
            result = whisper_model.transcribe(
                tmp_path,
                language="en",  # Can be changed to "auto" for language detection
                fp16=(DEVICE != "cpu")
            )
            
            text = result["text"].strip()
            print(f"Transcription: '{text[:50]}...'")
            
            return {"text": text, "language": result.get("language", "en")}
            
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Voice Management Endpoints
# ============================================================================

@app.get("/api/voices")
async def list_voices():
    """List all saved voices."""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM voices ORDER BY created_at DESC")
        voices = [dict(row) for row in c.fetchall()]
        conn.close()
        return voices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voices")
async def save_voice(
    name: str = Form(...),
    transcript: str = Form(""),
    file: UploadFile = File(...)
):
    """Save a voice (audio + transcript) to local storage."""
    try:
        voice_id = str(uuid.uuid4())
        filename = f"{voice_id}_{file.filename}"
        file_path = os.path.join(VOICES_DIR, filename)
        
        # Save file locally
        # Save file locally
        file_content = await file.read()
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Reset cursor for further processing
        file.file = io.BytesIO(file_content)
            
        # Save metadata to DB
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO voices (id, name, filename, transcript) VALUES (?, ?, ?, ?)",
            (voice_id, name, filename, transcript)
        )
        conn.commit()
        conn.close()
        
        if transcript:
             print(f"Creating profile for {name} with transcript...")
             ref_text = transcript
             audio_io = io.BytesIO(file.file.read()) # Read file again since cursor is at end
             file.file.seek(0)
             audio, sr = librosa.load(audio_io, sr=16000, mono=True)
             ref_audio = [(audio.astype(np.float32), 16000)]
             
             voice_prompt_items = manager.get_model().create_voice_clone_prompt(
                 ref_audio=ref_audio,
                 ref_text=ref_text
             )
        else:
             print(f"Creating x-vector profile for {name}...")
             audio_io = io.BytesIO(file.file.read())
             file.file.seek(0)
             audio, sr = librosa.load(audio_io, sr=16000, mono=True)
             ref_audio = [(audio.astype(np.float32), 16000)]
             
             voice_prompt_items = manager.get_model().create_voice_clone_prompt(
                 ref_audio=ref_audio,
                 x_vector_only_mode=True
             )
        
        # Save embedding
        embedding_filename = f"{voice_id}.pt"
        embedding_path = os.path.join(VOICES_DIR, embedding_filename)
        torch.save(voice_prompt_items, embedding_path)
        
        return {"id": voice_id, "message": "Voice profile saved successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """Delete a saved voice."""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Get filename
        c.execute("SELECT filename FROM voices WHERE id = ?", (voice_id,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            raise HTTPException(status_code=404, detail="Voice not found")
            
        filename = result["filename"]
        file_path = os.path.join(VOICES_DIR, filename)
        
        # Delete from DB
        c.execute("DELETE FROM voices WHERE id = ?", (voice_id,))
        conn.commit()
        conn.close()
        
        # Delete file
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"message": "Voice deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Generation Logic
# ============================================================================

async def get_audio_data(voice_id: Optional[str], audio_file: Optional[UploadFile], reference_text: str):
    """Helper to get audio bytes/path and transcript based on inputs."""
    
    # CASE 1: Use Saved Voice
    if voice_id:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT filename, transcript FROM voices WHERE id = ?", (voice_id,))
        result = c.fetchone()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Voice ID not found")
            
        filename = result["filename"]
        stored_transcript = result["transcript"]
        file_path = os.path.join(VOICES_DIR, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Voice file missing on server")
            
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
            
        # Use stored transcript if available
        final_transcript = stored_transcript if stored_transcript else reference_text
        return audio_bytes, final_transcript, True # True = use transcript if available

    # CASE 2: Uploaded File
    if not audio_file:
         raise HTTPException(status_code=400, detail="Either voice_id or audio_file is required")
         
    audio_bytes = await audio_file.read()
    return audio_bytes, reference_text, bool(reference_text)


async def _load_audio_for_prompt(audio_bytes: bytes) -> list:
    """Helper to load audio bytes into format expected by create_voice_clone_prompt."""
    audio_io = io.BytesIO(audio_bytes)
    # Run librosa in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    audio, sr = await loop.run_in_executor(None, lambda: librosa.load(audio_io, sr=16000, mono=True))
    return [(audio.astype(np.float32), 16000)]


async def generate_with_progress(
    prompt: str,
    voice_id: Optional[str],
    audio_file: Optional[UploadFile],
    reference_text: str,
    use_transcript_flag: bool # Explicit flag from frontend checkbox
) -> AsyncGenerator[str, None]:
    """Generator that yields SSE progress events during voice generation."""
    
    def send_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    try:
        # Load audio data (from DB or Upload)
        yield send_event("progress", {"stage": "loading", "percent": 5, "message": "Loading voice data..."})
        await asyncio.sleep(0.1)
        
        # Helper to resolve input source
        if voice_id:
             # Look for pre-computed embedding
             embedding_path = os.path.join(VOICES_DIR, f"{voice_id}.pt")
             
             if os.path.exists(embedding_path):
                 yield send_event("progress", {"stage": "loading", "percent": 5, "message": "Loading voice profile..."})
                 print(f"Loading cached voice profile: {embedding_path}")
                 voice_prompt = torch.load(embedding_path)
                 mode = "cached profile"
             else:
                 # Fallback to legacy behavior (load audio)
                 audio_bytes, final_ref_text, has_transcript = await get_audio_data(voice_id, None, "")
                 should_use_transcript = bool(final_ref_text)
                 ref_text_to_use = final_ref_text
                 ref_audio = await _load_audio_for_prompt(audio_bytes)
                 
                 # Create prompt (legacy fallback)
                 if should_use_transcript and ref_text_to_use.strip():
                     voice_prompt = manager.get_model().create_voice_clone_prompt(
                         ref_audio=ref_audio,
                         ref_text=ref_text_to_use.strip()
                     )
                     mode = "legacy transcript mode"
                 else:
                     voice_prompt = manager.get_model().create_voice_clone_prompt(
                         ref_audio=ref_audio,
                         x_vector_only_mode=True
                     )
                     mode = "legacy x-vector mode"

        else:
             # Use uploaded file logic
             if not audio_file:
                 raise HTTPException(status_code=400, detail="No audio source provided")
             audio_bytes = await audio_file.read()
             should_use_transcript = use_transcript_flag
             ref_text_to_use = reference_text
             
             ref_audio = await _load_audio_for_prompt(audio_bytes)
             
             if should_use_transcript and ref_text_to_use.strip():
                voice_prompt = manager.get_model().create_voice_clone_prompt(
                    ref_audio=ref_audio,
                    ref_text=ref_text_to_use.strip()
                )
                mode = "transcript mode"
             else:
                voice_prompt = manager.get_model().create_voice_clone_prompt(
                    ref_audio=ref_audio,
                    x_vector_only_mode=True
                )
                mode = "x-vector mode"
        
        yield send_event("progress", {"stage": "extracted", "percent": 40, "message": f"Voice profile created ({mode})"})
        await asyncio.sleep(0.1)
        
        # Stage 3: Generating speech (the long part)
        yield send_event("progress", {"stage": "generating", "percent": 50, "message": "Generating speech (this takes a while)..."})
        await asyncio.sleep(0.1)
        
        print(f"Generating speech for: '{prompt}'")
        start_time = time.time()
        
        # Run generation in a thread to not block
        loop = asyncio.get_event_loop()
        wavs, output_sr = await loop.run_in_executor(
            None,
            lambda: manager.get_model().generate_voice_clone(
                text=prompt,
                language="Auto",
                voice_clone_prompt=voice_prompt
            )
        )
        
        gen_time = time.time() - start_time
        print(f"Generation completed in {gen_time:.1f}s")
        
        yield send_event("progress", {"stage": "generated", "percent": 90, "message": f"Speech generated in {gen_time:.1f}s"})
        await asyncio.sleep(0.1)
        
        # Stage 4: Encoding output
        yield send_event("progress", {"stage": "encoding", "percent": 95, "message": "Encoding audio file..."})
        await asyncio.sleep(0.1)
        
        # Convert to WAV bytes
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, wavs[0], output_sr, format='WAV')
        audio_buffer.seek(0)
        audio_data = audio_buffer.read()
        
        # Base64 encode for SSE transport
        import base64
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        
        yield send_event("progress", {"stage": "complete", "percent": 100, "message": "Done!"})
        yield send_event("complete", {"audio": audio_b64, "format": "wav"})
        
        print(f"[OK] Voice generated successfully using {mode}!")
        
    except Exception as e:
        print(f"Error generating voice: {e}")
        yield send_event("error", {"message": str(e)})


@app.post("/api/generate-stream")
async def generate_voice_stream(
    prompt: str = Form(...),
    use_transcript: str = Form("false"),
    reference_text: str = Form(""),
    audio_file: UploadFile = File(None),
    voice_id: str = Form(None)
):
    """
    Generate cloned voice with streaming progress updates.
    Accepts EITHER audio_file OR voice_id.
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    use_transcript_bool = use_transcript.lower() == "true"
    
    return StreamingResponse(
        generate_with_progress(prompt, voice_id, audio_file, reference_text, use_transcript_bool),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/generate")
async def generate_voice(
    prompt: str = Form(...),
    use_transcript: str = Form("false"),
    reference_text: str = Form(""),
    audio_file: UploadFile = File(None),
    voice_id: str = Form(None)
):
    """
    Generate cloned voice (non-streaming version).
    """
    try:
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        # Resolve Input
        if voice_id:
             # Use saved voice logic
             audio_bytes, final_ref_text, has_transcript = await get_audio_data(voice_id, None, "")
             should_use_transcript = bool(final_ref_text)
             ref_text_to_use = final_ref_text
        else:
             # Use uploaded file logic
             if not audio_file:
                 raise HTTPException(status_code=400, detail="Audio file or voice_id is required")
             audio_bytes = await audio_file.read()
             should_use_transcript = use_transcript.lower() == "true"
             ref_text_to_use = reference_text
        
        # Load audio with librosa
        audio_io = io.BytesIO(audio_bytes)
        try:
            audio, sr = librosa.load(audio_io, sr=16000, mono=True)
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to load audio file: {str(e)}"
            )
        
        audio = audio.astype(np.float32)
        ref_audio = [(audio, 16000)]
        
        if should_use_transcript and ref_text_to_use.strip():
            print(f"Generating voice with transcript: '{ref_text_to_use[:50]}...'")
            voice_prompt = manager.get_model().create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=ref_text_to_use.strip()
            )
            mode = "transcript mode"
        else:
            print("Generating voice in x-vector mode")
            voice_prompt = manager.get_model().create_voice_clone_prompt(
                ref_audio=ref_audio,
                x_vector_only_mode=True
            )
            mode = "x-vector mode"
        
        print(f"Text to synthesize: '{prompt}'")
        
        wavs, output_sr = manager.get_model().generate_voice_clone(
            text=prompt,
            language="Auto",
            voice_clone_prompt=voice_prompt
        )
        
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, wavs[0], output_sr, format='WAV')
        audio_buffer.seek(0)
        
        print(f"[OK] Voice generated successfully using {mode}!")
        
        return StreamingResponse(
            audio_buffer,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=generated.wav"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Model Management Endpoints
# ============================================================================

@app.get("/api/model/status")
async def get_model_status():
    return {
        "current_model": manager.model_type,
        "is_loading": manager.is_loading,
        "supported_models": MODEL_MAP
    }

@app.post("/api/model/switch")
async def switch_model(target_model: str = Form(...)):
    if target_model not in MODEL_MAP:
        raise HTTPException(status_code=400, detail="Invalid model type")
    
    try:
        if manager.model_type != target_model:
            manager.load_model(target_model)
        return {"status": "success", "current_model": target_model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-design")
async def generate_design(
    text: str = Form(...),
    instruct: str = Form(...)
):
    if manager.model_type != "design":
         raise HTTPException(status_code=400, detail="Please switch to 'Voice Design' model first.")
    
    try:
        print(f"Generating Voice Design: '{text}' (Instruct: '{instruct}')")
        
        # Run generation in a thread
        loop = asyncio.get_event_loop()
        wavs, output_sr = await loop.run_in_executor(
            None,
            lambda: manager.get_model().generate_voice_design(
                text=text,
                instruct=instruct,
                language="Auto"
            )
        )
        
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, wavs[0], output_sr, format='WAV')
        audio_buffer.seek(0)
        
        return StreamingResponse(
            audio_buffer,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=design_generated.wav"
            }
        )
    except Exception as e:
         print(f"Error in Voice Design: {e}")
         raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-preset")
async def generate_preset(
    text: str = Form(...),
    speaker: str = Form(...),
):
    if manager.model_type != "custom":
         raise HTTPException(status_code=400, detail="Please switch to 'Custom Voice' model first.")
    
    try:
        print(f"Generating Custom Voice: '{text}' (Speaker: '{speaker}')")
        
        # Run generation in a thread
        loop = asyncio.get_event_loop()
        wavs, output_sr = await loop.run_in_executor(
            None,
            lambda: manager.get_model().generate_custom_voice(
                text=text,
                speaker=speaker,
                language="Auto"
            )
        )
        
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, wavs[0], output_sr, format='WAV')
        audio_buffer.seek(0)
        
        return StreamingResponse(
            audio_buffer,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=preset_generated.wav"
            }
        )
    except Exception as e:
         print(f"Error in Custom Voice: {e}")
         raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*50)
    print("[Parrot AI] FastAPI Backend")
    print("="*50)
    print(f"Device: {DEVICE}")
    print(f"Supported Models: {list(MODEL_MAP.keys())}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
