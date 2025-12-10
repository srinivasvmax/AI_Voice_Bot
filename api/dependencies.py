"""Dependency injection for API routes."""
from typing import Optional, Dict
from models.call_session import CallSession
from services.session_store import get_session_store


async def get_session(call_sid: str) -> Optional[CallSession]:
    """Get call session by SID."""
    store = get_session_store()
    return await store.get(call_sid)


async def store_session(session: CallSession):
    """Store call session."""
    store = get_session_store()
    await store.set(session)


async def remove_session(call_sid: str):
    """Remove call session."""
    store = get_session_store()
    await store.delete(call_sid)


async def get_all_sessions() -> Dict[str, CallSession]:
    """Get all active sessions."""
    store = get_session_store()
    return await store.get_all()
