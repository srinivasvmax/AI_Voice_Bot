"""Tests for audio utilities."""
import pytest
from utils.audio_utils import (
    mulaw_to_pcm,
    pcm_to_mulaw,
    mulaw_to_wav,
    wav_to_mulaw
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


def test_mulaw_to_wav():
    """Test mulaw to WAV conversion."""
    # Create sample mulaw data
    mulaw_data = b'\xff' * 160
    
    # Convert to WAV
    wav_data = mulaw_to_wav(mulaw_data, target_rate=16000)
    
    # Check output
    assert isinstance(wav_data, bytes)
    assert len(wav_data) > len(mulaw_data)


def test_wav_to_mulaw():
    """Test WAV to mulaw conversion."""
    # Create a simple WAV file (this is a minimal test)
    mulaw_data = b'\xff' * 160
    wav_data = mulaw_to_wav(mulaw_data)
    
    # Convert back to mulaw
    result_mulaw = wav_to_mulaw(wav_data)
    
    # Check output
    assert isinstance(result_mulaw, bytes)
