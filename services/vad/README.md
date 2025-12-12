# Silero VAD Service

A standalone Voice Activity Detection (VAD) service using the Silero VAD model for accurate voice detection in audio streams.

## Features

- **High Accuracy**: Uses the pre-trained Silero VAD ONNX model
- **Real-time Processing**: Optimized for streaming audio applications
- **Configurable Parameters**: Adjustable thresholds and timing
- **Event-driven**: Callbacks for voice start/stop events
- **Multiple Presets**: Pre-configured settings for different use cases
- **Sample Rate Support**: 8kHz and 16kHz audio
- **Memory Efficient**: Automatic model state management

## Quick Start

```python
from services.vad import create_vad_service

# Create VAD service with defaults
vad = create_vad_service()

# Add event handlers
@vad.event_handler("on_voice_started")
async def voice_started():
    print("Voice detected!")

@vad.event_handler("on_voice_stopped") 
async def voice_stopped():
    print("Voice stopped!")

# Process audio
audio_frame = AudioRawFrame(audio_data, 16000, 1)
await vad.process_frame(audio_frame, None)
```

## Configuration Presets

Use predefined configurations for common scenarios:

```python
from services.vad import get_vad_config, create_vad_service

# Different presets for different use cases
presets = {
    "conversation": "Normal conversation flow",
    "dictation": "Voice typing/dictation", 
    "presentation": "Presentations with long pauses",
    "high_sensitivity": "Very responsive detection",
    "low_sensitivity": "Noisy environments"
}

# Create VAD with preset
vad_params = get_vad_config("conversation")
vad = create_vad_service(
    sample_rate=16000,
    **vad_params.__dict__
)
```

## Advanced Usage

### Custom Configuration

```python
from services.vad import VADService
from pipecat.audio.vad.vad_analyzer import VADParams

# Custom VAD parameters
params = VADParams(
    confidence_threshold=0.6,  # Voice confidence threshold (0.0-1.0)
    start_secs=0.2,           # Seconds of voice to trigger start
    stop_secs=0.8             # Seconds of silence to trigger stop
)

vad = VADService(
    sample_rate=16000,
    params=params,
    pass_through_audio=True
)
```

### Integration with Audio Pipeline

```python
# Example: VAD-gated STT processing
class VADGatedSTT:
    def __init__(self, stt_service):
        self.stt = stt_service
        self.vad = create_vad_service()
        self.collecting_audio = False
        self.audio_buffer = []
        
        @self.vad.event_handler("on_voice_started")
        async def start_collecting():
            self.collecting_audio = True
            self.audio_buffer.clear()
        
        @self.vad.event_handler("on_voice_stopped")
        async def process_collected():
            if self.audio_buffer:
                combined_audio = b''.join(self.audio_buffer)
                # Process through STT
                await self.stt.process_audio(combined_audio)
            self.collecting_audio = False
    
    async def process_audio(self, audio_data):
        # Process through VAD
        await self.vad.process_audio(audio_data)
        
        # Collect audio if voice is active
        if self.collecting_audio:
            self.audio_buffer.append(audio_data)
```

### Real-time Monitoring

```python
from services.vad import create_vad_service

class VADMonitor:
    def __init__(self):
        self.vad = create_vad_service(preset="conversation")
        self.voice_active = False
        
        @self.vad.event_handler("on_voice_confidence")
        async def show_confidence(confidence):
            # Visual confidence indicator
            bar = "█" * int(confidence * 20)
            print(f"[{bar:<20}] {confidence:.2f}")
    
    async def monitor_audio(self, audio_stream):
        async for audio_chunk in audio_stream:
            await self.vad.process_audio(audio_chunk)
```

## API Reference

### VADService

Main VAD service class for processing audio frames.

**Methods:**
- `process_frame(frame, direction)` - Process audio frame
- `is_voice_active()` - Check if voice is currently detected
- `get_current_confidence()` - Get last confidence score
- `update_vad_params(params)` - Update VAD parameters
- `reset_state()` - Reset VAD state and buffers

**Events:**
- `on_voice_started` - Voice activity started
- `on_voice_stopped` - Voice activity stopped  
- `on_voice_confidence(confidence)` - Confidence score updated

### SileroVADAnalyzer

Low-level VAD analyzer for direct audio processing.

**Methods:**
- `voice_confidence(buffer)` - Get confidence for audio buffer
- `set_sample_rate(rate)` - Set audio sample rate
- `num_frames_required()` - Get required frame count

### Configuration

**VADParams:**
- `confidence_threshold` (float): Voice detection threshold (0.0-1.0)
- `start_secs` (float): Seconds of voice needed to trigger start
- `stop_secs` (float): Seconds of silence needed to trigger stop

**Presets:**
- `VADPresets.CONVERSATION` - Natural conversation flow
- `VADPresets.DICTATION` - Voice typing/dictation
- `VADPresets.PRESENTATION` - Long pauses expected
- `VADPresets.HIGH_SENSITIVITY` - Very responsive
- `VADPresets.LOW_SENSITIVITY` - Noisy environments
- `VADPresets.BALANCED` - General purpose (default)

## Installation

```bash
# Install Pipecat with Silero VAD support
pip install pipecat-ai[silero]

# Or install ONNX runtime separately
pip install onnxruntime
```

## Performance Tips

1. **Sample Rate**: Use 16kHz for best accuracy, 8kHz for lower CPU usage
2. **Threshold Tuning**: Start with 0.5, adjust based on your audio quality
3. **Buffer Management**: Service automatically manages audio buffers
4. **Memory Usage**: Model state resets every 5 seconds to prevent memory growth
5. **CPU Usage**: Silero VAD is optimized for real-time processing

## Examples

See the `examples/` directory for complete usage examples:

- `simple_vad_usage.py` - Basic usage patterns
- `vad_example.py` - Comprehensive examples
- `vad_integration_example.py` - Integration with STT/TTS services

## Troubleshooting

**Common Issues:**

1. **"Unsupported sample rate"** - Use 8000 or 16000 Hz
2. **"Input audio chunk too short"** - Ensure minimum 512 frames (16kHz) or 256 frames (8kHz)
3. **High CPU usage** - Consider using 8kHz sample rate or adjusting processing frequency
4. **False positives** - Increase confidence threshold or use LOW_SENSITIVITY preset
5. **Missed voice** - Decrease confidence threshold or use HIGH_SENSITIVITY preset

**Debug Mode:**
```python
import logging
logging.getLogger("services.vad").setLevel(logging.DEBUG)
```

## License

This service uses the Silero VAD model which is available under MIT license.