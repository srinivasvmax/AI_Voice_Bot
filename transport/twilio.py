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
    stream_sid: str,  # ✅ Now required - must be extracted from Twilio first
    language: str = None
) -> FastAPIWebsocketTransport:
    """
    Create and configure Twilio WebSocket transport.
    
    Args:
        websocket: FastAPI WebSocket connection
        stream_sid: Twilio stream SID (REQUIRED - extracted from Twilio start message)
        language: Language code for VAD
        
    Returns:
        Configured FastAPIWebsocketTransport
        
    Note:
        The stream_sid MUST be extracted from Twilio's start message before creating
        the transport. This ensures audio frames are sent to the correct Twilio stream.
    """
    logger.info(f"Creating Twilio transport: stream_sid={stream_sid}, language={language}")
    
    # VAD Configuration - Let STT service handle VAD instead of transport
    # The Sarvam STT service has built-in VAD that's more accurate
    from app.config import settings
    
    vad_analyzer = None
    if settings.VAD_ENABLED:
        vad_params = VADParams(
            confidence=settings.VAD_CONFIDENCE,
            start_secs=settings.VAD_START_SECS,
            stop_secs=settings.VAD_STOP_SECS,
            min_volume=settings.VAD_MIN_VOLUME
        )
        
        # Create VAD analyzer
        vad_analyzer = SileroVADAnalyzer(params=vad_params)
        logger.info(f"✅ Transport VAD configured: confidence={vad_params.confidence}, start={vad_params.start_secs}s, stop={vad_params.stop_secs}s, min_volume={vad_params.min_volume}")
    else:
        # Disable transport VAD to avoid conflict with STT service VAD
        vad_analyzer = None
        logger.info("✅ Transport VAD disabled - using STT service VAD")
    
    # Configure Twilio serializer
    # CRITICAL: Twilio sends mulaw at 8kHz, serializer decodes to PCM at 16kHz (Pipecat default)
    # Twilio expects mulaw at 8kHz, serializer encodes PCM to mulaw
    # ✅ FIXED: Pass stream_sid so serializer knows where to send audio
    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,  # ✅ Use extracted stream_sid for audio output
        params=TwilioFrameSerializer.InputParams(
            auto_hang_up=False  # Don't auto-hangup
        )
    )
    
    # Configure transport parameters
    transport_params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,  # Twilio uses raw mulaw
        vad_analyzer=vad_analyzer,
        audio_in_passthrough=True,  # Pass audio through to STT (new parameter name)
        serializer=serializer
    )
    
    # Create transport
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=transport_params
    )
    
    logger.info("Twilio transport created successfully")
    logger.info(f"🔧 Transport configured: audio_in={transport_params.audio_in_enabled}, audio_out={transport_params.audio_out_enabled}, vad={vad_analyzer is not None}")
    
    return transport
