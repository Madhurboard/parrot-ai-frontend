"""
Parrot AI - FastAPI Backend
Connects the Next.js frontend to Qwen3-TTS model

Run with: uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
"""

import io
import json
import time
import uuid
import os
import shutil
import re
import gc
import asyncio
import sqlite3
import base64
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Tuple, Dict, Any, Union

import torch
import numpy as np
import librosa
import soundfile as sf
import whisper

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

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
# Helpers
# ============================================================================

async def _load_audio_bytes(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Helper to load audio bytes into numpy array."""
    audio_io = io.BytesIO(audio_bytes)
    # Run librosa in executor to avoid blocking main thread
    loop = asyncio.get_event_loop()
    audio, sr = await loop.run_in_executor(None, lambda: librosa.load(audio_io, sr=16000, mono=True))
    return audio.astype(np.float32), 16000

async def _create_voice_profile(model: Qwen3TTSModel, audio_bytes: bytes, transcript: Optional[str] = None) -> Any:
    """
    Unified helper to create a voice profile from audio bytes.
    Handles both transcript-based and x-vector extraction.
    """
    audio, sr = await _load_audio_bytes(audio_bytes)
    ref_audio = [(audio, sr)]

    if transcript and transcript.strip():
        # Full voice clone with transcript (higher quality)
        return model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=transcript.strip()
        )
    else:
        # X-vector only mode (faster, no transcript needed)
        return model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            x_vector_only_mode=True
        )

def smart_split_text(text: str, max_chars: int = 500) -> List[str]:
    """
    Splits long text into smaller chunks based on sentence boundaries.
    Prioritizes splitting at punctuation to preserve flow.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    current_chunk = ""
    
    # Split by sentence endings using regex lookbehind
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_chars:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # Reset current chunk
            current_chunk = sentence + " "
            
            # Handle extremely long single sentences by splitting at commas or spaces
            while len(current_chunk) > max_chars:
                split_point = current_chunk.rfind(',', 0, max_chars)
                if split_point == -1:
                    split_point = current_chunk.rfind(' ', 0, max_chars)
                
                if split_point != -1:
                   chunks.append(current_chunk[:split_point+1].strip())
                   current_chunk = current_chunk[split_point+1:]
                else: 
                   # Hard split if absolutely no break points found
                   chunks.append(current_chunk[:max_chars].strip())
                   current_chunk = current_chunk[max_chars:]

    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

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
             voice_prompt_items = await _create_voice_profile(
                 manager.get_model(), 
                 file_content, 
                 transcript
             )
        else:
             print(f"Creating x-vector profile for {name}...")
             voice_prompt_items = await _create_voice_profile(
                 manager.get_model(), 
                 file_content, 
                 None
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



async def _resolve_voice_model(manager: ModelManager, voice_id: Optional[str], audio_file: Optional[UploadFile], transcript: str, use_transcript: bool) -> Tuple[Any, str]:
    """
    Determines the voice model prompt to use based on inputs (Saved Voice ID vs Uploaded File).
    Returns (voice_prompt, mode_description).
    """
    if voice_id:
        # CASE 1: Use Saved Voice
        conn = get_db()
        voice = conn.execute('SELECT * FROM voices WHERE id = ?', (voice_id,)).fetchone()
        conn.close()
        
        if not voice:
            raise ValueError("Voice not found")
        
        # Check for cached embedding
        embedding_path = os.path.join(VOICES_DIR, f"{voice_id}.pt")
        if os.path.exists(embedding_path):
            print(f"Loading cached embedding for voice {voice_id}")
            return torch.load(embedding_path), "saved voice (cached)"
            
        # Compute from stored audio file
        audio_path = os.path.join(VOICES_DIR, voice['filename'])
        if not os.path.exists(audio_path):
            raise ValueError("Voice audio file missing")
            
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Use stored transcript if available
        final_transcript = voice['transcript'] if voice['transcript'] else None
        
        prompt = await _create_voice_profile(manager.get_model(), audio_bytes, final_transcript)
        return prompt, "saved voice"

    elif audio_file:
        # CASE 2: Use Uploaded File
        audio_bytes = await audio_file.read()
        final_transcript = transcript if (use_transcript and transcript.strip()) else None
        
        prompt = await _create_voice_profile(manager.get_model(), audio_bytes, final_transcript)
        mode = "transcript mode" if final_transcript else "x-vector mode"
        return prompt, mode

    else:
        raise ValueError("No voice provided (ID or File required)")

async def generate_with_progress(prompt, voice_id, audio_file, reference_text, use_transcript, temperature=0.8, top_p=0.8, top_k=50, repetition_penalty=1.1):
    """Generator that yields SSE progress events during voice generation."""
    
    def send_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    yield send_event("progress", {"stage": "init", "percent": 0, "message": "Initializing generation..."})
        
    try:
        # Stage 1: Load/Create Voice Prompt
        yield send_event("progress", {"stage": "analyzing", "percent": 10, "message": "Analyzing voice characteristics..."})
        
        voice_prompt, mode = await _resolve_voice_model(
            manager, voice_id, audio_file, reference_text, use_transcript
        )
        
        yield send_event("progress", {"stage": "extracted", "percent": 30, "message": f"Voice profile ready ({mode})"})
        await asyncio.sleep(0.1)
        
        # Stage 2: Generate Speech
        yield send_event("progress", {"stage": "generating", "percent": 40, "message": "Generating speech components..."})
        
        text_chunks = smart_split_text(prompt)
        print(f"Generating '{prompt[:30]}...' in {len(text_chunks)} chunks (Temp: {temperature})")
        
        all_wavs = []
        output_sr = 24000
        loop = asyncio.get_event_loop()
        start_time = time.time()

        for i, chunk in enumerate(text_chunks):
            # Calculate progress: 40% -> 90%
            chunk_progress = 40 + int((i / len(text_chunks)) * 50)
            yield send_event("progress", {"stage": "generating", "percent": chunk_progress, "message": f"Generating part {i+1}/{len(text_chunks)}..."})
            
            wavs, sr = await loop.run_in_executor(
                None,
                lambda: manager.get_model().generate_voice_clone(
                    text=chunk,
                    language="Auto",
                    voice_clone_prompt=voice_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty
                )
            )
            all_wavs.append(wavs[0])
            output_sr = sr

        gen_time = time.time() - start_time
        yield send_event("progress", {"stage": "generated", "percent": 90, "message": f"Generated in {gen_time:.1f}s"})
        
        # Stage 3: Encode Output
        yield send_event("progress", {"stage": "encoding", "percent": 95, "message": "Finalizing audio..."})
        
        combined_wav = np.concatenate(all_wavs)
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, combined_wav, output_sr, format='WAV')
        audio_buffer.seek(0)
        
        audio_b64 = base64.b64encode(audio_buffer.read()).decode('utf-8')
        
        yield send_event("progress", {"stage": "complete", "percent": 100, "message": "Done!"})
        yield send_event("complete", {"audio": audio_b64, "format": "wav"})
        
        print(f"[OK] Generation complete ({mode})")
        
    except Exception as e:
        print(f"Error generating voice: {e}")
        yield send_event("error", {"message": str(e)})

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
    repetition_penalty: float = Form(1.1)
):
    """
    Generate cloned voice with streaming progress updates.
    Accepts EITHER audio_file OR voice_id.
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    use_transcript_bool = use_transcript.lower() == "true"
    
    return StreamingResponse(
        generate_with_progress(
            prompt, voice_id, audio_file, reference_text, use_transcript_bool,
            temperature, top_p, top_k, repetition_penalty
        ),
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
        
        if should_use_transcript and ref_text_to_use.strip():
            print(f"Generating voice with transcript: '{ref_text_to_use[:50]}...'")
            voice_prompt = await _create_voice_profile(
                manager.get_model(),
                audio_bytes,
                ref_text_to_use.strip()
            )
            mode = "transcript mode"
        else:
            print("Generating voice in x-vector mode")
            voice_prompt = await _create_voice_profile(
                 manager.get_model(),
                 audio_bytes,
                 None
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
    instruct: str = Form(...),
    temperature: float = Form(0.8),
    top_p: float = Form(0.8),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1)
):
    if manager.model_type != "design":
         raise HTTPException(status_code=400, detail="Please switch to 'Voice Design' model first.")
    
    try:
        print(f"Generating Voice Design: '{text[:50]}...' (Inst: '{instruct[:50]}') Temp: {temperature}")
        
        # Split text for long-form generation
        text_chunks = smart_split_text(text)
        print(f"Split into {len(text_chunks)} chunks")

        # Run generation in a thread
        loop = asyncio.get_event_loop()
        
        all_wavs = []
        output_sr = 24000 # default
        
        for chunk in text_chunks:
            wavs, sr = await loop.run_in_executor(
                None,
                lambda: manager.get_model().generate_voice_design(
                    text=chunk,
                    instruct=instruct,
                    language="Auto",
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty
                )
            )
            all_wavs.append(wavs[0])
            output_sr = sr
            
        # Concatenate all chunks
        combined_wav = np.concatenate(all_wavs)
        
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, combined_wav, output_sr, format='WAV')
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
    temperature: float = Form(0.8),
    top_p: float = Form(0.8),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1)
):
    if manager.model_type != "custom":
         raise HTTPException(status_code=400, detail="Please switch to 'Custom Voice' model first.")
    
    try:
        print(f"Generating Custom Voice: '{text[:50]}...' (Spk: '{speaker}') Temp: {temperature}")
        
        text_chunks = smart_split_text(text)
        print(f"Split into {len(text_chunks)} chunks")
        
        loop = asyncio.get_event_loop()
        all_wavs = []
        output_sr = 24000
        
        for chunk in text_chunks:
            wavs, sr = await loop.run_in_executor(
                None,
                lambda: manager.get_model().generate_custom_voice(
                    text=chunk,
                    speaker=speaker,
                    language="Auto",
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty
                )
            )
            all_wavs.append(wavs[0])
            output_sr = sr
            
        combined_wav = np.concatenate(all_wavs)
        
        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, combined_wav, output_sr, format='WAV')
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


# ============================================================================
# Pydantic Models for Dialogue
# ============================================================================

class DialogueLine(BaseModel):
    text: str
    speaker: str # One of the PRESET keys or a voice_id
    type: str # "preset" or "cloned"
    temperature: float = 0.8
    top_p: float = 0.8
    top_k: int = 50
    repetition_penalty: float = 1.1

class DialogueRequest(BaseModel):
    lines: List[DialogueLine]

@app.post("/api/generate-dialogue")
async def generate_dialogue(request: DialogueRequest):
    """
    Generates a multi-speaker audio file by processing lines sequentially.
    Stitches the output into a single WAV file with 0.3s silence between turns.
    """
    if not request.lines:
         raise HTTPException(status_code=400, detail="Script cannot be empty")
         
    print(f"Generating Dialogue with {len(request.lines)} lines")
    
    loop = asyncio.get_event_loop()
    all_audio_segments = []
    output_sr = 24000
    
    # Pre-generate silence (0.3s)
    silence = np.zeros(int(output_sr * 0.3))
    
    for i, line in enumerate(request.lines):
        print(f"[{i+1}/{len(request.lines)}] generating line for {line.speaker}...")
        
        # 1. Determine Model Type and Switch if needed
        needed_model = "custom" if line.type == "preset" else "base"
        
        if manager.model_type != needed_model:
            print(f"Switching model to {needed_model} for {line.speaker}...")
            # Run in executor to prevent blocking
            await loop.run_in_executor(None, lambda: manager.load_model(needed_model))
            
        # 2. Generate Audio
        wavs = None
        
        if line.type == "preset":
            # Generate Custom Voice
            wavs, sr = await loop.run_in_executor(
                None,
                lambda: manager.get_model().generate_custom_voice(
                    text=line.text,
                    speaker=line.speaker,
                    language="Auto",
                    temperature=line.temperature,
                    top_p=line.top_p,
                    top_k=line.top_k,
                    repetition_penalty=line.repetition_penalty
                )
            )
            output_sr = sr
            
        else: # type == "cloned"
             # Generate Cloned Voice
             voice_id = line.speaker
             
             # Load voice prompt
             mode = "unknown"
             voice_prompt = None
             
             # Check for pre-computed embedding
             embedding_path = os.path.join(VOICES_DIR, f"{voice_id}.pt")
             
             if os.path.exists(embedding_path):
                 voice_prompt = torch.load(embedding_path)
             else:
                 # Fallback: Load from DB and compute
                 conn = get_db()
                 voice = conn.execute('SELECT * FROM voices WHERE id = ?', (voice_id,)).fetchone()
                 conn.close()
                 
                 if not voice:
                     print(f"Skipping line: Voice {voice_id} not found")
                     continue
                     
                 audio_path = os.path.join(VOICES_DIR, voice['filename'])
                 with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                 
                 ref_audio = await _load_audio_for_prompt(audio_bytes)
                 
                 if voice['transcript']:
                    voice_prompt = manager.get_model().create_voice_clone_prompt(ref_audio=ref_audio, ref_text=voice['transcript'])
                 else:
                    voice_prompt = manager.get_model().create_voice_clone_prompt(ref_audio=ref_audio, x_vector_only_mode=True)

             # Generate
             wavs, sr = await loop.run_in_executor(
                None,
                lambda: manager.get_model().generate_voice_clone(
                    text=line.text,
                    language="Auto",
                    voice_clone_prompt=voice_prompt,
                    temperature=line.temperature,
                    top_p=line.top_p,
                    top_k=line.top_k,
                    repetition_penalty=line.repetition_penalty
                )
            )
             output_sr = sr

        if wavs is not None:
             all_audio_segments.append(wavs[0])
             # Add silence after every line except the last
             if i < len(request.lines) - 1:
                 all_audio_segments.append(silence)
    
    # 3. Concatenate and Return
    if not all_audio_segments:
        raise HTTPException(status_code=500, detail="No audio generated")
        
    combined_wav = np.concatenate(all_audio_segments)
    
    audio_buffer = io.BytesIO()
    sf.write(audio_buffer, combined_wav, output_sr, format='WAV')
    audio_buffer.seek(0)
    
    return StreamingResponse(audio_buffer, media_type="audio/wav")

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*50)
    print("[Parrot AI] FastAPI Backend")
    print("="*50)
    print(f"Device: {DEVICE}")
    print(f"Supported Models: {list(MODEL_MAP.keys())}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
