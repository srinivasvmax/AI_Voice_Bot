"""Audio utilities for Twilio media stream processing

Twilio Media Streams Format Requirements:
- Sample rate: 8000 Hz (8kHz)
- Encoding: μ-law (mulaw)
- Channels: Mono (1 channel)
- Format: Raw mulaw bytes (NO WAV headers)
- Transport: Base64-encoded in WebSocket messages
"""
import io
import base64
import wave
import audioop
from pathlib import Path
from typing import Optional
from loguru import logger

from app.constants import (
    MULAW_SAMPLE_RATE,
    PCM_SAMPLE_RATE_STT,
    PCM_SAMPLE_RATE_TTS,
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_WIDTH
)


def decode_mulaw_base64(encoded_audio: str) -> bytes:
    """
    Decode base64-encoded mulaw audio.
    
    Args:
        encoded_audio: Base64-encoded mulaw audio string
        
    Returns:
        Raw mulaw audio bytes
    """
    return base64.b64decode(encoded_audio)


def encode_mulaw_base64(mulaw_audio: bytes) -> str:
    """
    Encode mulaw audio to base64 string.
    
    Args:
        mulaw_audio: Raw mulaw audio bytes
        
    Returns:
        Base64-encoded string
    """
    return base64.b64encode(mulaw_audio).decode('utf-8')


def mulaw_to_wav(mulaw_data: bytes, target_rate: int = 16000, apply_noise_reduction: bool = True) -> bytes:
    """
    Convert mulaw audio to WAV format with optional noise reduction.
    
    Args:
        mulaw_data: mulaw encoded audio
        target_rate: target sample rate (16000 for better quality with Sarvam AI)
        apply_noise_reduction: apply basic noise reduction
        
    Returns:
        WAV file bytes
    """
    try:
        # Convert mulaw to linear PCM
        pcm_data = audioop.ulaw2lin(mulaw_data, 2)
        
        # Calculate initial RMS for diagnostics
        initial_rms = audioop.rms(pcm_data, 2)
        # logger.debug(f"📊 Initial audio RMS: {initial_rms}")  # Disabled to reduce log spam
        
        # Basic noise reduction: apply a simple noise gate
        if apply_noise_reduction:
            # If audio is moderately quiet, amplify it
            if 300 < initial_rms < 800:
                try:
                    # Amplify quiet audio (1.5x boost for moderate, 2x for very quiet)
                    boost_factor = 2.0 if initial_rms < 500 else 1.5
                    pcm_data = audioop.mul(pcm_data, 2, boost_factor)
                    new_rms = audioop.rms(pcm_data, 2)
                    logger.info(f"🔊 Amplified audio: {initial_rms} → {new_rms} (boost: {boost_factor}x)")
                except audioop.error as e:
                    logger.warning(f"⚠️ Amplification failed: {e}")
            
            # Apply simple high-pass filter by removing DC offset
            # This helps reduce low-frequency rumble/noise
            try:
                pcm_data = audioop.bias(pcm_data, 2, 0)
            except audioop.error:
                pass
        
        # Resample from 8kHz to 16kHz for better STT quality
        if target_rate != 8000:
            pcm_data, _ = audioop.ratecv(pcm_data, 2, 1, 8000, target_rate, None)
            logger.debug(f"🔄 Resampled to {target_rate}Hz")
        
        # Create WAV file
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(target_rate)
            wav_file.writeframes(pcm_data)
        
        wav_bytes = wav_io.getvalue()
        duration_secs = len(mulaw_data) / 8000.0
        logger.info(f"✅ Converted mulaw to WAV: {len(wav_bytes)} bytes at {target_rate}Hz ({duration_secs:.2f}s)")
        
        return wav_bytes
        
    except Exception as e:
        logger.error(f"❌ mulaw_to_wav error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return b""


def mulaw_to_pcm(mulaw_audio: bytes, target_sample_rate: int = PCM_SAMPLE_RATE_STT) -> bytes:
    """
    Convert mulaw audio to PCM format with optional resampling.
    
    Args:
        mulaw_audio: Raw mulaw audio bytes (8kHz)
        target_sample_rate: Target PCM sample rate (default: 16kHz for STT)
        
    Returns:
        PCM audio bytes at target sample rate
    """
    # Decode mulaw to PCM (16-bit)
    pcm_audio = audioop.ulaw2lin(mulaw_audio, AUDIO_SAMPLE_WIDTH)
    
    # Resample if needed
    if target_sample_rate != MULAW_SAMPLE_RATE:
        pcm_audio, _ = audioop.ratecv(
            pcm_audio,
            AUDIO_SAMPLE_WIDTH,
            AUDIO_CHANNELS,
            MULAW_SAMPLE_RATE,
            target_sample_rate,
            None
        )
    
    return pcm_audio


def wav_to_mulaw(wav_data: bytes) -> bytes:
    """
    Convert WAV to mulaw format for Twilio (8kHz, mono, raw mulaw).
    
    Twilio requires:
    - 8kHz sample rate
    - Mono channel
    - Raw mulaw encoding (no WAV headers)
    
    Args:
        wav_data: WAV file bytes
        
    Returns:
        Raw mulaw audio bytes
    """
    try:
        # Parse WAV file
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, 'rb') as wav_file:
                pcm_data = wav_file.readframes(wav_file.getnframes())
                sample_width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                framerate = wav_file.getframerate()
        
        logger.info(f"📊 Input WAV: {framerate}Hz, {channels}ch, {sample_width*8}bit")
        
        # Convert stereo to mono if needed
        if channels == 2:
            pcm_data = audioop.tomono(pcm_data, sample_width, 1, 1)
            logger.info(f"🔄 Converted stereo to mono")
        
        # Resample to 8kHz if needed (Twilio requirement)
        if framerate != 8000:
            pcm_data, _ = audioop.ratecv(pcm_data, sample_width, 1, framerate, 8000, None)
            logger.info(f"🔄 Resampled from {framerate}Hz to 8000Hz")
        
        # Convert PCM to mulaw (raw, no headers)
        mulaw_data = audioop.lin2ulaw(pcm_data, sample_width)
        logger.info(f"✅ Converted to raw mulaw: {len(mulaw_data)} bytes (8kHz mono)")
        
        return mulaw_data
        
    except Exception as e:
        logger.error(f"❌ wav_to_mulaw error: {e}")
        return b""


def pcm_to_mulaw(pcm_audio: bytes, source_sample_rate: int = PCM_SAMPLE_RATE_TTS) -> bytes:
    """
    Convert PCM audio to mulaw format with optional resampling.
    
    Args:
        pcm_audio: PCM audio bytes
        source_sample_rate: Source PCM sample rate
        
    Returns:
        Mulaw audio bytes at 8kHz
    """
    # Resample to 8kHz if needed
    if source_sample_rate != MULAW_SAMPLE_RATE:
        pcm_audio, _ = audioop.ratecv(
            pcm_audio,
            AUDIO_SAMPLE_WIDTH,
            AUDIO_CHANNELS,
            source_sample_rate,
            MULAW_SAMPLE_RATE,
            None
        )
    
    # Encode PCM to mulaw
    mulaw_audio = audioop.lin2ulaw(pcm_audio, AUDIO_SAMPLE_WIDTH)
    
    return mulaw_audio



