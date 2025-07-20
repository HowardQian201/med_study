"""
FastAPI Redis Session Management

This module provides Redis-based session management for FastAPI applications.
It includes middleware for automatic session handling and a session manager class
for easy session access in endpoints.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import secrets
from typing import Any, Dict, Optional

# Import database functions for session management
from ..database import (
    create_session, get_session_data, update_session_data, 
    delete_session, extend_session_ttl, clear_redis_session_content,
)


class RedisSessionMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for Redis session management."""
    
    def __init__(self, app, session_cookie_name: str = "session_id", session_ttl_hours: int = 1):
        super().__init__(app)
        self.session_cookie_name = session_cookie_name
        self.session_ttl_hours = session_ttl_hours
    
    async def dispatch(self, request: Request, call_next):
        # Load session before request
        session_id = request.cookies.get(self.session_cookie_name)
        session_data = {}
        
        if session_id:
            result = get_session_data(session_id)
            if result["success"]:
                session_data = result["data"]
                # Extend session TTL on access
                extend_session_ttl(session_id, self.session_ttl_hours)
            else:
                # Session expired or doesn't exist
                session_id = None
        
        # Store session data in request state
        request.state.session_id = session_id
        request.state.session_data = session_data
        request.state.session_modified = False
        
        # Process request
        response = await call_next(request)
        
        # Save session after request if modified
        if request.state.session_modified:
            if request.state.session_id and request.state.session_data:
                # Update existing session
                update_session_data(request.state.session_id, request.state.session_data, self.session_ttl_hours)
            elif not request.state.session_id and request.state.session_data:
                # Create new session
                new_session_id = secrets.token_urlsafe(32)
                create_result = create_session(new_session_id, request.state.session_data, self.session_ttl_hours)
                if create_result["success"]:
                    request.state.session_id = new_session_id
        
        # Set session cookie if we have a session
        if request.state.session_id:
            response.set_cookie(
                self.session_cookie_name,
                request.state.session_id,
                max_age=self.session_ttl_hours * 3600,  # Convert hours to seconds
                secure=True,
                httponly=True,
                samesite='lax'
            )
        
        return response


class SessionManager:
    """Session manager class for easy session access in FastAPI endpoints."""
    
    def __init__(self, request: Request):
        self.request = request
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get session value."""
        return self.request.state.session_data.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get session value with bracket notation."""
        return self.request.state.session_data[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set session value with bracket notation."""
        self.request.state.session_data[key] = value
        self.request.state.session_modified = True
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in session."""
        return key in self.request.state.session_data
    
    def pop(self, key: str, default: Any = None) -> Any:
        """Remove and return session value."""
        self.request.state.session_modified = True
        return self.request.state.session_data.pop(key, default)
    
    def clear(self) -> None:
        """Clear all session data."""
        if self.request.state.session_id:
            delete_session(self.request.state.session_id)
            self.request.state.session_id = None
        self.request.state.session_data = {}
        self.request.state.session_modified = True
    
    def update(self, data: Dict[str, Any]) -> None:
        """Update session data with dict."""
        self.request.state.session_data.update(data)
        self.request.state.session_modified = True
    
    def clear_content(self) -> bool:
        """Clear session content while preserving user auth."""
        if self.request.state.session_id:
            result = clear_redis_session_content(self.request.state.session_id)
            if result.get("success"):
                # Reload local session data to reflect the change
                self.request.state.session_data = result.get("data", {})
                # Note: We don't set session_modified = True here because
                # the Redis update is handled by clear_redis_session_content
                return True
        return False
    
    @property
    def session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return getattr(self.request.state, 'session_id', None)
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get all session data."""
        return getattr(self.request.state, 'session_data', {})


# Dependency function to get session manager
def get_session(request: Request) -> SessionManager:
    """FastAPI dependency to get session manager."""
    return SessionManager(request)
