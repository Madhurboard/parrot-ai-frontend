# 🦜 Parrot AI - System Documentation Report

This report provides a comprehensive overview of the **Parrot AI Voice Cloning** system. It covers architecture, machine learning logic, and system integrations.

## 📁 Documentation Modules

1. **[Architecture Overview](./architecture_overview.md)**
   - High-level system design.
   - Core components and their roles.
   - Overall infrastructure layout.

2. **[Engine & Inference Deep Dive](./engine_and_inference.md)**
   - Detailed Qwen3-TTS logic.
   - Voice cloning pipeline flowchart.
   - Audio processing and optimization techniques.

3. **[API & System Integration](./api_and_integration.md)**
   - API endpoint specifications.
   - Supabase storage and database flows.
   - Authentication and persistence sequences.

## 🚀 Key Highlights

- **Next-Gen Model**: Built on **Qwen3-TTS-12Hz-1.7B-Base**, leveraging the latest advancements in speech synthesis.
- **Real-time Experience**: Implements **Server-Sent Events (SSE)** to provide a responsive, live feedback loop during audio generation.
- **SaaS Ready**: Fully integrated with **Supabase** for user management, cloud storage, and database persistence.
- **Hybrid Tiering**: Features a robust `ModelManager` that can switch between different model variants for different use cases (Cloning, Design, Preset).

---
*This report was generated for the Parrot AI project by Antigravity.*
