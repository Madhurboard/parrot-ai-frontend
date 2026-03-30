from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel
import inspect

print("Qwen3TTSModel methods:")
for name, member in inspect.getmembers(Qwen3TTSModel, predicate=inspect.isfunction):
    print(f" - {name}")
