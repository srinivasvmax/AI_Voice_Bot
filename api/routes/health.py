"""Health check and analytics routes."""
from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

from api.dependencies import get_all_sessions
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        Health status and system info
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": "production" if not settings.DEBUG else "development"
    }


@router.get("/analytics")
async def get_analytics() -> Dict[str, Any]:
    """
    Get analytics for all calls.
    
    Returns:
        Analytics data for all sessions
    """
    sessions = get_all_sessions()
    
    # Calculate aggregate stats
    total_calls = len(sessions)
    active_calls = sum(1 for s in sessions.values() if s.state == "active")
    total_queries = sum(s.query_count for s in sessions.values())
    
    # Language distribution
    language_dist = {}
    for session in sessions.values():
        lang = session.language or "unknown"
        language_dist[lang] = language_dist.get(lang, 0) + 1
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": {
            "total_calls": total_calls,
            "active_calls": active_calls,
            "total_queries": total_queries
        },
        "language_distribution": language_dist,
        "sessions": [s.to_analytics_dict() for s in sessions.values()]
    }


@router.get("/analytics/{call_sid}")
async def get_call_analytics(call_sid: str) -> Dict[str, Any]:
    """
    Get analytics for a specific call.
    
    Args:
        call_sid: Twilio call SID
        
    Returns:
        Analytics data for the call
    """
    sessions = get_all_sessions()
    session = sessions.get(call_sid)
    
    if not session:
        return {
            "error": "Call not found",
            "call_sid": call_sid
        }
    
    return session.to_analytics_dict()
