import torch
import os
import io
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
        # Load the official model
        print(f"[Qwen3TTS] Loading local model: {model_path}...")
        official = OfficialQwen3TTSModel.from_pretrained(
            model_path,
            device_map="cuda", # Let Transformers handle all sub-module placement
            dtype=dtype
        )
        
        # Handle cases where official might be a tuple (some transformers versions)
        if isinstance(official, tuple):
            official = official[0]

        instance = cls(official_model=official)
            
        print(f"[Qwen3TTS] Load complete.")
        return instance

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
                            print(f"[DEBUG] Detected raw audio in audio_values (size {vals.numel()}). Needs encoding.")
                            # Attempt to extract speaker embedding using the model's encoder
                            try:
                                if hasattr(self.official_model, 'speaker_encoder'):
                                    print("[DEBUG] Using model.speaker_encoder to extract x-vector...")
                                    with torch.no_grad():
                                        # ECAPA-TDNN usually takes (batch, samples)
                                        # Ensure it's on the right device and dtype
                                        audio_input = vals.to(device=target_device, dtype=torch.float32).view(1, -1)
                                        spk_emb = self.official_model.speaker_encoder(audio_input)
                                        item['ref_spk_embedding'] = spk_emb
                                elif hasattr(self.official_model, 'model') and hasattr(self.official_model.model, 'speaker_encoder'):
                                    print("[DEBUG] Using model.model.speaker_encoder to extract x-vector...")
                                    with torch.no_grad():
                                        audio_input = vals.to(device=target_device, dtype=torch.float32).view(1, -1)
                                        spk_emb = self.official_model.model.speaker_encoder(audio_input)
                                        item['ref_spk_embedding'] = spk_emb
                                else:
                                    print("[WARNING] Could not find speaker_encoder. Model may fail.")
                                    # Fallback: if it's already mapped to ref_spk_embedding, we might have a problem
                            except Exception as e:
                                print(f"[ERROR] Speaker encoding failed: {e}")
                        
                        # Remove audio_values as it's not a field in VoiceClonePromptItem
                        item.pop('audio_values', None)

                    # 2. Legacy check: if ref_spk_embedding is still too large, it was probably wrongly mapped earlier
                    if 'ref_spk_embedding' in item:
                        emb = item['ref_spk_embedding']
                        if isinstance(emb, torch.Tensor) and emb.numel() > 4096:
                             print(f"[DEBUG] ref_spk_embedding seems to be raw audio (size {emb.numel()}). Fixing...")
                             # Repeat encoding logic or set to None to let it fail gracefully
                             # (Ideally we repeat the encoding if we can)
                    
                    item_kwargs = {k: v for k, v in item.items() if k in valid_fields}
                    
                    # Set mandatory fields if missing to avoid dataclass init errors
                    if 'ref_code' not in item_kwargs: item_kwargs['ref_code'] = None
                    if 'ref_spk_embedding' not in item_kwargs: 
                        # If we still don't have it, we might be in trouble unless the official model handles it
                        print("[WARNING] VoiceClonePromptItem missing 'ref_spk_embedding'")

                    item = VoiceClonePromptItem(**item_kwargs)
                
                # Final check for VoiceClonePromptItem consistency
                if hasattr(item, 'ref_text'):
                    rt = getattr(item, 'ref_text', None)
                    print(f"[DEBUG] Item ref_text: '{rt}'")
                    if not rt or rt == "None":
                        # Force x_vector_only_mode if ref_text is missing to avoid ICL errors
                        print("[DEBUG] Forcing x_vector_only_mode=True as ref_text is empty")
                        if hasattr(item, 'x_vector_only_mode'):
                            try:
                                item.x_vector_only_mode = True
                            except Exception:
                                pass
                        if hasattr(item, 'icl_mode'):
                            try:
                                item.icl_mode = False
                            except Exception:
                                pass
                    else:
                        print("[DEBUG] Keeping ICL mode as ref_text is present")
                        if hasattr(item, 'x_vector_only_mode'):
                            try:
                                item.x_vector_only_mode = False
                            except Exception:
                                pass
                        if hasattr(item, 'icl_mode'):
                            try:
                                item.icl_mode = True
                            except Exception:
                                pass
                
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
