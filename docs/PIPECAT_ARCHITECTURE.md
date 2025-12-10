# Pipecat Framework Architecture Implementation

## Overview

This document explains how we've properly implemented the Pipecat framework for our voice AI bot, following best practices and patterns from the official Pipecat documentation.

## Pipeline Structure

### Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipecat Pipeline                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. FastAPIWebsocketTransport.input()                       │
│     ↓ (AudioRawFrame @ 16kHz PCM)                          │
│     ↓ (UserStartedSpeakingFrame, UserStoppedSpeakingFrame) │
│                                                              │
│  2. SarvamSTTService (FrameProcessor)                       │
│     ↓ (TranscriptionFrame)                                  │
│                                                              │
│  3. LoggingUserAggregator (LLMUserContextAggregator)        │
│     ↓ (LLMMessagesFrame with context)                       │
│                                                              │
│  4. SarvamLLMService (FrameProcessor)                       │
│     ↓ (TextFrame)                                           │
│     ↓ (LLMFullResponseEndFrame)                             │
│                                                              │
│  5. LLMAssistantResponseAggregator                          │
│     ↓ (Updates shared context)                              │
│                                                              │
│  6. SarvamTTSService (FrameProcessor)                       │
│     ↓ (TTSAudioRawFrame @ 8kHz PCM)                        │
│                                                              │
│  7. FastAPIWebsocketTransport.output()                      │
│     ↓ (Sends to Twilio via WebSocket)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Pipecat Concepts

### 1. FrameProcessor Base Class

All custom processors extend `FrameProcessor`:

```python
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import Frame, FrameDirection

class SarvamSTTService(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Process frames
        pass
```

**Key Rules:**
- ✅ Always extend `FrameProcessor`
- ✅ Implement `process_frame(frame, direction)`
- ✅ Use `await self.push_frame(frame, direction)` to send frames downstream
- ✅ Call `await super().process_frame(frame, direction)` when appropriate

### 2. Frame Types

#### Input Frames (from upstream)
- `AudioRawFrame`: Raw PCM audio data
- `UserStartedSpeakingFrame`: VAD detected speech start
- `UserStoppedSpeakingFrame`: VAD detected speech end
- `TranscriptionFrame`: Transcribed text from STT
- `LLMMessagesFrame`: Messages for LLM processing
- `TextFrame`: Text from LLM
- `LLMFullResponseEndFrame`: LLM response complete
- `CancelFrame`: Cancel ongoing operations

#### Output Frames (to downstream)
- `TranscriptionFrame`: From STT service
- `LLMMessagesFrame`: From user aggregator
- `TextFrame`: From LLM service
- `TTSAudioRawFrame`: From TTS service
- `CancelFrame`: For interruptions

### 3. Frame Direction

```python
class FrameDirection(Enum):
    DOWNSTREAM = "downstream"  # Normal flow
    UPSTREAM = "upstream"      # Control flow (e.g., cancellation)
```

**Best Practice:**
- Use `FrameDirection.DOWNSTREAM` for normal data flow
- Use `direction` parameter when passing through frames
- Control frames (like `CancelFrame`) can flow upstream

### 4. Context Management

#### Shared Context Pattern

```python
from pipecat.services.openai import OpenAILLMContext

# Create shared context ONCE
shared_context = OpenAILLMContext(
    messages=[
        {"role": "system", "content": "System prompt"}
    ]
)

# User aggregator ADDS user messages
user_aggregator = LLMUserContextAggregator(shared_context)

# LLM service READS from context (via LLMMessagesFrame)
llm_service = SarvamLLMService(...)

# Assistant aggregator ADDS assistant messages
assistant_aggregator = LLMAssistantResponseAggregator(shared_context)
```

**Critical Rules:**
- ✅ Create context ONCE and share it
- ✅ Aggregators modify the context
- ✅ LLM service reads from `frame.context`, doesn't store reference
- ❌ Never mutate context in LLM service

### 5. Transport Configuration

#### Twilio Transport Setup

```python
from pipecat.transports.services.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams
)
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.vad.silero import SileroVADAnalyzer

# Configure VAD
vad_analyzer = SileroVADAnalyzer(
    params=SileroVADAnalyzer.InputParams(
        stop_secs=0.8,
        start_secs=0.2,
        min_volume=0.6
    )
)

# Configure serializer
serializer = TwilioFrameSerializer(
    stream_sid=stream_sid,
    params=TwilioFrameSerializer.InputParams(
        auto_hang_up=False
    )
)

# Create transport
transport = FastAPIWebsocketTransport(
    websocket=websocket,
    params=FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_enabled=True,
        vad_analyzer=vad_analyzer,
        vad_audio_passthrough=True,
        serializer=serializer
    )
)
```

**Key Points:**
- ✅ Transport owns the WebSocket connection
- ✅ VAD is configured at transport level
- ✅ Serializer handles Twilio-specific encoding/decoding
- ✅ `vad_audio_passthrough=True` passes audio to STT

## Implementation Details

### STT Service Implementation

```python
class SarvamSTTService(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Handle VAD events
        if isinstance(frame, UserStartedSpeakingFrame):
            self._is_speaking = True
            self._audio_buffer.clear()
            # Send cancel to interrupt TTS
            await self.push_frame(CancelFrame(), direction)
            await self.push_frame(frame, direction)
            return
        
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._is_speaking = False
            # Process buffered audio
            await self._process_audio_buffer()
            # Small delay for proper ordering
            await asyncio.sleep(0.05)
            await self.push_frame(frame, FrameDirection.DOWNSTREAM)
            return
        
        elif isinstance(frame, AudioRawFrame):
            if self._is_speaking:
                self._audio_buffer.append(frame.audio)
            # Don't pass through - STT consumes audio
            return
        
        # Pass through other frames
        await self.push_frame(frame, direction)
    
    async def _process_audio_buffer(self):
        # Transcribe audio
        transcription = await self._transcribe(audio)
        
        # Push TranscriptionFrame IMMEDIATELY
        await self.push_frame(
            TranscriptionFrame(text=transcription, user_id="user"),
            FrameDirection.DOWNSTREAM
        )
```

