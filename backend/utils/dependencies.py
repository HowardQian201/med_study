"""
FastAPI dependency functions
"""
from fastapi import Depends, HTTPException
from .redis import get_session, SessionManager

async def require_auth(session: SessionManager = Depends(get_session)) -> int:
    """
    Dependency that requires authentication and returns user_id
    Raises HTTPException(401) if user is not authenticated
    """
    user_id = session.get('user_id')

    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing user ID in session")
    
    return user_id

