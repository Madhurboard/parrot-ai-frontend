# Hardware & Deployment Architecture

## 1. Supabase (Database, Auth, Storage)
- **Authentication**: Supabase Auth configured with Google OAuth provider.
- **Database (PostgreSQL)**:
  - `profiles`: User information (tied to `auth.users`).
  - `voices`: Holds voice profiles (`id`, `user_id`, `name`, `transcript`, `audio_url`, `embedding_url`).
  - `generations` (optional): History of user generations.
- **Storage Buckets**:
  - `voice-samples`: Secure bucket for uploaded reference audio `.wav` files.
  - `voice-embeddings`: Secure bucket for generated Qwen-TTS `.pt` embeddings.
- **Security**: Row Level Security (RLS) policies ensuring users can only read/write their own voices and audio.

## 2. Backend (FastAPI + Qwen3-TTS) -> Render or Railway
- **Role**: AI Inference and heavy-lifting.
- **Changes from Current**:
  - Migrate from `sqlite3` to Supabase Python Client (PostgreSQL).
  - Migrate local `saved_voices/` directory to Supabase Storage.
  - Implement JWT middleware to protect endpoints (verify Supabase JWT).
  - Add logic to download/cache `.pt` embeddings from Supabase Storage prior to inference.
- **Deployment Strategy**: 
  - Dockerized using an NVIDIA CUDA base image (`nvidia/cuda:12.1.0-runtime-ubuntu22.04`).
  - Deployed on Railway or Render using their GPU tiers (e.g. Render GPU instances or Railway private GPUs).

## 3. Frontend (React / Next.js) -> Vercel
- **Role**: User-facing application.
- **Core Features**:
  - **Landing Page**: SaaS marketing features.
  - **Authentication**: Sign in with Google (Supabase Auth UI).
  - **Dashboard**: Fetch user voices from Supabase.
  - **Studio (Voice Generation)**: Select a voice, type text, and call the FastAPI backend to stream the SSE progress and audio output.
- **State Management**: React Query / Zustand for managing user state and fetched voices.
- **Deployment**: Vercel for edge-optimized static and serverless delivery.