**Key Points:**
- ✅ Buffers audio during speech
- ✅ Sends `CancelFrame` on speech start (interrupts TTS)
- ✅ Pushes `TranscriptionFrame` immediately after transcription
- ✅ Small delay before `UserStoppedSpeakingFrame` for proper ordering
- ✅ Doesn't pass through `AudioRawFrame` (consumes it)

### LLM Service Implementation

```python
class SarvamLLMService(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Call super first
        await super().process_frame(frame, direction)
        
        if isinstance(frame, CancelFrame):
            # Cancel ongoing generation
            if self._llm_task:
                self._llm_task.cancel()
            await self.push_frame(frame, direction)
            return
        
        elif isinstance(frame, LLMMessagesFrame):
            # Create task for cancellation support
            self._llm_task = asyncio.create_task(
                self._generate_response(frame)
            )
            return
        
        # Pass through other frames
        await self.push_frame(frame, direction)
    
    async def _generate_response(self, frame: LLMMessagesFrame):
        # Read messages from context (DON'T mutate)
        messages = frame.context.messages
        
        # Generate response
        response = await self._call_llm(messages)
        
        # Push frames
        await self.push_frame(TextFrame(text=response), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
```

**Key Points:**
- ✅ Calls `super().process_frame()` first
- ✅ Uses asyncio.Task for cancellation support
- ✅ Reads from `frame.context.messages` (doesn't mutate)
- ✅ Pushes `TextFrame` then `LLMFullResponseEndFrame`

### TTS Service Implementation

```python
class SarvamTTSService(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Call super first
        await super().process_frame(frame, direction)
        
        if isinstance(frame, CancelFrame):
            self._text_buffer.clear()
            if self._tts_task:
                self._tts_task.cancel()
            await self.push_frame(frame, direction)
            return
        
        elif isinstance(frame, TextFrame):
            # Buffer text (don't pass through)
            self._text_buffer.append(frame.text)
            return
        
        elif isinstance(frame, LLMFullResponseEndFrame):
            # Process buffer
            self._tts_task = asyncio.create_task(
                self._process_text_buffer()
            )
            # Pass through end frame
            await self.push_frame(frame, direction)
            return
        
        # Pass through other frames
        await self.push_frame(frame, direction)
    
    async def _process_text_buffer(self):
        # Synthesize speech
        wav_audio = await self._synthesize(text)
        
        # Extract and resample PCM
        pcm_audio, rate, channels = wav_to_pcm(wav_audio)
        pcm_8k = resample_to_8khz_mono(pcm_audio, rate, channels)
        
        # Push audio frame
        await self.push_frame(
            TTSAudioRawFrame(
                audio=pcm_8k,
                sample_rate=8000,
                num_channels=1
            ),
            FrameDirection.DOWNSTREAM
        )
```

**Key Points:**
- ✅ Calls `super().process_frame()` first
- ✅ Buffers `TextFrame` (doesn't pass through)
- ✅ Processes on `LLMFullResponseEndFrame`
- ✅ Forces 8kHz mono PCM for Twilio compatibility
- ✅ Uses asyncio.Task for cancellation

## Pipeline Execution

### Runner Pattern

```python
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

# Build pipeline
pipeline = Pipeline([...])

# Create task
task = PipelineTask(pipeline)

# Create runner
runner = PipelineRunner()

# Run (blocks until complete)
await runner.run(task)
```

**Key Points:**
- ✅ `PipelineTask` wraps the pipeline
- ✅ `PipelineRunner` executes the task
- ✅ `runner.run()` blocks until pipeline completes
- ✅ Handles cancellation and cleanup automatically

## Best Practices Summary

### ✅ DO

1. **Extend FrameProcessor** for custom processors
2. **Call super().process_frame()** in LLM/TTS services
3. **Use asyncio.Task** for cancellable operations
4. **Push frames with correct direction**
5. **Handle CancelFrame** for interruptions
6. **Share context** between aggregators
7. **Force 8kHz mono** for TTS output to Twilio
8. **Buffer appropriately** (audio in STT, text in TTS)
9. **Use proper frame ordering** (TranscriptionFrame before UserStoppedSpeakingFrame)
10. **Clean up resources** in cleanup() methods

### ❌ DON'T

1. **Don't mutate context** in LLM service
2. **Don't pass through consumed frames** (AudioRawFrame in STT, TextFrame in TTS)
3. **Don't block** in process_frame() - use async
4. **Don't ignore CancelFrame** - always handle interruptions
5. **Don't create multiple contexts** - share one
6. **Don't skip super().process_frame()** in services that need it
7. **Don't forget cleanup()** - always implement resource cleanup

## Verification Checklist

- ✅ All processors extend `FrameProcessor`
- ✅ `process_frame()` implemented correctly
- ✅ Frame directions handled properly
- ✅ Context shared between aggregators
- ✅ LLM doesn't mutate context
- ✅ Cancellation supported via asyncio.Task
- ✅ Audio resampling to 8kHz mono for TTS
- ✅ Proper frame ordering (TranscriptionFrame first)
- ✅ CancelFrame handled in all services
- ✅ Resources cleaned up in cleanup()

## References

- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat GitHub](https://github.com/pipecat-ai/pipecat)
- [Frame Types Reference](https://docs.pipecat.ai/api-reference/frames)
- [Processor Guide](https://docs.pipecat.ai/guides/processors)
