# Pipecat Framework Architecture Implementation

## Overview

This document explains how we've implemented the Pipecat 0.0.95 framework for our voice AI bot, using **built-in Pipecat services** with minimal custom code.

## Key Principle

**Use Pipecat's built-in services whenever possible.** Only implement custom processors when necessary (e.g., custom LLM integration).

---

## Pipeline Structure

### Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipecat Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. FastAPIWebsocketTransport.input()                       │
│     ├─ TwilioFrameSerializer (mulaw ↔ PCM conversion)      │
│     ├─ SileroVADAnalyzer (optional)                        │
│     └─ Outputs: AudioRawFrame @ 16kHz PCM                  │
│                                                              │
│  2. SarvamSTTService (Built-in Pipecat Service)            │
│     ├─ WebSocket connection to Sarvam API                  │
│     ├─ Model: saarika:v2.5                                 │
│     ├─ VAD signals enabled                                 │
│     └─ Outputs: TranscriptionFrame                         │
│                                                              │
│  3. LLMUserContextAggregator (Built-in)                    │
│     ├─ Accumulates user transcriptions                     │
│     ├─ Manages conversation context                        │
│     └─ Outputs: OpenAILLMContextFrame                      │
│                                                              │
│  4. SarvamLLMService (Custom Implementation)               │
│     ├─ HTTP connection to Sarvam API                       │
│     ├─ Model: sarvam-m                                     │
│     ├─ Optional RAG knowledge base                         │
│     └─ Outputs: LLMTextFrame(s)                            │
│                                                              │
│  5. LLMAssistantContextAggregator (Built-in, Patched)     │
│     ├─ Accumulates assistant responses                     │
│     ├─ Updates conversation context                        │
│     ├─ Forwards frames to TTS (patched behavior)           │
│     └─ Outputs: LLMTextFrame(s) to TTS                     │
│                                                              │
│  6. SarvamTTSService (Built-in Pipecat Service)            │
│     ├─ WebSocket connection to Sarvam API                  │
│     ├─ Voice: bulbul:v2                                    │
│     ├─ Sample rate: 8kHz                                   │
│     └─ Outputs: TTSAudioRawFrame @ 8kHz PCM                │
│                                                              │
│  7. FastAPIWebsocketTransport.output()                      │
│     ├─ TwilioFrameSerializer (PCM → mulaw conversion)      │
│     └─ Sends to Twilio via WebSocket                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Built-in Services Used

### 1. SarvamSTTService (Built-in)

**Location**: `pipecat.services.sarvam.stt.SarvamSTTService`

**Configuration**:
```python
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.transcriptions.language import Language

stt_service = SarvamSTTService(
    api_key=settings.SARVAM_API_KEY,
    model="saarika:v2.5",
    sample_rate=16000,
    params=SarvamSTTService.InputParams(
        language=Language.TE_IN,  # or HI_IN, EN_IN
        vad_signals=True,  # Enable VAD signals
        high_vad_sensitivity=False
    )
)
```

**Features**:
- WebSocket connection to Sarvam STT API
- Built-in VAD support
- Language-specific transcription
- Automatic reconnection
- Frame-based output

**Input**: `AudioRawFrame` (16kHz PCM)  
**Output**: `TranscriptionFrame`

---

### 2. SarvamTTSService (Built-in)

**Location**: `pipecat.services.sarvam.tts.SarvamTTSService`

**Configuration**:
```python
from pipecat.services.sarvam.tts import SarvamTTSService

tts_service = SarvamTTSService(
    api_key=settings.SARVAM_API_KEY,
    voice="bulbul:v2",
    sample_rate=8000
)
```

**Features**:
- WebSocket connection to Sarvam TTS API
- Streaming audio generation
- Multiple voice options
- Automatic reconnection
- Frame-based output

**Fallback**: `SarvamHttpTTSService` (HTTP-based, if WebSocket fails)

**Input**: `LLMTextFrame` or `TextFrame`  
**Output**: `TTSAudioRawFrame` (8kHz PCM)

---

### 3. LLMUserContextAggregator (Built-in)

**Location**: `pipecat.processors.aggregators.llm_response.LLMUserContextAggregator`

