import time
import os

def benchmark_cloud():
    print("\n=== CLOUD SPEED TEST (Hugging Face) ===")
    try:
        from gradio_client import Client
        print("Connecting to Hugging Face Space: Qwen/Qwen3-TTS...")
        start_connect = time.time()
        # This connects to the official Qwen space
        client = Client("Qwen/Qwen3-TTS")
        print(f"Connected in {time.time() - start_connect:.2f}s")
        
        test_sentences = [
            "Hello, this is a short test of the cloud synthesis engine.",
            "Parrot AI Studio provides editorial grade monochrome design and high performance voice cloning capabilities for professional creators around the world."
        ]

        for i, text in enumerate(test_sentences):
            print(f"\nTest {i+1}: {len(text.split())} words")
            start_gen = time.time()
            try:
                # We use the /predict endpoint
                # Arguments for Qwen3-TTS space: (text, language, voice_prompt, speed)
                result = client.predict(
                    text,
                    "Auto", # Language
                    None,   # Voice prompt (None = base voice)
                    api_name="/predict"
                )
                gen_time = time.time() - start_gen
                print(f"Cloud Generation Time (incl. Network): {gen_time:.2f}s")
            except Exception as e:
                print(f"Cloud call failed: {e}")
                
    except ImportError:
        print("Error: 'gradio_client' not installed. Run 'pip install gradio_client'.")
    except Exception as e:
        print(f"Cloud Error: {e}")

if __name__ == "__main__":
    benchmark_cloud()
