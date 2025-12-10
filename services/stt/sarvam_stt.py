"""Sarvam AI Speech-to-Text service implementation using Pipecat STTService."""
import asyncio
from typing import AsyncGenerator
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    ErrorFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
    InterruptionFrame
)
from pipecat.services.stt_service import STTService
from pipecat.processors.frame_processor import FrameDirection

from app.config import settings
from utils.audio_utils import save_debug_audio


class SarvamSTTService(STTService):
    """
    Sarvam AI STT service using Pipecat's built-in STTService base class.
    
    Follows Pipecat's standard pattern:
    - Extends STTService
    - Implements run_stt() to yield transcription frames
    - Base class handles all frame routing automatically
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "saarika:v2.5",
        language: str = "en-IN",
        sample_rate: int = 16000,
        **kwargs
    ):
        """
        Initialize Sarvam STT service.
        
        Args:
            api_key: Sarvam API key
            model: STT model name
            language: Language code
            sample_rate: Audio sample rate
        """
        # Initialize base STTService with audio passthrough enabled
        super().__init__(
            sample_rate=sample_rate,
            audio_passthrough=False,  # We don't need to pass audio downstream
            **kwargs
        )
        
        from services.sarvam_ai import SarvamAI
        
        self._sarvam = SarvamAI()
        self._language = language
        self._model = model
        
        # Audio buffering for batch STT
        self._audio_buffer: list[bytes] = []
        self._is_speaking = False
        
        logger.info(f"🎤 [STT] Initialized SarvamSTTService: language={language}, sample_rate={sample_rate}Hz")
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """
        Override to handle VAD events and buffer audio.
        
        For AudioRawFrame: super() calls our overridden process_audio_frame() for buffering.
        For VAD events: we handle them to control buffering state.
        """
        from pipecat.frames.frames import AudioRawFrame, StartFrame, MetricsFrame
        
        # Only log critical frames (VAD events and interruptions)
        # Skip: StartFrame, MetricsFrame, AudioRawFrame, UserSpeakingFrame, BotSpeakingFrame
        if isinstance(frame, (UserStartedSpeakingFrame, UserStoppedSpeakingFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame, InterruptionFrame)):
            logger.info(f"🔍 [STT] Received frame: {frame.__class__.__name__}")
        
        # Handle VAD events for buffering BEFORE calling super()
        if isinstance(frame, UserStartedSpeakingFrame):
            self._is_speaking = True
            self._audio_buffer.clear()
            logger.info("🎤 [STT] User started speaking - buffering audio")
            # Pass frame downstream and return
            await super().process_frame(frame, direction)
            return
        
        elif isinstance(frame, UserStoppedSpeakingFrame):
            if self._is_speaking:
                self._is_speaking = False
                logger.info(f"🛑 [STT] User stopped speaking - processing {len(self._audio_buffer)} audio chunks")
                
                # Combine buffered audio
                if self._audio_buffer:
                    combined_audio = b''.join(self._audio_buffer)
                    logger.info(f"📊 [STT] Combined audio buffer: {len(combined_audio)} bytes")
                    
                    # CRITICAL: Process transcription FIRST, then pass UserStoppedSpeakingFrame
                    # This ensures TranscriptionFrame arrives at aggregator BEFORE UserStoppedSpeakingFrame
                    # AWAIT the generator to ensure transcription completes before continuing
                    await self.process_generator(self.run_stt(combined_audio))
                    
                    # Clear buffer
                    self._audio_buffer.clear()
                    
                    logger.info("✅ [STT] Transcription complete, now passing UserStoppedSpeakingFrame")
            
            # ALWAYS pass UserStoppedSpeakingFrame downstream (whether we had audio or not)
            await super().process_frame(frame, direction)
            return  # Don't call super() again below
        
        # Call super() for ALL other frames (handles system frames + AudioRawFrame processing)
        # For AudioRawFrame: super() will call our overridden process_audio_frame()
        # For other frames: super() will push them downstream
        await super().process_frame(frame, direction)
    
    async def process_audio_frame(self, frame, direction):
        """
        Override to buffer audio instead of processing immediately.
        
        The base STTService calls this for every AudioRawFrame.
        We buffer the audio and only process when VAD says user stopped speaking.
        """
        # Log first audio frame to confirm audio is flowing
        if not hasattr(self, '_first_audio_logged'):
            self._first_audio_logged = True
            logger.info(f"🎵 [STT] First audio frame received: {len(frame.audio)} bytes")
        
        if self._is_speaking and frame.audio:
            self._audio_buffer.append(frame.audio)
            # Removed noisy debug logging
        
        # Don't call super() - we handle audio ourselves
        # Pass through audio if needed
        if self._audio_passthrough:
            await self.push_frame(frame, direction)
    
    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        """
        Run speech-to-text on batched audio data.
        
        This is called manually after we've buffered audio between
        UserStartedSpeaking and UserStoppedSpeaking events.
        
        Args:
            audio: Combined PCM audio bytes to transcribe
            
        Yields:
            TranscriptionFrame with transcribed text
        """
        try:
            # Check minimum audio size
            MIN_AUDIO_SIZE = 19200  # ~0.6s at 16kHz
            
            if len(audio) < MIN_AUDIO_SIZE:
                logger.warning(f"🔇 [STT] Audio too small: {len(audio)} bytes (minimum: {MIN_AUDIO_SIZE} bytes)")
                return
            
            logger.info(f"📊 [STT] Processing audio: {len(audio)} bytes")
            
            # Convert PCM to WAV
            import io
            import wave
            
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(audio)
            
            wav_data = wav_io.getvalue()
            logger.info(f"✅ [STT] Created WAV file: {len(wav_data)} bytes at {self._sample_rate}Hz")
            
            # Save debug audio if enabled
            if settings.SAVE_DEBUG_AUDIO:
                save_debug_audio(
                    audio,
                    f"stt_input_{asyncio.get_event_loop().time()}",
                    self._sample_rate,
                    audio_format="pcm",
                    debug_dir=settings.DEBUG_AUDIO_DIR
                )
            
            # Call Sarvam STT API
            transcription, detected_lang = await self._sarvam.speech_to_text(
                wav_data,
                language=self._language,
                retry_count=2,
                timeout=15
            )
            
            if transcription and transcription.strip():
                logger.info("=" * 80)
                logger.info("🎯 [CHECKPOINT 8] STT TRANSCRIPTION SUCCESS!")
                logger.info(f"👤 User said: {transcription}")
                logger.info("=" * 80)
                
                # Yield TranscriptionFrame - base class will handle pushing it downstream
                yield TranscriptionFrame(
                    text=transcription,
                    user_id=self._user_id,
                    timestamp=asyncio.get_event_loop().time()
                )
            else:
                logger.warning("🔇 [STT] No speech detected in audio buffer")
                
        except Exception as e:
            logger.error(f"❌ [STT] Error processing audio: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield ErrorFrame(error=str(e))
    
    async def cleanup(self):
        """Cleanup resources."""
        await self._sarvam.close()
        logger.debug("[STT] Cleanup complete")
