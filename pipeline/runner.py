"""Pipeline runner for executing Pipecat pipelines."""
import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger
from pipecat.pipeline.runner import PipelineRunner

from pipeline.builder import PipelineBuilder
from models.call_session import CallSession, CallState
from app.constants import EVENT_CALL_STARTED, EVENT_CALL_ENDED
from app.middleware import track_call_started, track_call_ended


async def run_bot(
    websocket,
    stream_sid: str,
    call_sid: str,
    language: str = "en-IN",
    system_prompt: Optional[str] = None
) -> CallSession:
    """
    Run the voice bot pipeline for a call.
    
    This is the main entry point for executing a voice conversation.
    
    Args:
        websocket: FastAPI WebSocket connection
        stream_sid: Twilio stream SID
        call_sid: Twilio call SID
        language: Language code
        system_prompt: Custom system prompt (optional)
        
    Returns:
        CallSession with analytics data
    """
    logger.info(f"[CHECKPOINT 0] Starting bot - call_sid={call_sid}, stream_sid={stream_sid}")
    
    # Create call session
    session = CallSession(
        call_sid=call_sid,
        stream_sid=stream_sid,
        language=language,
        state=CallState.ACTIVE
    )
    
    # Track analytics
    start_time = datetime.utcnow()
    track_call_started(language)
    
    try:
        # Build pipeline with real Stream SID from Twilio
        builder = PipelineBuilder(
            websocket=websocket,
            stream_sid=stream_sid,  # Real Stream SID extracted from Twilio's 'start' message
            language=language,
            system_prompt=system_prompt
        )
        
        pipeline, task, transport, services = builder.build()
        
        logger.info("[CHECKPOINT 3] Creating pipeline runner...")
        
        # Create runner
        runner = PipelineRunner()
        
        logger.info("[CHECKPOINT 4] Starting pipeline runner...")
        
        # Run pipeline (blocks until call ends)
        await runner.run(task)
        
        logger.info("[CHECKPOINT FINAL] Bot finished - call ended")
        
        # Update session state
        session.state = CallState.ENDED
        session.ended_at = datetime.utcnow()
        session.total_duration = (session.ended_at - start_time).total_seconds()
        track_call_ended(language, "completed")
        
    except asyncio.CancelledError:
        logger.info("Pipeline cancelled")
        session.state = CallState.ENDED
        session.ended_at = datetime.utcnow()
        track_call_ended(language, "cancelled")
        raise
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        session.state = CallState.ERROR
        session.ended_at = datetime.utcnow()
        session.metadata["error"] = str(e)
        track_call_ended(language, "error")
        
    finally:
        # Cleanup services
        logger.info("Cleaning up services...")
        for service in services:
            try:
                await service.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error for {service.__class__.__name__}: {e}")
        
        # Log analytics
        if session.ended_at:
            session.total_duration = (session.ended_at - start_time).total_seconds()
        
        logger.info(f"Call session ended: {session.to_analytics_dict()}")
    
    return session
