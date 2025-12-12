"""
HTTP-based Sarvam AI Text-to-Speech Service for Pipecat 0.0.97
Follows the official TTSService pattern from Pipecat docs.
"""

import aiohttp
import base64
from typing import Optional
from loguru import logger

from pipecat.frames.frames import (
    TTSAudioRawFrame,
)
from pipecat.services.tts_service import TTSService


class SarvamTTSProcessor(TTSService):
    """HTTP Sarvam TTS following Pipecat 0.0.97 TTSService pattern."""

    def __init__(self, *, api_key: str, voice: str = "bulbul:v2", sample_rate: int = 8000, 
                 frame_duration_ms: int = 20, fallback_chunk_size: int = 1024, 
                 api_base_url: str = "https://api.sarvam.ai", api_endpoint: str = "/text-to-speech", **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)  # TTSService requires sample_rate
        
        # WORKAROUND: Ensure _FrameProcessor__process_queue is initialized
        # This fixes the Pipecat 0.0.97 compatibility issue
        if not hasattr(self, '_FrameProcessor__process_queue'):
            import asyncio
            self._FrameProcessor__process_queue = asyncio.Queue()
            logger.debug("🔧 [TTS] Applied _FrameProcessor__process_queue workaround")
        self.api_key = api_key
        self.voice = voice
        # Store sample rate explicitly (parent class might not set it correctly)
        self._sample_rate = sample_rate
        self.set_model_name(voice)  # Set model name for metrics
        # Audio chunking parameters - now configurable
        self.frame_duration_ms = frame_duration_ms
        self.fallback_chunk_size = fallback_chunk_size
        self.bytes_per_sample = 2    # 16-bit PCM (this should remain hardcoded)
        # API configuration - now configurable
        self.api_base_url = api_base_url.rstrip('/')
        self.api_endpoint = api_endpoint
        logger.info(f"🔊 [SARVAM TTS] Initialized with voice: {voice}, sample_rate: {sample_rate}")
        logger.debug(f"🔊 [SARVAM TTS] Chunking params: frame_duration_ms={self.frame_duration_ms}, bytes_per_sample={self.bytes_per_sample}")
        logger.debug(f"🔊 [SARVAM TTS] API: {self.api_base_url}{self.api_endpoint}")
    
    @property
    def sample_rate(self):
        """Get sample rate, using our stored value if parent class doesn't set it."""
        return getattr(self, '_sample_rate', 8000)

    async def run_tts(self, text: str):
        """Generate TTS audio for the given text.
        
        This is the main method that TTSService calls when it receives text.
        
        Args:
            text: The text to synthesize to speech.
            
        Yields:
            TTSAudioRawFrame: Audio frames containing synthesized speech.
        """
        logger.info("🚨 [TTS] ===== RUN_TTS CALLED =====")
        logger.info(f"🔊 [SARVAM TTS] Synthesizing: {text[:50]!r}")
        logger.info(f"🔊 [SARVAM TTS] Full text length: {len(text)} characters")
        
        # Get full TTS audio bytes via HTTP
        audio_bytes = await self._fetch_sarvam_tts(text)

        # If we got audio, chunk it into multiple frames for lower latency
        if audio_bytes:
            # Strip WAV header if present (Pipecat expects raw PCM)
            pcm_data = self._strip_wav_header(audio_bytes)
            
            # Chunk audio to multiple TTSAudioRawFrames for lower latency
            chunk_size = int(self.sample_rate * self.frame_duration_ms / 1000) * self.bytes_per_sample
            
            # Debug chunk size calculation
            logger.info(f"🔊 [SARVAM TTS] Chunk calculation: sample_rate={self.sample_rate}, frame_duration_ms={self.frame_duration_ms}, bytes_per_sample={self.bytes_per_sample}, chunk_size={chunk_size}")
            
            # Ensure chunk_size is not zero
            if chunk_size <= 0:
                chunk_size = self.fallback_chunk_size  # Use configurable fallback
                logger.warning(f"🔊 [SARVAM TTS] Chunk size was 0, using fallback: {chunk_size}")
            
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i+chunk_size]
                if chunk:  # Only yield non-empty chunks
                    yield TTSAudioRawFrame(chunk, self.sample_rate, 1)  # Remove channels= parameter
        else:
            logger.warning("🔊 [SARVAM TTS] No audio generated")

    async def _fetch_sarvam_tts(self, text: str) -> Optional[bytes]:
        """HTTP call to Sarvam TTS API - handles JSON response with base64 audio."""
        url = f"{self.api_base_url}{self.api_endpoint}"
        payload = {
            "text": text,  # Use 'text' field, not 'input'
            "model": self.voice,  # Should be 'bulbul:v2' or 'bulbul:v3-beta'
            "format": "wav",
            "sample_rate": self.sample_rate
        }
        headers = {
            "api-subscription-key": self.api_key,  # Use api-subscription-key, not Bearer
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"[SARVAM TTS] API error {resp.status}: {await resp.text()}")
                        return None
                    
                    # Sarvam returns JSON containing base64-encoded audio(s)
                    resp_json = await resp.json()
                    
                    # Extract base64 audio from response
                    audios = resp_json.get("audios", [])
                    if not audios:
                        logger.error("[SARVAM TTS] No audio in response")
                        return None
                    
                    # Decode base64 audio
                    b64_audio = audios[0]  # First audio track
                    audio_bytes = base64.b64decode(b64_audio)
                    
                    return audio_bytes
                    
        except Exception as e:
            logger.error(f"[SARVAM TTS] HTTP Exception: {e}")
            return None
    
    def _strip_wav_header(self, data: bytes) -> bytes:
        """Strip WAV header if present, return raw PCM data."""
        if len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            # Standard WAV header is 44 bytes
            return data[44:]
        return data