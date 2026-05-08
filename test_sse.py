"""Quick SSE test — sends audio + prompt to /api/generate-stream and logs every chunk."""
import requests, time, sys

API = "http://localhost:8000"
TOKEN = "test-token"
AUDIO_FILE = r"d:\Voice-Cloner-Qwen-Arnav\Recording (2).mp3"
PROMPT = "hii how are you"

print("=" * 60)
print("  PARROT AI — SSE Stream Test")
print("=" * 60)

# Build multipart form
files = {"audio_file": ("recording.mp3", open(AUDIO_FILE, "rb"), "audio/mpeg")}
data = {"prompt": PROMPT, "use_transcript": "false", "reference_text": ""}

print(f"\n[POST] {API}/api/generate-stream")
print(f"  Prompt: {PROMPT}")
print(f"  Audio:  {AUDIO_FILE}")
print()

t0 = time.time()
resp = requests.post(
    f"{API}/api/generate-stream",
    headers={"Authorization": f"Bearer {TOKEN}"},
    files=files,
    data=data,
    stream=True,
)

print(f"[{resp.status_code}] Response received, reading SSE stream...\n")

if resp.status_code != 200:
    print(f"ERROR: {resp.text}")
    sys.exit(1)

event_type = ""
chunk_count = 0
audio_b64_len = 0

for raw_line in resp.iter_lines(decode_unicode=True):
    if raw_line is None:
        continue
    line = raw_line.strip()
    if not line:
        continue

    if line.startswith("event: "):
        event_type = line[7:].strip()
    elif line.startswith("data: "):
        import json
        try:
            d = json.loads(line[6:])
        except json.JSONDecodeError:
            print(f"  [WARN] JSON parse failed on {len(line)} char line")
            continue

        if event_type == "progress":
            elapsed = time.time() - t0
            print(f"  [{elapsed:5.1f}s] PROGRESS {d.get('percent', 0):3d}% — {d.get('message', '')}")
        elif event_type == "complete":
            audio_b64_len = len(d.get("audio", ""))
            elapsed = time.time() - t0
            print(f"  [{elapsed:5.1f}s] COMPLETE — audio base64 length: {audio_b64_len}")
            
            # Decode and save
            import base64
            audio_bytes = base64.b64decode(d["audio"])
            out_path = r"d:\Voice-Cloner-Qwen-Arnav\test_output.wav"
            with open(out_path, "wb") as f:
                f.write(audio_bytes)
            print(f"\n  ✅ Audio saved: {out_path} ({len(audio_bytes)} bytes)")
        elif event_type == "error":
            print(f"  ❌ ERROR: {d.get('message', 'unknown')}")

total = time.time() - t0
print(f"\n{'=' * 60}")
print(f"  Done in {total:.1f}s")
if audio_b64_len > 0:
    print(f"  ✅ SUCCESS — Audio received and decoded")
else:
    print(f"  ❌ FAILED — No audio in stream")
print(f"{'=' * 60}")