**Configuration**:
```python
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMUserAggregatorParams
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

# Shared context
context = OpenAILLMContext([
    {"role": "system", "content": "System prompt..."}
])

# User aggregator
user_aggregator = LLMUserContextAggregator(
    context=context,
    params=LLMUserAggregatorParams(
        aggregation_timeout=2.0  # Wait 2s for complete utterance
    )
)
```

**Features**:
- Accumulates user transcriptions
- Manages conversation context
- Timeout-based aggregation
- Handles interruptions

**Input**: `TranscriptionFrame`  
**Output**: `OpenAILLMContextFrame`

---

### 4. LLMAssistantContextAggregator (Built-in, Patched)

**Location**: `pipecat.processors.aggregators.llm_response.LLMAssistantContextAggregator`

**Configuration**:
```python
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantContextAggregator,
    LLMAssistantAggregatorParams
)

assistant_aggregator = LLMAssistantContextAggregator(
    context=context,  # Same shared context
    params=LLMAssistantAggregatorParams(
        expect_stripped_words=True
    )
)
```

**Features**:
- Accumulates assistant responses
- Updates conversation context
- Handles interruptions
- **Patched**: Forwards frames to TTS (see PIPECAT_PATCHES.md)

**Input**: `LLMTextFrame`, `LLMFullResponseStartFrame`, `LLMFullResponseEndFrame`  
**Output**: Frames forwarded to TTS + context updates

**Note**: This aggregator has been patched to forward frames downstream. See `docs/PIPECAT_PATCHES.md` for details.

---

## Custom Implementation

### SarvamLLMService (Custom)

**Location**: `services/llm/sarvam_llm.py`

**Why Custom?**:
- Sarvam AI doesn't have a built-in Pipecat service yet
- Need custom RAG integration
- Need specific message formatting

**Implementation**:
```python
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import (
    OpenAILLMContextFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    LLMFullResponseEndFrame,
    StartFrame
)

class SarvamLLMService(FrameProcessor):
    async def process_frame(self, frame, direction):
        # 1. Handle StartFrame (CRITICAL)
        if isinstance(frame, StartFrame):
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)  # Push downstream!
            return
        
        # 2. Handle context frame from aggregator
        if isinstance(frame, OpenAILLMContextFrame):
            messages = frame.context.messages
            await self._handle_messages(messages)
            return
        
        # 3. Everything else → base class
        await super().process_frame(frame, direction)
    
    async def _handle_messages(self, messages):
        # Generate response
        response = await self._call_llm(messages)
        
        # Stream frames
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        
        for sentence in split_sentences(response):
            await self.push_frame(LLMTextFrame(sentence), FrameDirection.DOWNSTREAM)
        
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
```

**Key Points**:
- Extends `FrameProcessor`
- Handles `OpenAILLMContextFrame` from user aggregator
- Emits `LLMTextFrame` for TTS
- **Must push StartFrame downstream** (critical for pipeline initialization)

---

## Transport Configuration

### FastAPIWebsocketTransport

**Configuration**:
```python
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams
)
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

# VAD (optional)
vad_analyzer = SileroVADAnalyzer(
    params=VADParams(
        confidence=0.85,
        start_secs=0.4,
        stop_secs=1.5,
        min_volume=0.75
    )
)

# Serializer (REQUIRED)
serializer = TwilioFrameSerializer(
    stream_sid=stream_sid,  # Extracted from Twilio's 'start' message
    params=TwilioFrameSerializer.InputParams(
        auto_hang_up=False
    )
)

# Transport
transport = FastAPIWebsocketTransport(
    websocket=websocket,
    params=FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,  # Twilio uses raw mulaw
        vad_analyzer=vad_analyzer,
        audio_in_passthrough=True,  # Pass audio to STT
        serializer=serializer
    )
)
```

**Critical**: The `stream_sid` must be extracted from Twilio's WebSocket 'start' message before creating the transport.

---

## WebSocket Lifecycle

### Proper Implementation

```python
@router.websocket("/media-stream/{language}")
async def handle_media_stream(websocket: WebSocket, language: str):
    # 1. Accept connection
    await websocket.accept()
    
    # 2. Read Twilio events until 'start'
    stream_sid = None
    call_sid = None
    
    while not stream_sid:
        msg = await websocket.receive_json()
        event = msg.get("event")
        
        if event == "connected":
            logger.info("Twilio connected")
            continue
        
        elif event == "start":
            stream_sid = msg.get("streamSid")
            call_sid = msg.get("start", {}).get("callSid")
            logger.info(f"Extracted: stream_sid={stream_sid}, call_sid={call_sid}")
            break
    
    # 3. Create pipeline with extracted IDs
    await run_bot(
        websocket=websocket,
        stream_sid=stream_sid,
        call_sid=call_sid,
        language=language
    )
```

