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
        logger.debug(f"📊 Initial audio RMS: {initial_rms}")
        
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


def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Resample audio from one sample rate to another using audioop.
    
    Args:
        audio_data: Input PCM audio bytes (16-bit)
        from_rate: Source sample rate
        to_rate: Target sample rate
        
    Returns:
        Resampled PCM audio bytes
    """
    if from_rate == to_rate:
        return audio_data
    
    # Use audioop for resampling (no scipy dependency)
    resampled, _ = audioop.ratecv(
        audio_data,
        AUDIO_SAMPLE_WIDTH,
        AUDIO_CHANNELS,
        from_rate,
        to_rate,
        None
    )
    
    return resampled


def resample_to_8khz_mono(wav_pcm: bytes, input_sample_rate: int, input_channels: int, sample_width: int = 2) -> bytes:
    """
    Resample PCM audio to 8kHz mono for Twilio.
    
    Args:
        wav_pcm: Raw PCM audio data (no WAV headers)
        input_sample_rate: Current sample rate (e.g., 22050, 24000, 16000)
        input_channels: Number of channels (1 or 2)
        sample_width: Bytes per sample (2 for 16-bit)
        
    Returns:
        PCM audio at 8kHz mono, 16-bit
    """
    try:
        pcm_data = wav_pcm
        
        # Convert stereo to mono if needed
        if input_channels == 2:
            pcm_data = audioop.tomono(pcm_data, sample_width, 1, 1)
            logger.debug(f"🔄 Converted stereo to mono")
        
        # Resample to 8kHz if needed (Twilio requirement)
        if input_sample_rate != 8000:
            pcm_data, _ = audioop.ratecv(pcm_data, sample_width, 1, input_sample_rate, 8000, None)
            logger.debug(f"🔄 Resampled from {input_sample_rate}Hz to 8000Hz")
        
        logger.info(f"✅ Resampled to 8kHz mono: {len(pcm_data)} bytes")
        return pcm_data
        
    except Exception as e:
        logger.error(f"❌ resample_to_8khz_mono error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return b""


def pcm_to_wav(pcm_audio: bytes, sample_rate: int, num_channels: int = AUDIO_CHANNELS) -> bytes:
    """
    Convert raw PCM audio to WAV format.
    
    Args:
        pcm_audio: Raw PCM audio bytes
        sample_rate: Sample rate
        num_channels: Number of channels
        
    Returns:
        WAV file bytes
    """
    wav_buffer = io.BytesIO()
    
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_audio)
    
    return wav_buffer.getvalue()


def wav_to_pcm(wav_audio: bytes) -> tuple[bytes, int, int]:
    """
    Extract PCM audio from WAV format.
    
    Args:
        wav_audio: WAV file bytes
        
    Returns:
        Tuple of (pcm_audio, sample_rate, num_channels)
    """
    wav_buffer = io.BytesIO(wav_audio)
    
    with wave.open(wav_buffer, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        num_channels = wav_file.getnchannels()
        pcm_audio = wav_file.readframes(wav_file.getnframes())
    
    return pcm_audio, sample_rate, num_channels


def save_debug_audio(
    audio_data: bytes,
    filename: str,
    sample_rate: int,
    audio_format: str = "pcm",
    debug_dir: str = "debug_audio"
) -> Optional[Path]:
    """
    Save audio data for debugging purposes.
    
    Args:
        audio_data: Audio bytes (PCM or mulaw)
        filename: Output filename (without extension)
        sample_rate: Sample rate
        audio_format: "pcm" or "mulaw"
        debug_dir: Debug directory path
        
    Returns:
        Path to saved file or None if failed
    """
    try:
        debug_path = Path(debug_dir)
        debug_path.mkdir(exist_ok=True)
        
        if audio_format == "pcm":
            # Save as WAV
            wav_data = pcm_to_wav(audio_data, sample_rate)
            file_path = debug_path / f"{filename}.wav"
            file_path.write_bytes(wav_data)
        else:
            # Save raw mulaw
            file_path = debug_path / f"{filename}.ulaw"
            file_path.write_bytes(audio_data)
        
        logger.debug(f"Saved debug audio: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Failed to save debug audio: {e}")
        return None


def calculate_audio_duration(audio_data: bytes, sample_rate: int, sample_width: int = AUDIO_SAMPLE_WIDTH) -> float:
    """
    Calculate audio duration in seconds.
    
    Args:
        audio_data: Audio bytes
        sample_rate: Sample rate
        sample_width: Sample width in bytes
        
    Returns:
        Duration in seconds
    """
    num_samples = len(audio_data) // sample_width
    return num_samples / sample_rate
