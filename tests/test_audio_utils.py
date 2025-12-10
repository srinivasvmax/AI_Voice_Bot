"""Tests for audio utilities."""
import pytest
from utils.audio_utils import (
    mulaw_to_pcm,
    pcm_to_mulaw,
    resample_audio,
    resample_to_8khz_mono
)


def test_mulaw_to_pcm():
    """Test mulaw to PCM conversion."""
    # Create sample mulaw data (silence)
    mulaw_data = b'\xff' * 160
    
    # Convert to PCM
    pcm_data = mulaw_to_pcm(mulaw_data, target_sample_rate=16000)
    
    # Check output
    assert isinstance(pcm_data, bytes)
    assert len(pcm_data) > len(mulaw_data)


def test_pcm_to_mulaw():
    """Test PCM to mulaw conversion."""
    # Create sample PCM data (silence)
    pcm_data = b'\x00\x00' * 160
    
    # Convert to mulaw
    mulaw_data = pcm_to_mulaw(pcm_data, source_sample_rate=8000)
    
    # Check output
    assert isinstance(mulaw_data, bytes)
    assert len(mulaw_data) < len(pcm_data)


def test_resample_audio():
    """Test audio resampling."""
    # Create sample PCM data
    pcm_data = b'\x00\x00' * 1600  # 1600 samples at 16kHz = 0.1s
    
    # Resample from 16kHz to 8kHz
    resampled = resample_audio(pcm_data, from_rate=16000, to_rate=8000)
    
    # Check output
    assert isinstance(resampled, bytes)
    assert len(resampled) < len(pcm_data)


def test_resample_to_8khz_mono():
    """Test forced resampling to 8kHz mono."""
    # Create sample PCM data
    pcm_data = b'\x00\x00' * 1600
    
    # Resample to 8kHz mono
    resampled = resample_to_8khz_mono(pcm_data, source_rate=16000, num_channels=1)
    
    # Check output
    assert isinstance(resampled, bytes)