**Why This Matters**:
- Twilio sends 'connected' then 'start' messages
- Stream SID is in the 'start' message
- Must extract before creating transport
- Transport needs stream SID for audio output

---

## Frame Types

### System Frames (High Priority)
- `StartFrame` - Initializes processors
- `CancelFrame` - Cancels ongoing operations
- `InterruptionFrame` - Handles interruptions

### Audio Frames
- `AudioRawFrame` - Raw PCM audio data
- `TTSAudioRawFrame` - TTS-generated audio

### Transcription Frames
- `TranscriptionFrame` - STT output
- `InterimTranscriptionFrame` - Partial transcription

### LLM Frames
- `OpenAILLMContextFrame` - Context for LLM
- `LLMMessagesFrame` - Messages for LLM
- `LLMFullResponseStartFrame` - Response starting
- `LLMTextFrame` - Response text
- `LLMFullResponseEndFrame` - Response complete

### VAD Frames
- `UserStartedSpeakingFrame` - User started speaking
- `UserStoppedSpeakingFrame` - User stopped speaking

---

## Context Management

### Shared Context Pattern

```python
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

# Create ONCE
context = OpenAILLMContext([
    {"role": "system", "content": "You are a helpful assistant."}
])

# Share with aggregators
user_aggregator = LLMUserContextAggregator(context=context, ...)
assistant_aggregator = LLMAssistantContextAggregator(context=context, ...)

# LLM reads from context (via OpenAILLMContextFrame)
# Aggregators modify context
```

**Rules**:
- Create context ONCE
- Share between aggregators
- LLM reads from `frame.context.messages`
- LLM does NOT mutate context directly
- Aggregators handle context updates

---

## Pipeline Execution

### Runner Pattern

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner

# Build pipeline
pipeline = Pipeline([
    transport.input(),
    stt_service,
    user_aggregator,
    llm_service,
    assistant_aggregator,
    tts_service,
    transport.output()
])

# Create task
task = PipelineTask(
    pipeline,
    params=PipelineParams(
        audio_in_sample_rate=8000,
        audio_out_sample_rate=8000,
        enable_metrics=True,
        enable_usage_metrics=True
    )
)

# Run (blocks until complete)
runner = PipelineRunner()
await runner.run(task)
```

---

## Best Practices

### ✅ DO

1. **Use built-in services** whenever available
2. **Extract stream_sid** from Twilio before creating transport
3. **Push StartFrame downstream** in custom processors
4. **Share context** between aggregators
5. **Handle CancelFrame** for interruptions
6. **Use asyncio.Task** for cancellable operations
7. **Call super().process_frame()** in custom processors
8. **Clean up resources** in cleanup() methods

### ❌ DON'T

1. **Don't create custom audio processors** (use TwilioFrameSerializer)
2. **Don't mutate context** in LLM service
3. **Don't block** in process_frame()
4. **Don't ignore CancelFrame**
5. **Don't create multiple contexts**
6. **Don't skip super().process_frame()** when needed
7. **Don't forget cleanup()**

---

## Patches Applied

See `docs/PIPECAT_PATCHES.md` for details on:
1. Frame processor race condition fix
2. Aggregator frame forwarding fix

---

## Verification Checklist

- ✅ Using built-in `SarvamSTTService`
- ✅ Using built-in `SarvamTTSService`
- ✅ Using built-in aggregators
- ✅ Stream SID extracted from Twilio
- ✅ StartFrame pushed downstream in custom LLM
- ✅ Context shared between aggregators
- ✅ TwilioFrameSerializer handles audio conversion
- ✅ WebSocket lifecycle properly handled
- ✅ Patches applied (see PIPECAT_PATCHES.md)

---

## References

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Sarvam AI Services](https://docs.sarvam.ai/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)

---

**Last Updated**: December 18, 2025  
**Pipecat Version**: 0.0.95  
**Status**: ✅ Production Ready

