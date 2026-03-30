import requests
import json
import base64

def test_generation():
    url = "http://localhost:8000/api/generate-stream"
    headers = {
        "Authorization": "Bearer test-token"
    }
    
    # We'll use the 'uploaded' path with a very short dummy WAV
    # To simulate the large tensor, we should use a real audio or just a long enough one.
    # But since we fixed the logic, any audio should now be encoded or handled correctly.
    
    # Create a 1-second 16kHz dummy audio (16000 samples)
    import numpy as np
    import soundfile as sf
    import io
    
    sr = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format='WAV')
    buf.seek(0)
    
    data = {
        "prompt": "This is a verification test of the voice cloning system.",
        "use_transcript": "false",
        "reference_text": "",
        "temperature": 0.8
    }
    
    files = {
        "audio_file": ("test.wav", buf, "audio/wav")
    }
    
    print(f"Sending request to {url}...")
    response = requests.post(url, headers=headers, data=data, files=files, stream=True)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return

    print("Streamed response:")
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                event_data = json.loads(decoded_line[6:])
                print(f" - {event_data.get('stage', 'unknown')}: {event_data.get('message', '')}")
                if 'audio' in event_data:
                    print(" [SUCCESS] Received audio data!")
                if decoded_line.startswith('event: error'):
                    print(f" [ERROR EVENT] {event_data.get('message')}")

if __name__ == "__main__":
    test_generation()
