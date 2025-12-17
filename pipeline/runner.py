"""Clean pipeline runner using async build method."""
import asyncio
from datetime import datetime
from typing import Optional
from loguru import logger
from pipecat.pipeline.runner import PipelineRunner

from pipeline.builder import PipelineBuilder
from models.call_session import CallSession, CallState
# Removed unused event constants
from app.middleware import track_call_started, track_call_ended


# Removed create_bot_pipeline() - use run_bot() directly to avoid duplication


async def run_bot(
    websocket,
    stream_sid: str,
    call_sid: str,
    language: str,
    system_prompt: Optional[str] = None
) -> CallSession:
    """
    Run the voice bot pipeline for a call using built-in Pipecat services.
    
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
    logger.info(f"🚀 Starting bot - call_sid={call_sid}, stream_sid={stream_sid}")
    
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
    
    builder = None
    
    try:
        # Build pipeline with real Stream SID from Twilio
        builder = PipelineBuilder(
            websocket=websocket,
            stream_sid=stream_sid,
            language=language,
            system_prompt=system_prompt
        )
        
        # Build pipeline asynchronously (uses built-in services)
        logger.info("🔨 Building pipeline with built-in services...")
        pipeline, task = await builder.build()
        
        logger.info("🏃 Creating pipeline runner...")
        
        # Create runner
        runner = PipelineRunner()
        
        logger.info("✅ Pipeline ready, ensuring readiness...")
        
        # Ensure pipeline is ready before processing media frames
        await builder.ensure_pipeline_ready()
        
        logger.info("▶️ Starting pipeline runner...")
        
        # Run pipeline (blocks until call ends)
        await runner.run(task)
        
        logger.info("🏁 Bot finished - call ended")
        
        # Update session state
        session.state = CallState.ENDED
        session.ended_at = datetime.utcnow()
        session.total_duration = (session.ended_at - start_time).total_seconds()
        track_call_ended(language, "completed")
        
    except asyncio.CancelledError:
        logger.info("⚠️ Pipeline cancelled")
        session.state = CallState.ENDED
        session.ended_at = datetime.utcnow()
        track_call_ended(language, "cancelled")
        raise
        
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}", exc_info=True)
        session.state = CallState.ERROR
        session.ended_at = datetime.utcnow()
        session.metadata["error"] = str(e)
        track_call_ended(language, "error")
        
    finally:
        # Cleanup builder resources (aiohttp session, etc.)
        if builder:
            try:
                await builder.cleanup()
                logger.info("🧹 Builder cleanup completed")
            except Exception as e:
                logger.warning(f"⚠️ Builder cleanup error: {e}")
        
        # Log analytics
        if session.ended_at:
            session.total_duration = (session.ended_at - start_time).total_seconds()
        
        logger.info(f"📊 Call session ended: {session.to_analytics_dict()}")
    
    return session
