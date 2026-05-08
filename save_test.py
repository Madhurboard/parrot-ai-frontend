import requests, base64, json, time
r = requests.post(
    "http://localhost:8000/api/generate-stream",
    headers={"Authorization": "Bearer test-token"},
    files={"audio_file": ("r.mp3", open(r"d:\Voice-Cloner-Qwen-Arnav\Recording (2).mp3", "rb"), "audio/mpeg")},
    data={"prompt": "hii how are you"},
    stream=True,
)
print(f"Status: {r.status_code}")
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data: ") and '"audio"' in line:
        d = json.loads(line[6:])
        ab = base64.b64decode(d["audio"])
        with open(r"d:\Voice-Cloner-Qwen-Arnav\test_output.wav", "wb") as f:
            f.write(ab)
        print(f"Saved WAV: {len(ab)} bytes")
        break
    elif line and line.startswith("data:"):
        try:
            d = json.loads(line[6:])
            print(f"{d.get('percent','')}% {d.get('message','')}")
        except:
            pass
