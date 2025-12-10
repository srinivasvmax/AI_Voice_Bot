"""Production-grade session storage with Redis support."""
import json
from typing import Optional, Dict
from datetime import datetime, timedelta
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - using in-memory storage")

from models.call_session import CallSession
from app.config import settings


class SessionStore:
    """
    Session storage with Redis backend and in-memory fallback.
    
    Features:
    - Redis for production (persistent, distributed)
    - In-memory fallback for development
    - Automatic session expiration
    - JSON serialization
    """
    
    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = 3600):
        """
        Initialize session store.
        
        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
            ttl_seconds: Session TTL in seconds (default: 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        self.redis_client: Optional[redis.Redis] = None
        self._memory_store: Dict[str, CallSession] = {}
        self._use_redis = False
        
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                self._use_redis = True
                logger.info(f"✅ SessionStore initialized with Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect to Redis: {e}, using in-memory storage")
                self._use_redis = False
        else:
            logger.info("📦 SessionStore using in-memory storage")
    
    async def get(self, call_sid: str) -> Optional[CallSession]:
        """Get session by call SID."""
        try:
            if self._use_redis and self.redis_client:
                data = await self.redis_client.get(f"session:{call_sid}")
                if data:
                    session_dict = json.loads(data)
                    return CallSession(**session_dict)
                return None
            else:
                return self._memory_store.get(call_sid)
        except Exception as e:
            logger.error(f"Error getting session {call_sid}: {e}")
            return None
    
    async def set(self, session: CallSession):
        """Store session with TTL."""
        try:
            if self._use_redis and self.redis_client:
                key = f"session:{session.call_sid}"
                data = session.model_dump_json()
                await self.redis_client.setex(key, self.ttl_seconds, data)
                logger.debug(f"Stored session {session.call_sid} in Redis (TTL: {self.ttl_seconds}s)")
            else:
                self._memory_store[session.call_sid] = session
                logger.debug(f"Stored session {session.call_sid} in memory")
        except Exception as e:
            logger.error(f"Error storing session {session.call_sid}: {e}")
    
    async def delete(self, call_sid: str):
        """Delete session."""
        try:
            if self._use_redis and self.redis_client:
                await self.redis_client.delete(f"session:{call_sid}")
                logger.debug(f"Deleted session {call_sid} from Redis")
            else:
                self._memory_store.pop(call_sid, None)
                logger.debug(f"Deleted session {call_sid} from memory")
        except Exception as e:
            logger.error(f"Error deleting session {call_sid}: {e}")
    
    async def get_all(self) -> Dict[str, CallSession]:
        """Get all active sessions."""
        try:
            if self._use_redis and self.redis_client:
                sessions = {}
                async for key in self.redis_client.scan_iter("session:*"):
                    data = await self.redis_client.get(key)
                    if data:
                        session_dict = json.loads(data)
                        session = CallSession(**session_dict)
                        sessions[session.call_sid] = session
                return sessions
            else:
                return self._memory_store.copy()
        except Exception as e:
            logger.error(f"Error getting all sessions: {e}")
            return {}
    
    async def cleanup_expired(self):
        """Cleanup expired sessions (only for in-memory store)."""
        if not self._use_redis:
            now = datetime.utcnow()
            expired = []
            for call_sid, session in self._memory_store.items():
                if session.ended_at:
                    age = (now - session.ended_at).total_seconds()
                    if age > self.ttl_seconds:
                        expired.append(call_sid)
            
            for call_sid in expired:
                self._memory_store.pop(call_sid, None)
                logger.debug(f"Cleaned up expired session {call_sid}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✅ Redis connection closed")


# Global session store instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get or create global session store instance."""
    global _session_store
    
    if _session_store is None:
        redis_url = getattr(settings, 'REDIS_URL', None)
        _session_store = SessionStore(redis_url=redis_url)
    
    return _session_store
