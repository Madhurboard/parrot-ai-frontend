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
from typing import AsyncGenerator
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from qwen_tts import Qwen3TTSModel

# ============================================================================
# Configuration
# ============================================================================

MODEL_NAME = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

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
# Model Loading
# ============================================================================

print(f"[Parrot AI] Loading model on {DEVICE}...")
print(f"Model: {MODEL_NAME}")

model = Qwen3TTSModel.from_pretrained(
    MODEL_NAME,
    device_map=DEVICE,
    dtype=DTYPE
)

print("[OK] Model loaded successfully!")

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
    
    Args:
        audio_file: Audio file to transcribe (MP3, WAV, WebM)
    
    Returns:
        JSON with transcribed text
    """
    try:
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Save to temp file (Whisper needs a file path)
        import tempfile
        import os
        
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


async def generate_with_progress(
    prompt: str,
    use_transcript: bool,
    reference_text: str,
    audio_bytes: bytes
) -> AsyncGenerator[str, None]:
    """Generator that yields SSE progress events during voice generation."""
    
    def send_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    try:
        # Stage 1: Loading audio
        yield send_event("progress", {"stage": "loading", "percent": 5, "message": "Loading reference audio..."})
        await asyncio.sleep(0.1)  # Allow event to flush
        
        # Load audio with librosa
        audio_io = io.BytesIO(audio_bytes)
        try:
            audio, sr = librosa.load(audio_io, sr=16000, mono=True)
        except Exception as e:
            yield send_event("error", {"message": f"Failed to load audio: {str(e)}"})
            return
        
        audio = audio.astype(np.float32)
        ref_audio = [(audio, 16000)]
        
        yield send_event("progress", {"stage": "loaded", "percent": 15, "message": "Reference audio loaded"})
        await asyncio.sleep(0.1)
        
        # Stage 2: Creating voice prompt
        yield send_event("progress", {"stage": "extracting", "percent": 25, "message": "Extracting voice characteristics..."})
        await asyncio.sleep(0.1)
        
        if use_transcript and reference_text.strip():
            print(f"Creating voice prompt with transcript: '{reference_text[:50]}...'")
            voice_prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=reference_text.strip()
            )
            mode = "transcript mode"
        else:
            print("Creating voice prompt in x-vector mode")
            voice_prompt = model.create_voice_clone_prompt(
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
            lambda: model.generate_voice_clone(
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
    audio_file: UploadFile = File(...)
):
    """
    Generate cloned voice with streaming progress updates.
    
    Returns Server-Sent Events with progress and final audio.
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    if not audio_file:
        raise HTTPException(status_code=400, detail="Audio file is required")
    
    audio_bytes = await audio_file.read()
    use_transcript_bool = use_transcript.lower() == "true"
    
    return StreamingResponse(
        generate_with_progress(prompt, use_transcript_bool, reference_text, audio_bytes),
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
    audio_file: UploadFile = File(...)
):
    """
    Generate cloned voice (non-streaming version for compatibility).
    """
    try:
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        audio_bytes = await audio_file.read()
        
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
        
        use_ref_text = use_transcript.lower() == "true" and reference_text.strip()
        
        if use_ref_text:
            print(f"Generating voice with transcript: '{reference_text[:50]}...'")
            voice_prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=reference_text.strip()
            )
            mode = "transcript mode"
        else:
            print("Generating voice in x-vector mode")
            voice_prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                x_vector_only_mode=True
            )
            mode = "x-vector mode"
        
        print(f"Text to synthesize: '{prompt}'")
        
        wavs, output_sr = model.generate_voice_clone(
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
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*50)
    print("[Parrot AI] FastAPI Backend")
    print("="*50)
    print(f"Device: {DEVICE}")
    print(f"Model: {MODEL_NAME}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
