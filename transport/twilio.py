"""Twilio WebSocket transport configuration."""
from fastapi import WebSocket
from loguru import logger
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams
)
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

from app.config import settings


def create_twilio_transport(
    websocket: WebSocket,
    stream_sid: str = None,
    language: str = "en-IN"
) -> FastAPIWebsocketTransport:
    """
    Create and configure Twilio WebSocket transport.
    
    Args:
        websocket: FastAPI WebSocket connection
        stream_sid: Twilio stream SID (optional - will be extracted from Twilio's start message)
        language: Language code for VAD
        
    Returns:
        Configured FastAPIWebsocketTransport
    """
    logger.info(f"Creating Twilio transport: stream_sid={stream_sid or 'will be extracted from Twilio'}, language={language}")
    
    # Configure VAD parameters
    # CRITICAL: stop_secs MUST be >= aggregation_timeout (0.8s)
    # This ensures UserStoppedSpeakingFrame comes AFTER the aggregation timeout
    vad_params = VADParams(
        confidence=0.8,  # Increased from 0.7 to reduce false positives
        start_secs=0.3,  # Increased from 0.2 to avoid noise triggering
        stop_secs=1.0,   # Increased from 0.8 to allow longer pauses
        min_volume=0.7   # Increased from 0.6 to filter out background noise
    )
    
    # Create VAD analyzer
    vad_analyzer = SileroVADAnalyzer(params=vad_params)
    
    logger.info(f"✅ VAD configured: confidence={vad_params.confidence}, start={vad_params.start_secs}s, stop={vad_params.stop_secs}s, min_volume={vad_params.min_volume}")
    
    # Configure Twilio serializer
    # CRITICAL: Twilio sends mulaw at 8kHz, serializer decodes to PCM at 16kHz (Pipecat default)
    # Twilio expects mulaw at 8kHz, serializer encodes PCM to mulaw
    # CRITICAL: We MUST pass the real stream_sid extracted from Twilio's 'start' message
    # The serializer uses this stream_sid in ALL outgoing messages
    # If we pass a wrong stream_sid, Twilio will reject messages with Error 31951
    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,  # Real Stream SID from Twilio's 'start' message
        params=TwilioFrameSerializer.InputParams(
            auto_hang_up=False  # Don't auto-hangup
        )
    )
    
    # Configure transport parameters
    transport_params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,  # Twilio uses raw mulaw
        vad_analyzer=vad_analyzer if settings.VAD_ENABLED else None,
        audio_in_passthrough=True,  # Pass audio through to STT (new parameter name)
        serializer=serializer
    )
    
    # Create transport
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=transport_params
    )
    
    logger.info("Twilio transport created successfully")
    
    return transport
