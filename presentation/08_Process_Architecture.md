# How Parrot-AI Works

- **Phase 1 (Acquisition):** Audio resampled to 16kHz & transcribed.
- **Phase 2 (Inference):** Qwen Encoder extracts speaker identity; Transformer Decoder predicts acoustic tokens.
- **Phase 3 (Streaming):** Server-Sent Events (SSE) push live progress to the UI.
- **Phase 4 (Assembly):** Audio chunks are concatenated with 300ms conversational pauses and peak-normalized to -1dB.

---
**Visual Suggestion:**
*Paste your "Proposed Method Diagram" (Figure 1) or "Neural TTS Architecture" (Figure 3) here.*
