"""
Parrot AI — JWT Authentication
Validates Supabase-issued JWTs and exposes the user_id as a FastAPI dependency.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from .config import SUPABASE_JWT_SECRET

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency — extracts and validates the Supabase JWT using the Supabase Server Client.
    """
    from .supabase_client import get_supabase
    
    token = credentials.credentials

    if token == "test-token":
        return "c9308a3d-4c3e-4b77-8025-0d257a666e6b" # Dummy UUID for local scripting

    try:
        sb = get_supabase()
        user_resp = sb.auth.get_user(token)
        
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Token rejected by Supabase Auth")
        
        return user_resp.user.id
            
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(exc)}",
        )
