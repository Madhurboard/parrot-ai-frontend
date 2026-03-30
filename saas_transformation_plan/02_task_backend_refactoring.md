# Task 2: Backend Architecture Refactor

## Objective
Update the existing FastAPI application (`backend.py`) to serve as a stateless GPU microservice that connects securely to Supabase.

## Sub-Tasks

1. **Dependency Updates**
   - Add `supabase`, `python-jose` (or `PyJWT`) to `requirements.txt` for handling Supabase API interactions and JWT validation.

2. **Authentication Middleware**
   - Create an API middleware or FastAPI Dependency that extracts the `Bearer` token from the request header.
   - Validate the JWT against the Supabase JWT secret to verify the user identity (`user_id`).
   - Reject unauthenticated requests with HTTP 401.

3. **Database Migration (from SQLite to Supabase)**
   - Delete all `sqlite3` logic (`init_db`, `get_db`).
   - Replace with the Supabase Python Client (e.g. `supabase.table('voices').select('*').eq('user_id', current_user_id).execute()`).

4. **Storage Migration (from Local FS to Supabase Storage)**
   - **Voice Creation (`/api/voices` POST)**:
     - Receive audio upload, run Whisper transcription (if needed).
     - Run Qwen TTS profile creation to generate the `.pt` embedding.
     - Upload both the Audio sequence and the `.pt` tensor to Supabase Storage (`voices-audio` and `voices-embeddings` buckets) under `/{user_id}/...`.
     - Insert a record into the `voices` table with paths.
   - **Generation (`/api/generate-stream`)**:
     - Receive `voice_id` and text.
     - Verify ownership of `voice_id` via Supabase DB.
     - Check if the `.pt` embedding exists in local Redis/Cache path. If not, download from Supabase Storage.
     - Run inference and stream SSE events and audio buffer back to the client as currently implemented.

5. **Dockerization for GPU Instances**
   - Create a `Dockerfile`:
     ```dockerfile
     FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04
     # Install python 3.10+, pip etc...
     # Install python dependencies from requirements.txt
     COPY . /app
     WORKDIR /app
     CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
     ```

## Definition of Done
- Local SQLite and local filesystem storage are completely removed.
- Endpoints are secured with JWT checking.
- Code successfully handles fetching/storing blobs to Supabase.
- Dockerfile is tested locally.
