import torch
import os
import io
import gc
import numpy as np
import librosa
from typing import List, Tuple, Optional, Any
from transformers import AutoConfig, AutoModel, AutoProcessor

from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel as OfficialQwen3TTSModel, VoiceClonePromptItem

class Qwen3TTSModel:
    """
    Refactored wrapper around the official Qwen3-TTS library.
    Ensures tiered inference fallback by exposing the same interface as the cloud client.
    """
    def __init__(self, official_model: OfficialQwen3TTSModel):
        self.official_model = official_model

    @classmethod
    def from_pretrained(cls, model_path: str, device: str = "cuda", dtype: torch.dtype = torch.bfloat16):
        """Standard loading method used by ModelManager."""
        # Check if model_path is a local directory with model files
        if os.path.isdir(model_path) and any(f in os.listdir(model_path) for f in ['pytorch_model.bin', 'model.safetensors', 'tf_model.h5', 'model.ckpt.index', 'flax_model.msgpack']):
            print(f"[Qwen3TTS] Loading from local cache: {model_path}...")
            model_source = model_path
        else:
            # If it looks like a local path (contains separators), generate HF repo ID
            if "/" in model_path or "\\" in model_path:
                # Extract model name from path (e.g., "Qwen3-TTS-1.7B-Base")
                model_name = os.path.basename(model_path)
                hf_repo_id = f"Qwen/{model_name}"
                print(f"[Qwen3TTS] Local model not found. Attempting to download from Hugging Face: {hf_repo_id}...")
                model_source = hf_repo_id
            else:
                # Already looks like a repo ID
                model_source = model_path
                print(f"[Qwen3TTS] Loading from Hugging Face: {model_source}...")
        
        try:
            print(f"[Qwen3TTS] Loading model: {model_source}...")
            official = OfficialQwen3TTSModel.from_pretrained(
                model_source,
                device_map="cuda", # Let Transformers handle all sub-module placement
                dtype=dtype
            )
            
            # Handle cases where official might be a tuple (some transformers versions)
            if isinstance(official, tuple):
                official = official[0]

            instance = cls(official_model=official)
                
            print(f"[Qwen3TTS] Load complete.")
            return instance
        except Exception as e:
            err_str = str(e)
            print(f"[Qwen3TTS] Failed to load model: {err_str}")
            if "is not a local folder" in err_str or "not a valid model" in err_str:
                print(f"[INFO] Model file not found locally and not available on Hugging Face Hub.")
                print(f"[INFO] To use local models, download them and place in: {model_path}")
            raise

    def to(self, device: str):
        """Delegate device movement to the official model's internal model."""
        if hasattr(self.official_model, 'model'):
            self.official_model.model.to(device)
        return self

    def generate_voice_clone(self, 
                             text: str, 
                             voice_clone_prompt: Any = None,
                             language: str = "Auto",
                             **kwargs) -> Tuple[List[np.ndarray], int]:
        """Delegates to the official library's generate_voice_clone."""
        # The official library expects voice_clone_prompt to be a List[VoiceClonePromptItem] 
        # or a specific dict. If it's a single prompt item (not in a list), it can fail.
        if voice_clone_prompt is not None:
            # Normalize to list if it's a single item (detected by lacking '__iter__')
            if not isinstance(voice_clone_prompt, (list, dict)):
                voice_clone_prompt = [voice_clone_prompt]
            
            # Ensure tensors are on the correct device
            target_device = self.official_model.device
                
            # Normalize EVERYTHING to a list of VoiceClonePromptItem for the official library
            # This avoids 'bool object is not subscriptable' errors in batch processing
            items_to_process = []
            if isinstance(voice_clone_prompt, list):
                items_to_process = voice_clone_prompt
            elif isinstance(voice_clone_prompt, dict):
                items_to_process = [voice_clone_prompt]
            else:
                items_to_process = [voice_clone_prompt]

            processed_prompts = []
            for item in items_to_process:
                print(f"[DEBUG] Normalizing prompt item type: {type(item)}")
                if isinstance(item, dict):
                    # Filter to only supported fields
                    valid_fields = {f.name for f in VoiceClonePromptItem.__dataclass_fields__.values()}
                    
                    # 1. Handle audio_values (raw audio) vs ref_spk_embedding (x-vector)
                    if 'audio_values' in item:
                        vals = item.get('audio_values')
                        # If audio_values is a long sequence (raw audio), it's NOT an embedding
                        if isinstance(vals, torch.Tensor) and vals.numel() > 4096:
                            print(f"[DEBUG] Detected raw audio in audio_values (size {vals.numel()}). Re-extracting via official method...")
                            import tempfile
                            import soundfile as sf
                            
                            try:
                                # Save to temp file and use official prompt creator
                                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                                    audio_np = vals.cpu().float().numpy().flatten()
                                    sf.write(tf.name, audio_np, 16000)
                                    temp_path = tf.name
                                
                                try:
                                    # Pre-emptive clear for re-extraction
                                    torch.cuda.empty_cache()
                                    
                                    # Create a clean prompt using official logic
                                    ref_text = item.get('ref_text') or ""
                                    x_vec_mode = True if not ref_text.strip() else item.get('x_vector_only_mode', True)
                                    
                                    # Use autocast to prevent Half/Float mismatch during official re-extraction
                                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16 if torch.cuda.is_available() else torch.float32):
                                        result = self.official_model.create_voice_clone_prompt(
                                            ref_audio=temp_path,
                                            ref_text=ref_text,
                                            x_vector_only_mode=x_vec_mode
                                        )
                                    
                                    # Handle case where official library returns a list
                                    clean_item = result[0] if isinstance(result, list) and len(result) > 0 else result
                                    
                                    # Update our item with the generated fields from the clean item
                                    for field_name in ['ref_spk_embedding', 'ref_code', 'ref_text', 'x_vector_only_mode', 'icl_mode']:
                                        if hasattr(clean_item, field_name):
                                            val = getattr(clean_item, field_name)
                                            if val is not None:
                                                item[field_name] = val
                                    
                                    print(f"[REPAIR] Asset optimized for high-speed synthesis.")
                                    
                                    # Post-repair clear
                                    torch.cuda.empty_cache()
                                    gc.collect()
                                    
                                except Exception as e:
                                    print(f"[ERROR] Re-extraction via official method failed: {e}")
                                finally:
                                    if os.path.exists(temp_path):
                                        os.unlink(temp_path)
                            except Exception as e:
                                print(f"[ERROR] Re-extraction via official method failed: {e}")
                                # Fallback to manual if possible, but the above is safer
                        
                        # Remove audio_values as it's not a field in VoiceClonePromptItem
                        item.pop('audio_values', None)

                    # 2. Legacy check: if ref_spk_embedding is still too large, it was probably wrongly mapped earlier
                    if 'ref_spk_embedding' in item:
                        emb = item['ref_spk_embedding']
                        if isinstance(emb, torch.Tensor) and emb.numel() > 4096:
                             print(f"[DEBUG] ref_spk_embedding seems to be raw audio (size {emb.numel()}). Fixing...")
                             # Repeat encoding logic or set to None to let it fail gracefully
                             # (Ideally we repeat the encoding if we can)
                    
                    # Ensure ALL mandatory fields for VoiceClonePromptItem are present
                    # This prevents 'missing positional argument' errors in the constructor
                    mandatory_fields = {
                        'ref_spk_embedding': None,
                        'ref_code': None,
                        'ref_text': '',
                        'x_vector_only_mode': True,
                        'icl_mode': False
                    }
                    
                    # Filter item for valid VoiceClonePromptItem fields
                    valid_fields = ['ref_spk_embedding', 'ref_code', 'ref_text', 'x_vector_only_mode', 'icl_mode']
                    item_kwargs = {k: v for k, v in item.items() if k in valid_fields}

                    for field, default in mandatory_fields.items():
                        if field not in item_kwargs or item_kwargs[field] is None:
                            item_kwargs[field] = default
                    
                    if item_kwargs['ref_spk_embedding'] is None:
                        print("[WARNING] VoiceClonePromptItem created without valid embedding.")

                    item = VoiceClonePromptItem(**item_kwargs)
                
                # Move tensors to correct device
                if hasattr(item, 'ref_spk_embedding') and item.ref_spk_embedding is not None:
                    if isinstance(item.ref_spk_embedding, list):
                        item.ref_spk_embedding = torch.tensor(item.ref_spk_embedding)
                    item.ref_spk_embedding = item.ref_spk_embedding.to(target_device)
                if hasattr(item, 'ref_code') and item.ref_code is not None:
                    if isinstance(item.ref_code, list):
                        item.ref_code = torch.tensor(item.ref_code)
                    item.ref_code = item.ref_code.to(target_device)
                processed_prompts.append(item)
            
            voice_clone_prompt = processed_prompts
            
            # Diagnostic for the first item
            if voice_clone_prompt and len(voice_clone_prompt) > 0:
                first = voice_clone_prompt[0]
                attrs = {f.name: str(getattr(first, f.name, "N/A"))[:50] for f in VoiceClonePromptItem.__dataclass_fields__.values()}
                print(f"[DEBUG] Final call prompt attributes: {attrs}")

        return self.official_model.generate_voice_clone(
            text=text,
            voice_clone_prompt=voice_clone_prompt,
            language=language,
            **kwargs
        )

    def generate_voice_design(self, 
                              text: str, 
                              instruct: str,
                              language: str = "Auto",
                              **kwargs) -> Tuple[List[np.ndarray], int]:
        """Delegates to the official library's generate_voice_design."""
        return self.official_model.generate_voice_design(
            text=text,
            instruct=instruct,
            language=language,
            **kwargs
        )

    def generate_custom_voice(self, 
                              text: str, 
                              speaker: str,
                              language: str = "Auto",
                              **kwargs) -> Tuple[List[np.ndarray], int]:
        """Delegates to the official library's generate_custom_voice."""
        return self.official_model.generate_custom_voice(
            text=text,
            speaker=speaker,
            language=language,
            **kwargs
        )

    def create_voice_clone_prompt(self, audio_content: Optional[bytes] = None, **kwargs):
        """Delegates prompt creation to the official model, handling raw bytes via temp file if needed."""
        import tempfile
        import os
        
        # Map our internal 'transcript' to 'ref_text' if needed
        if 'transcript' in kwargs:
            kwargs['ref_text'] = kwargs.pop('transcript')
            
        # Enforce x_vector_only_mode if no ref_text is provided to avoid ICL errors
        if not kwargs.get('ref_text'):
            kwargs.setdefault('x_vector_only_mode', True)
        else:
            kwargs.setdefault('x_vector_only_mode', False)

        if audio_content is not None:
            # The official library expects 'ref_audio'
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tf.write(audio_content)
                temp_path = tf.name
            
            try:
                return self.official_model.create_voice_clone_prompt(ref_audio=temp_path, **kwargs)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        return self.official_model.create_voice_clone_prompt(**kwargs)
