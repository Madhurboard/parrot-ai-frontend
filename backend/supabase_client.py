"""
Parrot AI — Supabase Client Helpers
Replaces SQLite + local filesystem with Supabase DB + Storage.
"""

import os
import io
from typing import Optional

from supabase import create_client, Client

from backend.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    VOICE_AUDIO_BUCKET,
    VOICE_EMBEDDING_BUCKET,
    CACHE_DIR,
)

# ---------------------------------------------------------------------------
# Singleton client (uses SERVICE key for full DB + Storage access)
# ---------------------------------------------------------------------------
_client: Optional[Client] = None


def get_supabase() -> Client:
    """Return a cached Supabase client."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set as environment variables."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ============================================================================
# Voice DB Operations
# ============================================================================


def insert_voice(
    user_id: str,
    voice_id: str,
    name: str,
    transcript: Optional[str],
    audio_path: str,
    embedding_path: Optional[str] = None,
) -> dict:
    """Insert a new voice record owned by *user_id*."""
    sb = get_supabase()
    data = {
        "id": voice_id,
        "user_id": user_id,
        "name": name,
        "transcript": transcript or "",
        "audio_path": audio_path,
        "embedding_path": embedding_path or "",
    }
    result = sb.table("voices").insert(data).execute()
    return result.data[0] if result.data else data


def list_voices(user_id: str) -> list[dict]:
    """Return all voices belonging to *user_id*, newest first."""
    sb = get_supabase()
    result = (
        sb.table("voices")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_voice(voice_id: str, user_id: str) -> Optional[dict]:
    """Fetch a single voice, scoped to the requesting user."""
    sb = get_supabase()
    result = (
        sb.table("voices")
        .select("*")
        .eq("id", voice_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_voice_record(voice_id: str, user_id: str) -> bool:
    """Delete a voice record (returns True if a row was actually removed)."""
    sb = get_supabase()
    result = (
        sb.table("voices")
        .delete()
        .eq("id", voice_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


def update_voice_embedding(voice_id: str, embedding_path: str) -> None:
    """Set the embedding_path column after the .pt file has been uploaded."""
    sb = get_supabase()
    sb.table("voices").update({"embedding_path": embedding_path}).eq(
        "id", voice_id
    ).execute()


# ============================================================================
# Storage Helpers
# ============================================================================


def upload_to_storage(bucket: str, remote_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload binary data to a Supabase Storage bucket. Returns the remote path."""
    sb = get_supabase()
    sb.storage.from_(bucket).upload(
        remote_path,
        data,
        file_options={"content-type": content_type},
    )
    return remote_path


def download_from_storage(bucket: str, remote_path: str) -> bytes:
    """Download a file from Supabase Storage and return raw bytes."""
    sb = get_supabase()
    return sb.storage.from_(bucket).download(remote_path)


def delete_from_storage(bucket: str, remote_path: str) -> None:
    """Remove a file from Supabase Storage."""
    sb = get_supabase()
    sb.storage.from_(bucket).remove([remote_path])


def download_to_cache(bucket: str, remote_path: str) -> str:
    """Download a file from Supabase Storage into the local cache directory.
    Returns the local file path. Skips download if the file already exists.
    """
    local_path = os.path.join(CACHE_DIR, remote_path.replace("/", os.sep))
    if os.path.exists(local_path):
        return local_path

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    data = download_from_storage(bucket, remote_path)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path
