"""WebSocket route for media streaming."""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from pipeline.runner import run_bot, create_bot_pipeline
from api.dependencies import get_session, store_session, remove_session
from models.call_session import CallState

router = APIRouter(tags=["websocket"])


@router.get("/media-stream-test")
async def test_media_stream():
    """Test endpoint to verify media-stream route is accessible."""
    return {
        "status": "ok",
        "message": "Media stream endpoint is accessible",
        "websocket_url": "/media-stream/{language}"
    }


@router.websocket("/media-stream")
async def handle_media_stream_fallback(websocket: WebSocket):
    """
    Fallback route - language must be selected first.
    """
    await websocket.accept()
    logger.error("❌ WebSocket connected without language parameter - language selection required")
    await websocket.send_text('{"error": "Language selection required. Please select language first."}')
    await websocket.close()


@router.websocket("/media-stream/{language}")
async def handle_media_stream(
    websocket: WebSocket,
    language: str
):
    """
    Handle Twilio media stream WebSocket connection.
    
    ✅ FIX: Language passed via URL path (Twilio strips query params)
    ✅ FIX: WebSocket lifecycle - DO NOT consume messages manually
    Let Pipecat transport handle ALL WebSocket events
    
    This is where the real-time voice conversation happens.
    
    Args:
        websocket: WebSocket connection
        language: Selected language code from URL path
    """
    logger.info("=" * 80)
    logger.info("🔌 WebSocket CONNECTION ATTEMPT!")
    logger.info(f"🔌 Headers: {websocket.headers}")
    logger.info(f"🔌 Query params: {websocket.query_params}")
    logger.info("=" * 80)
    
    try:
        # Accept WebSocket connection
        await websocket.accept()
        
        logger.info("=" * 80)
        logger.info("✅ WebSocket ACCEPTED!")
        logger.info(f"🔌 Client: {websocket.client}")
        logger.info("=" * 80)
        
        # Get language from path parameter (passed via route)
        selected_language = language
        
        # CRITICAL: Extract stream_sid and call_sid from Twilio's 'start' message
        # Following the reference pattern: read messages until we get 'start'
        # Twilio sends: 1) {"event": "connected"} 2) {"event": "start", "streamSid": "...", ...}
        
        logger.info("🎬 Waiting for Twilio 'start' message to extract stream_sid...")
        
        stream_sid = None
        call_sid = None
        
        # Read messages until we get the 'start' event
        # This handles both 'connected' and 'start' messages
        while not stream_sid:
            msg = await websocket.receive_json()
            event = msg.get("event")
            
            logger.info(f"📨 Received Twilio event: {event}")
            
            if event == "connected":
                logger.info("✅ Twilio connection confirmed")
                continue
            
            elif event == "start":
                # Extract IDs from the start message
                stream_sid = msg.get("streamSid")
                call_sid = msg.get("start", {}).get("callSid")
                
                if not stream_sid or not call_sid:
                    raise ValueError(f"Missing stream_sid or call_sid in start message: {msg}")
                
                logger.info(f"✅ Extracted from Twilio: stream_sid={stream_sid}, call_sid={call_sid}")
                logger.debug(f"🎬 Full start message: {msg}")
                break
            
            else:
                logger.warning(f"⚠️ Unexpected Twilio event: {event}")
                # Continue reading in case there are other messages before 'start'
        
    except Exception as e:
        logger.error(f"❌ WebSocket setup error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    
    try:
        # Now that we have the real stream_sid and call_sid from Twilio,
        # we can create the transport with the correct IDs.
        # The transport will continue reading from the WebSocket (media frames).
        # We've already consumed the 'connected' and 'start' messages,
        # so the transport will only see 'media' and 'stop' messages.
        logger.info("=" * 80)
        logger.info(f"🤖 [CHECKPOINT 0] Starting bot with stream_sid={stream_sid}, call_sid={call_sid}")
        logger.info("=" * 80)
        
        # Create pipeline and wait for readiness before processing media frames
        from pipeline.runner import create_bot_pipeline
        import asyncio
        
        logger.info("🔧 Creating pipeline components...")
        builder, runner, task, session = await create_bot_pipeline(
            websocket=websocket,
            stream_sid=stream_sid,  # Real Stream SID extracted from Twilio's 'start' message
            call_sid=call_sid,      # Real Call SID extracted from Twilio's 'start' message
            language=selected_language
        )
        
        logger.info("⏳ Ensuring pipeline readiness before processing media frames...")
        
        # Start readiness check asynchronously
        asyncio.create_task(builder.ensure_pipeline_ready())
        
        # Wait for pipeline to be ready before allowing media frame processing
        try:
            await asyncio.wait_for(builder.pipeline_ready.wait(), timeout=5.0)
            logger.info("✅ Pipeline ready - safe to process Twilio media frames")
        except asyncio.TimeoutError:
            logger.error("❌ Pipeline not ready in time - cannot process Twilio media")
            raise
        
        # Now run the pipeline (this will process media frames)
        logger.info("🚀 Starting pipeline runner...")
        await runner.run(task)
        
        # Update session state
        from datetime import datetime
        from utils.analytics import track_call_ended
        session.state = CallState.ENDED
        session.ended_at = datetime.utcnow()
        track_call_ended(selected_language, "completed")
        
        # Store final session
        await store_session(session)
        
        logger.info("=" * 80)
        logger.info("🏁 [CHECKPOINT FINAL] Bot finished - call ended")
        logger.info("=" * 80)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for stream {stream_sid}")
        
    except asyncio.CancelledError:
        logger.info(f"WebSocket cancelled for stream {stream_sid}")
        
    except Exception as e:
        logger.error(f"❌ WebSocket error for stream {stream_sid}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        # Cleanup
        logger.info(f"Cleaning up WebSocket for stream {stream_sid}")
        
        if websocket.client_state.name == "CONNECTED":
            try:
                await websocket.close()
                logger.info("🔌 WebSocket closed")
            except Exception:
                pass
