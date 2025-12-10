"""Call session models."""
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .language import LanguageCode


class CallState(str, Enum):
    """Call session states."""
    INITIATED = "initiated"
    LANGUAGE_SELECTION = "language_selection"
    ACTIVE = "active"
    ENDED = "ended"
    ERROR = "error"


class CallSession(BaseModel):
    """Call session data model."""
    call_sid: str = Field(..., description="Twilio call SID")
    stream_sid: Optional[str] = Field(None, description="Twilio stream SID")
    language: Optional[LanguageCode] = Field(None, description="Selected language")
    state: CallState = Field(default=CallState.INITIATED, description="Call state")
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    
    # Conversation tracking
    query_count: int = Field(default=0, description="Number of user queries")
    failed_stt_count: int = Field(default=0, description="Failed STT attempts")
    
    # Analytics
    total_duration: Optional[float] = None
    stt_calls: int = 0
    llm_calls: int = 0
    tts_calls: int = 0
    interruptions: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True
    
    def to_analytics_dict(self) -> Dict[str, Any]:
        """Convert to analytics dictionary."""
        return {
            "call_sid": self.call_sid,
            "stream_sid": self.stream_sid,
            "language": self.language,
            "state": self.state,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "query_count": self.query_count,
            "failed_stt_count": self.failed_stt_count,
            "total_duration": self.total_duration,
            "stt_calls": self.stt_calls,
            "llm_calls": self.llm_calls,
            "tts_calls": self.tts_calls,
            "interruptions": self.interruptions,
            "metadata": self.metadata
        }
