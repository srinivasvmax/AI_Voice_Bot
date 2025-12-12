"""Standalone Voice Activity Detection service for audio pipelines.

This service provides a complete VAD solution that can be used independently
or integrated into audio processing pipelines. It uses the Silero VAD model
for accurate voice activity detection.
"""
import asyncio
from typing import Optional, Callable, Awaitable
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
    StartFrame,
    EndFrame,
    CancelFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.audio.vad.vad_analyzer import VADParams

from .silero_vad import SileroVADAnalyzer


class VADService(FrameProcessor):
    """Standalone Voice Activity Detection service.
    
    Processes audio frames and emits VAD start/stop events based on voice activity
    detection using the Silero VAD model. Can be used as a standalone service or
    integrated into audio processing pipelines.
    
    Features:
    - Real-time voice activity detection
    - Configurable detection thresholds and timing
    - Event callbacks for voice start/stop
    - Audio buffering and state management
    - Support for 8kHz and 16kHz sample rates
    
    Example::
        vad = VADService(
            sample_rate=16000,
            params=VADParams(
                confidence_threshold=0.6,
                start_secs=0.2,
                stop_secs=0.8
            )
        )
        
        # Register event callbacks
        @vad.event_handler("on_voice_started")
        async def on_voice_started():
            print("Voice activity started!")
            
        @vad.event_handler("on_voice_stopped") 
        async def on_voice_stopped():
            print("Voice activity stopped!")
    """
    
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        params: Optional[VADParams] = None,
        pass_through_audio: bool = True,
        **kwargs
    ):
        """Initialize the VAD service.
        
        Args:
            sample_rate: Audio sample rate (8000 or 16000 Hz).
            params: VAD parameters for detection thresholds and timing.
            pass_through_audio: Whether to pass audio frames downstream. Defaults to True.
            **kwargs: Additional arguments passed to FrameProcessor.
        """
        super().__init__(**kwargs)
        
        self._sample_rate = sample_rate
        self._pass_through_audio = pass_through_audio
        
        # Default VAD parameters if not provided
        if params is None:
            params = VADParams(
                confidence=0.5,
                start_secs=0.2,
                stop_secs=0.8
            )
        
        # Initialize Silero VAD analyzer
        try:
            self._vad_analyzer = SileroVADAnalyzer(
                sample_rate=sample_rate,
                params=params
            )
            logger.info(f"🎤 [VAD] Initialized Silero VAD: sample_rate={sample_rate}Hz, threshold={params.confidence}")
        except Exception as e:
            logger.error(f"🎤 [VAD] Failed to initialize Silero VAD: {e}")
            raise
        
        # VAD state management
        self._is_voice_active = False
        self._voice_start_time = None
        self._voice_stop_time = None
        self._last_confidence = 0.0
        
        # Audio buffering for frame size requirements
        self._audio_buffer = bytearray()
        self._frames_required = self._vad_analyzer.num_frames_required()
        self._bytes_per_frame = 2  # 16-bit audio
        self._buffer_size_bytes = self._frames_required * self._bytes_per_frame
        
        # Event handlers
        self._register_event_handler("on_voice_started")
        self._register_event_handler("on_voice_stopped")
        self._register_event_handler("on_voice_confidence")
        
        logger.debug(f"🎤 [VAD] Buffer size: {self._buffer_size_bytes} bytes ({self._frames_required} frames)")
    
    async def start(self, frame: StartFrame):
        """Start the VAD service."""
        await super().start(frame)
        logger.info("🎤 [VAD] Service started")
    
    async def stop(self, frame: EndFrame):
        """Stop the VAD service."""
        await super().stop(frame)
        if self._is_voice_active:
            await self._handle_voice_stop()
        logger.info("🎤 [VAD] Service stopped")
    
    async def cancel(self, frame: CancelFrame):
        """Cancel the VAD service."""
        await super().cancel(frame)
        if self._is_voice_active:
            await self._handle_voice_stop()
        logger.info("🎤 [VAD] Service cancelled")
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frames."""
        await super().process_frame(frame, direction)
        
        if isinstance(frame, AudioRawFrame):
            await self._process_audio_frame(frame)
        else:
            # Pass through non-audio frames
            await self.push_frame(frame, direction)
    
    async def _process_audio_frame(self, frame: AudioRawFrame):
        """Process an audio frame through VAD analysis."""
        try:
            # Add audio data to buffer
            self._audio_buffer.extend(frame.audio)
            
            # Process complete chunks
            while len(self._audio_buffer) >= self._buffer_size_bytes:
                # Extract chunk for VAD analysis
                chunk = bytes(self._audio_buffer[:self._buffer_size_bytes])
                self._audio_buffer = self._audio_buffer[self._buffer_size_bytes:]
                
                # Analyze voice activity
                confidence = self._vad_analyzer.voice_confidence(chunk)
                self._last_confidence = confidence
                
                # Emit confidence event
                await self._call_event_handler("on_voice_confidence", confidence)
                
                # Handle voice state transitions
                await self._handle_voice_state(confidence)
                
                logger.debug(f"🎤 [VAD] Confidence: {confidence:.3f}, Active: {self._is_voice_active}")
            
            # Pass through audio frame if enabled
            if self._pass_through_audio:
                await self.push_frame(frame)
                
        except Exception as e:
            logger.error(f"🎤 [VAD] Error processing audio frame: {e}")
            # Pass through frame even on error
            if self._pass_through_audio:
                await self.push_frame(frame)
    
    async def _handle_voice_state(self, confidence: float):
        """Handle voice activity state transitions based on confidence."""
        current_time = asyncio.get_event_loop().time()
        threshold = self._vad_analyzer._params.confidence
        
        if confidence >= threshold:
            # Voice detected
            if not self._is_voice_active:
                # Check if we should start voice activity
                if self._voice_start_time is None:
                    self._voice_start_time = current_time
                elif current_time - self._voice_start_time >= self._vad_analyzer._params.start_secs:
                    await self._handle_voice_start()
            else:
                # Voice is active, reset stop timer
                self._voice_stop_time = None
        else:
            # No voice detected
            if self._is_voice_active:
                # Check if we should stop voice activity
                if self._voice_stop_time is None:
                    self._voice_stop_time = current_time
                elif current_time - self._voice_stop_time >= self._vad_analyzer._params.stop_secs:
                    await self._handle_voice_stop()
            else:
                # No voice, reset start timer
                self._voice_start_time = None
    
    async def _handle_voice_start(self):
        """Handle voice activity start."""
        if not self._is_voice_active:
            self._is_voice_active = True
            self._voice_start_time = None
            self._voice_stop_time = None
            
            logger.info("🎤 [VAD] Voice activity STARTED")
            
            # Emit VAD start frame
            await self.push_frame(VADUserStartedSpeakingFrame())
            
            # Call event handler
            await self._call_event_handler("on_voice_started")
    
    async def _handle_voice_stop(self):
        """Handle voice activity stop."""
        if self._is_voice_active:
            self._is_voice_active = False
            self._voice_start_time = None
            self._voice_stop_time = None
            
            logger.info("🎤 [VAD] Voice activity STOPPED")
            
            # Emit VAD stop frame
            await self.push_frame(VADUserStoppedSpeakingFrame())
            
            # Call event handler
            await self._call_event_handler("on_voice_stopped")
    
    def get_current_confidence(self) -> float:
        """Get the last calculated voice confidence score.
        
        Returns:
            Voice confidence score between 0.0 and 1.0.
        """
        return self._last_confidence
    
    def is_voice_active(self) -> bool:
        """Check if voice activity is currently detected.
        
        Returns:
            True if voice is currently active, False otherwise.
        """
        return self._is_voice_active
    
    def get_vad_params(self) -> VADParams:
        """Get the current VAD parameters.
        
        Returns:
            Current VAD parameters.
        """
        return self._vad_analyzer._params
    
    def update_vad_params(self, params: VADParams):
        """Update VAD parameters.
        
        Args:
            params: New VAD parameters to apply.
        """
        self._vad_analyzer._params = params
        logger.info(f"🎤 [VAD] Updated parameters: threshold={params.confidence}, "
                   f"start={params.start_secs}s, stop={params.stop_secs}s")
    
    async def reset_state(self):
        """Reset VAD state and clear buffers."""
        if self._is_voice_active:
            await self._handle_voice_stop()
        
        self._audio_buffer.clear()
        self._voice_start_time = None
        self._voice_stop_time = None
        self._last_confidence = 0.0
        
        # Reset VAD model state
        self._vad_analyzer._model.reset_states()
        
        logger.info("🎤 [VAD] State reset")


# Convenience function for quick VAD setup
def create_vad_service(
    sample_rate: int = 16000,
    confidence_threshold: float = 0.5,
    start_secs: float = 0.2,
    stop_secs: float = 0.8,
    pass_through_audio: bool = True
) -> VADService:
    """Create a VAD service with common parameters.
    
    Args:
        sample_rate: Audio sample rate (8000 or 16000 Hz).
        confidence_threshold: Voice confidence threshold (0.0 to 1.0).
        start_secs: Seconds of voice needed to trigger start.
        stop_secs: Seconds of silence needed to trigger stop.
        pass_through_audio: Whether to pass audio frames downstream.
        
    Returns:
        Configured VAD service instance.
    """
    params = VADParams(
        confidence=confidence_threshold,
        start_secs=start_secs,
        stop_secs=stop_secs
    )
    
    return VADService(
        sample_rate=sample_rate,
        params=params,
        pass_through_audio=pass_through_audio
    )