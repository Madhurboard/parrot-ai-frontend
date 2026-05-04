import time
import torch
import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

import qwen_engine as qwen_tts
from backend.config import MODEL_MAP, DEVICE, DTYPE

def benchmark_local():
    print("=== LOCAL BENCHMARK ===")
    start_load = time.time()
    engine = qwen_tts.Qwen3TTSModel.from_pretrained(
        MODEL_MAP["base"],
        device=DEVICE,
        dtype=DTYPE
    )
    load_time = time.time() - start_load
    print(f"Model Load Time: {load_time:.2f}s")

    test_sentences = [
        "Hello, this is a short test of the local synthesis engine.",
        "Parrot AI Studio provides editorial grade monochrome design and high performance voice cloning capabilities for professional creators around the world."
    ]

    for i, text in enumerate(test_sentences):
        print(f"\nTest {i+1}: {len(text.split())} words")
        start_gen = time.time()
        # Using a dummy prompt or none for base model speed test
        audio, sr = engine.generate_voice_clone(text=text)
        gen_time = time.time() - start_gen
        
        audio_duration = sum([len(a) for a in audio]) / sr
        rtf = gen_time / audio_duration
        
        print(f"Generation Time: {gen_time:.2f}s")
        print(f"Audio Duration: {audio_duration:.2f}s")
        print(f"Real-Time Factor (RTF): {rtf:.3f} (lower is better)")

def benchmark_cloud():
    print("\n=== CLOUD BENCHMARK (Hugging Face) ===")
    try:
        from gradio_client import Client
        print("Connecting to Hugging Face Space: Qwen/Qwen3-TTS...")
        start_connect = time.time()
        client = Client("Qwen/Qwen3-TTS")
        print(f"Connected in {time.time() - start_connect:.2f}s")
        
        test_sentences = [
            "Hello, this is a short test of the cloud synthesis engine.",
            "Parrot AI Studio provides editorial grade monochrome design and high performance voice cloning capabilities for professional creators around the world."
        ]

        for i, text in enumerate(test_sentences):
            print(f"\nTest {i+1}: {len(text.split())} words")
            start_gen = time.time()
            # Note: The exact API name might vary, this is a guess based on typical Qwen Spaces
            # We use predict() which is the standard Gradio client method
            try:
                result = client.predict(
                    text,
                    "Auto", # Language
                    None,   # Voice prompt
                    api_name="/predict"
                )
                gen_time = time.time() - start_gen
                print(f"Cloud Generation Time (incl. Network): {gen_time:.2f}s")
            except Exception as e:
                print(f"Cloud call failed: {e}")
                print("Tip: Ensure the HF Space is active and public.")
                
    except ImportError:
        print("Error: 'gradio_client' not installed. Run 'pip install gradio_client' to test cloud.")
    except Exception as e:
        print(f"Cloud Benchmark Error: {e}")

if __name__ == "__main__":
    # Ensure model cache exists
    if not os.path.exists(MODEL_MAP["base"]):
        print(f"Error: Local model not found at {MODEL_MAP['base']}. Please download it first.")
    else:
        benchmark_local()
    
    benchmark_cloud()
