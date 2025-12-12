"""Simple in-memory session storage."""
from typing import Optional, Dict
from loguru import logger

from models.call_session import CallSession


class SessionStore:
    """Simple in-memory session storage."""
    
    def __init__(self):
        self._memory_store: Dict[str, CallSession] = {}
        logger.info("📦 SessionStore using in-memory storage")
    
    async def get(self, call_sid: str) -> Optional[CallSession]:
        """Get session by call SID."""
        return self._memory_store.get(call_sid)
    
    async def set(self, session: CallSession):
        """Store session."""
        self._memory_store[session.call_sid] = session
        logger.debug(f"Stored session {session.call_sid}")
    
    async def delete(self, call_sid: str):
        """Delete session."""
        self._memory_store.pop(call_sid, None)
        logger.debug(f"Deleted session {call_sid}")
    
    async def get_all(self) -> Dict[str, CallSession]:
        """Get all active sessions."""
        return self._memory_store.copy()
    
    async def close(self):
        """No-op for in-memory store."""
        pass


# Global session store instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get or create global session store instance."""
    global _session_store
    
    if _session_store is None:
        _session_store = SessionStore()
    
    return _session_store
