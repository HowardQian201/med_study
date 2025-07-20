"""
FastAPI dependency functions
"""
from fastapi import Depends, HTTPException
from .redis import get_session, SessionManager

async def require_auth(session: SessionManager = Depends(get_session)) -> str:
    """
    Dependency that requires authentication and returns user_id (as a string UUID)
    Raises HTTPException(401) if user is not authenticated or user ID is invalid.
    """
    user_id = session.get('user_id')

    if not user_id or not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing user ID in session")
    
    # Add a basic check for UUID format if desired, though not strictly necessary for functionality
    # if not re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", user_id):
    #     raise HTTPException(status_code=401, detail="Unauthorized: Invalid user ID format in session")
    
    return user_id

