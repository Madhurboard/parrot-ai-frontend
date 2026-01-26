"""
Parrot AI - Voice Cloning Application
Powered by Qwen3-TTS-12Hz-1.7B-Base

Run with: python app.py
"""

import torch
import gradio as gr
import librosa
import numpy as np
from qwen_tts import Qwen3TTSModel

# ============================================================================
# Configuration
# ============================================================================

MODEL_NAME = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

# ============================================================================
# Model Loading
# ============================================================================

print(f"Loading model on {DEVICE}...")
print(f"Model: {MODEL_NAME}")

model = Qwen3TTSModel.from_pretrained(
    MODEL_NAME,
    device_map=DEVICE,
    dtype=DTYPE
)

print("✓ Model loaded successfully!")

# ============================================================================
# Audio Processing
# ============================================================================

def load_ref_audio(path: str, target_sr: int = 16000) -> list:
    """Load and preprocess reference audio for voice cloning."""
    audio, sr = librosa.load(
        path,
        sr=target_sr,
        mono=True  # Ensure mono audio
    )
    audio = audio.astype(np.float32)
    return [(audio, target_sr)]

# ============================================================================
# Voice Cloning Function
# ============================================================================

def clone_voice(
    audio_path: str,
    use_manual_transcript: bool,
    transcript: str,
    text_to_synthesize: str
):
    """
    Clone a voice from reference audio and generate new speech.
    
    Args:
        audio_path: Path to reference audio file (5-10 seconds recommended)
        use_manual_transcript: Whether to use manual transcript (better quality)
        transcript: Manual transcript of reference audio (optional)
        text_to_synthesize: Text to speak in the cloned voice
    
    Returns:
        Tuple of (audio_output, status_message)
    """
    # Validation
    if audio_path is None:
        return None, "❌ Please upload a reference audio file."
    
    if not text_to_synthesize.strip():
        return None, "❌ Please enter text to synthesize."
    
    try:
        # Load reference audio
        ref_audio = load_ref_audio(audio_path)
        
        # Create voice clone prompt
        if use_manual_transcript and transcript.strip():
            # Full voice clone with transcript (higher quality)
            prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                ref_text=transcript
            )
            mode = "full transcript mode"
        else:
            # X-vector only mode (faster, no transcript needed)
            prompt = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                x_vector_only_mode=True
            )
            mode = "x-vector mode"
        
        # Generate cloned speech
        wavs, sr = model.generate_voice_clone(
            text=text_to_synthesize,
            language="Auto",
            voice_clone_prompt=prompt
        )
        
        return (sr, wavs[0]), f"✅ Voice cloned successfully using {mode}!"
    
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# ============================================================================
# Gradio Interface
# ============================================================================

# Custom CSS for Parrot AI branding
custom_css = """
.gradio-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.gr-button-primary {
    background: linear-gradient(135deg, #00d4aa 0%, #007acc 100%) !important;
    border: none !important;
}
.gr-button-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 212, 170, 0.3);
}
"""

with gr.Blocks(
    title="Parrot AI - Voice Cloning",
    theme=gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="cyan",
        neutral_hue="slate"
    ),
    css=custom_css
) as demo:
    
    gr.Markdown("""
    # 🦜 Parrot AI - Voice Cloning
    ### *If you can hear it, we can clone it.*
    
    Upload a clear voice sample (5-10 seconds) and enter text to synthesize.
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            # Input Section
            audio_input = gr.Audio(
                sources=["microphone", "upload"],
                type="filepath",
                label="🎙️ Reference Voice (5-10s, clear speech)"
            )
            
            transcript_toggle = gr.Checkbox(
                label="📝 Provide transcript manually (better quality)",
                value=False
            )
            
            transcript_input = gr.Textbox(
                label="Reference Transcript (what is said in the audio)",
                placeholder="Enter the exact words spoken in your reference audio...",
                lines=2,
                visible=False
            )
            
            text_input = gr.Textbox(
                label="✍️ Text to Synthesize",
                placeholder="Enter the text you want the cloned voice to speak...",
                lines=3
            )
            
            generate_btn = gr.Button(
                "🚀 Generate Cloned Voice",
                variant="primary",
                size="lg"
            )
        
        with gr.Column(scale=1):
            # Output Section
            output_audio = gr.Audio(
                label="🔊 Cloned Voice Output",
                type="numpy"
            )
            
            status = gr.Textbox(
                label="Status",
                interactive=False
            )
    
    # Show/hide transcript based on toggle
    transcript_toggle.change(
        fn=lambda x: gr.update(visible=x),
        inputs=[transcript_toggle],
        outputs=[transcript_input]
    )
    
    # Generate button click
    generate_btn.click(
        fn=clone_voice,
        inputs=[audio_input, transcript_toggle, transcript_input, text_input],
        outputs=[output_audio, status]
    )
    
    # Examples
    gr.Markdown("""
    ---
    ### Tips for Best Results:
    - Use **5-10 seconds** of clear, single-speaker audio
    - Avoid background noise or music
    - Providing a **transcript** improves voice matching quality
    - Works best with natural, conversational speech
    """)

# ============================================================================
# Launch
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🦜 Parrot AI - Voice Cloning")
    print("="*50)
    print(f"Device: {DEVICE}")
    print(f"Model: {MODEL_NAME}")
    print("="*50 + "\n")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
