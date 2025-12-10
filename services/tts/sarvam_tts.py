"""Sarvam AI Text-to-Speech service using Pipecat TTSService."""
import asyncio
from typing import AsyncGenerator
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TTSAudioRawFrame,
    ErrorFrame
)
from pipecat.services.tts_service import TTSService

from app.config import settings
from utils.audio_utils import wav_to_pcm, resample_to_8khz_mono, save_debug_audio


class SarvamTTSService(TTSService):
    """
    Sarvam AI TTS service using Pipecat's TTSService base class.
    
    Follows Pipecat's standard pattern:
    - Extends TTSService
    - Implements run_tts() to yield audio frames
    - Base class handles text aggregation automatically
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "bulbul:v2",
        voice: str = "anushka",
        language: str = "en-IN",
        target_sample_rate: int = 8000,
        **kwargs
    ):
        """
        Initialize Sarvam TTS service.
        
        Args:
            api_key: Sarvam API key
            model: TTS model name
            voice: Voice name
            language: Language code
            target_sample_rate: Target sample rate (8kHz for Twilio)
        """
        # Initialize base TTSService
        # CRITICAL: Pass minimal parameters to avoid internal queue issues
        super().__init__(
            sample_rate=target_sample_rate,
            **kwargs
        )
        
        from services.sarvam_ai import SarvamAI
        
        self._sarvam = SarvamAI()
        self._language = language
        self._model = model
        self._voice = voice
        
        logger.info(f"🔊 [TTS] Initialized SarvamTTSService: language={language}, target_rate={target_sample_rate}Hz")
    
    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """
        Synthesize speech from text.
        
        This is called by the base TTSService after text aggregation.
        
        Args:
            text: Aggregated text to synthesize
            
        Yields:
            TTSAudioRawFrame with synthesized audio
        """
        try:
            if not text or not text.strip():
                logger.warning("[TTS] Empty text received")
                return
            
            logger.info(f"[TTS] Synthesizing: {text[:100]}...")
            
            # Call Sarvam TTS API
            wav_audio = await self._sarvam.text_to_speech(
                text,
                language=self._language,
                retry_count=2,
                timeout=20
            )
            
            if wav_audio:
                # Extract PCM from WAV
                pcm_audio, sample_rate, num_channels = wav_to_pcm(wav_audio)
                
                logger.debug(f"[TTS] Received audio: {len(pcm_audio)} bytes, {sample_rate}Hz, {num_channels}ch")
                
                # Force resample to 8kHz mono (critical for Twilio)
                pcm_8k = resample_to_8khz_mono(pcm_audio, sample_rate, num_channels)
                
                logger.debug(f"[TTS] Resampled to 8kHz mono: {len(pcm_8k)} bytes")
                
                # Save debug audio if enabled
                if settings.SAVE_DEBUG_AUDIO:
                    save_debug_audio(
                        pcm_8k,
                        f"tts_output_{asyncio.get_event_loop().time()}",
                        self._sample_rate,
                        audio_format="pcm",
                        debug_dir=settings.DEBUG_AUDIO_DIR
                    )
                
                # Yield TTSAudioRawFrame
                logger.info(f"🔊 [TTS] Yielding audio frame: {len(pcm_8k)} bytes at {self._sample_rate}Hz")
                yield TTSAudioRawFrame(
                    audio=pcm_8k,
                    sample_rate=self._sample_rate,
                    num_channels=1
                )
                
                logger.info(f"✅ [TTS] Audio frame sent to transport for: {text[:50]}...")
            else:
                logger.warning("[TTS] No audio generated")
                
        except Exception as e:
            logger.error(f"[TTS] Error synthesizing speech: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield ErrorFrame(error=str(e))
    
    async def cleanup(self):
        """Cleanup resources."""
        await self._sarvam.close()
        logger.debug("[TTS] Cleanup complete")
