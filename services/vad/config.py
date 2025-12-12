"""VAD service configuration presets."""

from pipecat.audio.vad.vad_analyzer import VADParams


class VADPresets:
    """Predefined VAD configuration presets for different use cases."""
    
    # High sensitivity - detects voice quickly, good for interactive applications
    HIGH_SENSITIVITY = VADParams(
        confidence_threshold=0.3,
        start_secs=0.1,
        stop_secs=0.5
    )
    
    # Balanced - good general purpose settings
    BALANCED = VADParams(
        confidence_threshold=0.5,
        start_secs=0.2,
        stop_secs=0.8
    )
    
    # Low sensitivity - more conservative, good for noisy environments
    LOW_SENSITIVITY = VADParams(
        confidence_threshold=0.7,
        start_secs=0.3,
        stop_secs=1.2
    )
    
    # Conversation mode - optimized for natural conversation flow
    CONVERSATION = VADParams(
        confidence_threshold=0.4,
        start_secs=0.15,
        stop_secs=1.0
    )
    
    # Presentation mode - longer pauses expected
    PRESENTATION = VADParams(
        confidence_threshold=0.6,
        start_secs=0.2,
        stop_secs=2.0
    )
    
    # Dictation mode - very sensitive, minimal delays
    DICTATION = VADParams(
        confidence_threshold=0.25,
        start_secs=0.05,
        stop_secs=0.3
    )


# Sample rate configurations
class SampleRateConfig:
    """Sample rate configurations for different quality levels."""
    
    # Standard quality - good for most applications
    STANDARD = 16000
    
    # Lower quality - for bandwidth-constrained applications
    LOW_QUALITY = 8000
    
    # Supported sample rates by Silero VAD
    SUPPORTED_RATES = [8000, 16000]


# Quick setup functions
def get_vad_config(preset_name: str = "balanced") -> VADParams:
    """Get VAD configuration by preset name.
    
    Args:
        preset_name: Name of the preset (case-insensitive).
            Options: "high_sensitivity", "balanced", "low_sensitivity", 
                    "conversation", "presentation", "dictation"
    
    Returns:
        VAD parameters for the specified preset.
    
    Raises:
        ValueError: If preset name is not recognized.
    """
    preset_map = {
        "high_sensitivity": VADPresets.HIGH_SENSITIVITY,
        "balanced": VADPresets.BALANCED,
        "low_sensitivity": VADPresets.LOW_SENSITIVITY,
        "conversation": VADPresets.CONVERSATION,
        "presentation": VADPresets.PRESENTATION,
        "dictation": VADPresets.DICTATION,
    }
    
    preset_key = preset_name.lower()
    if preset_key not in preset_map:
        available = ", ".join(preset_map.keys())
        raise ValueError(f"Unknown preset '{preset_name}'. Available presets: {available}")
    
    return preset_map[preset_key]


def validate_sample_rate(sample_rate: int) -> int:
    """Validate and return sample rate.
    
    Args:
        sample_rate: Sample rate to validate.
    
    Returns:
        Validated sample rate.
    
    Raises:
        ValueError: If sample rate is not supported.
    """
    if sample_rate not in SampleRateConfig.SUPPORTED_RATES:
        supported = ", ".join(map(str, SampleRateConfig.SUPPORTED_RATES))
        raise ValueError(f"Unsupported sample rate {sample_rate}. Supported rates: {supported}")
    
    return sample_rate