# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User's Phone                          │
└────────────────────┬────────────────────────────────────┘
                     │ Phone Call
                     ↓
┌─────────────────────────────────────────────────────────┐
│                  Twilio Platform                         │
│  • Receives call                                         │
│  • Plays multilingual IVR menu                          │
│  • Gathers DTMF input (1=Telugu, 2=Hindi, 3=English)   │
│  • Streams audio via WebSocket (mulaw 8kHz)             │
└────────────────────┬────────────────────────────────────┘
                     │ WebSocket (mulaw audio)
                     ↓
┌─────────────────────────────────────────────────────────┐
│              FastAPI Server (app/main.py)                │
│  ┌─────────────────────────────────────────────────┐    │
│  │  API Routes                                      │    │
│  │  • POST /voice/incoming (IVR)                   │    │
│  │  • POST /voice/language-selected                │    │
│  │  • WS /media-stream/{language}                  │    │
│  │  • GET /health, /metrics                        │    │
│  └─────────────────────────────────────────────────┘    │
│                     ↓                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Pipecat Pipeline (pipeline/builder.py)         │    │
│  │  • FastAPIWebsocketTransport                    │    │
│  │  • TwilioFrameSerializer (with stream_sid)      │    │
│  │  • SileroVAD (optional)                         │    │
│  │  • Real-time frame processing                   │    │
│  └─────────────────────────────────────────────────┘    │
│                     ↓                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Voice AI Pipeline Components (Built-in)        │    │
│  │  • SarvamSTTService (Pipecat built-in)          │    │
│  │  • LLMUserContextAggregator                     │    │
│  │  • SarvamLLMService (Custom)                    │    │
│  │  • LLMAssistantContextAggregator (Patched)      │    │
│  │  • SarvamTTSService (Pipecat built-in)          │    │
│  │  • RAG Knowledge Base (Optional)                │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS/WSS API Calls
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Sarvam AI API Services                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │     STT      │  │     LLM      │  │     TTS      │  │
│  │ saarika:v2.5 │  │  sarvam-m    │  │  bulbul:v2   │  │
│  │ 16kHz input  │  │ Context-aware│  │ 8kHz output  │  │
│  │ (WebSocket)  │  │ (HTTP)       │  │ (WebSocket)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Complete Call Flow

### 1. Call Initiation
```
User dials Twilio number
    ↓
Twilio webhook → POST /voice/incoming
    ↓
Server creates CallSession (LANGUAGE_SELECTION state)
    ↓
TwiML response with <Gather> for language selection
    ↓
IVR menu plays (Polly.Aditi voice)
    ↓
User presses digit (1=Telugu, 2=Hindi, 3=English)
```

### 2. Language Selection
```
Twilio webhook → POST /voice/language-selected
    ↓
Server maps digit → LanguageCode (te-IN, hi-IN, en-IN)
    ↓
TwiML response with <Connect><Stream>
    ↓
WebSocket URL: wss://domain/media-stream/{language}
    ↓
Twilio establishes WebSocket connection
```

### 3. WebSocket Handshake
```
Server accepts WebSocket connection
    ↓
Twilio sends: {"event": "connected"}
    ↓
Twilio sends: {"event": "start", "streamSid": "...", "callSid": "..."}
    ↓
Server extracts stream_sid and call_sid
    ↓
Server creates Pipecat pipeline with extracted IDs
    ↓
Pipeline ready for audio streaming
```

### 4. Real-time Conversation
```
User speaks
    ↓
Twilio sends: {"event": "media", "payload": "base64_mulaw..."}
    ↓
TwilioFrameSerializer: mulaw → PCM 16kHz
    ↓
SarvamSTTService: PCM → TranscriptionFrame
    ↓
LLMUserContextAggregator: Accumulate → OpenAILLMContextFrame
    ↓
SarvamLLMService: Generate response → LLMTextFrame(s)
    ↓
LLMAssistantContextAggregator: Forward to TTS
    ↓
SarvamTTSService: Text → TTSAudioRawFrame (8kHz PCM)
    ↓
TwilioFrameSerializer: PCM → mulaw base64
    ↓
Server sends: {"event": "media", "payload": "base64_mulaw..."}
    ↓
User hears response
```

### 5. Call Termination
```
User hangs up OR timeout
    ↓
Twilio sends: {"event": "stop"}
    ↓
Pipeline cleanup
    ↓
CallSession updated (ENDED state)
    ↓
Analytics logged
    ↓
WebSocket closed
```

---

## Component Details

### 1. Twilio Platform
**Role**: Telephony infrastructure

**Responsibilities**:
- Receives incoming phone calls
- Plays IVR menu prompts (using Polly.Aditi voice)
- Gathers DTMF (keypad) input (1=Telugu, 2=Hindi, 3=English)
- Streams audio to/from server via WebSocket
- Provides stream_sid and call_sid in start message
- Handles call routing and termination

**Audio Format**: Mulaw (8kHz, mono, base64-encoded)

**Critical Implementation Details**:
- Language passed via URL path (`/media-stream/{language}`) not query params
- Stream SID extracted from Twilio's 'start' message before pipeline creation
- WebSocket URL uses wss:// protocol for secure connections

---

### 2. FastAPI Server (app/main.py)
**Role**: Main application server with modular architecture

**Core Components**:
- **FastAPI Application**: Modern async web framework
- **Configuration Management**: Environment (.env) + YAML (config.yaml) configuration
- **Logging**: Structured logging with loguru (app/logging_config.py)
- **Middleware**: CORS, metrics tracking, rate limiting (app/middleware.py)
- **Prometheus Metrics**: Available at `/metrics` endpoint

**API Endpoints**:

#### `/voice/incoming` (POST)
- Initial Twilio webhook (api/routes/voice.py)
- Plays multilingual IVR menu using Polly.Aditi voice
- Gathers user's language choice (1=Telugu, 2=Hindi, 3=English)
- Creates CallSession with LANGUAGE_SELECTION state
- Timeout: 10 seconds, then repeats menu

#### `/voice/language-selected` (POST)
- Receives selected language digit via DTMF
- Maps to LanguageCode enum (te-IN, hi-IN, en-IN)
- Builds WebSocket URL with language in path
- Connects to `/media-stream/{language}` via TwiML <Connect><Stream>
- No greeting played (bot greets via WebSocket)

#### `/media-stream/{language}` (WebSocket)
- Language-specific WebSocket endpoint
- Extracts real stream_sid and call_sid from Twilio's 'start' message
- Bidirectional audio streaming (mulaw 8kHz)
- Runs Pipecat pipeline for real-time conversation
- Handles WebSocket lifecycle (connected, start, media, stop)

#### Additional Endpoints
- `/` - Root endpoint with API info
- `/health` - Health check and system status
- `/metrics` - Prometheus metrics (if available)
- `/voice/outbound` - Outbound call handling (skips language selection)

**Key Features**:
- **Configuration Management**: Pydantic settings with .env and config.yaml
- **Session Management**: CallSession tracking across pipeline
- **Modular Architecture**: Clean separation of concerns (api/, services/, pipeline/)
- **Feature Flags**: Analytics, debug mode, VAD enable/disable
- **Language Selection**: IVR-based language selection (skips detection)
- **Outbound Calls**: Direct WebSocket connection without IVR

---

### 3. Pipecat Pipeline (pipeline/builder.py)
**Role**: Voice AI pipeline orchestration

**Components**:

#### Transport Layer
- `FastAPIWebsocketTransport` - WebSocket connection management
- `TwilioFrameSerializer` - Audio format conversion (mulaw ↔ PCM)
- `SileroVADAnalyzer` - Voice activity detection (optional)

#### STT Service (Built-in)
- `SarvamSTTService` - Pipecat's built-in Sarvam STT service
- WebSocket connection to Sarvam API
- Model: saarika:v2.5
- Input: AudioRawFrame (16kHz PCM)
- Output: TranscriptionFrame

#### Context Aggregators (Built-in)
- `LLMUserContextAggregator` - Accumulates user messages
- `LLMAssistantContextAggregator` - Accumulates assistant responses (patched)
- Shared `OpenAILLMContext` for conversation history

#### LLM Service (Custom)
- `SarvamLLMService` - Custom implementation for Sarvam AI
- HTTP connection to Sarvam API
- Model: sarvam-m
- Optional RAG knowledge base integration
- Input: OpenAILLMContextFrame
- Output: LLMTextFrame(s)

#### TTS Service (Built-in)
- `SarvamTTSService` - Pipecat's built-in Sarvam TTS service
- WebSocket connection to Sarvam API
- Voice: bulbul:v2
- Input: LLMTextFrame
- Output: TTSAudioRawFrame (8kHz PCM)

**Pipeline Flow**:
```
Transport.input() → STT → UserAggregator → LLM → 
AssistantAggregator → TTS → Transport.output()
```

---

### 4. Sarvam AI Services
**Role**: AI model providers

**Services Used**:

#### Speech-to-Text (STT)
- **API**: WebSocket streaming
- **Model**: saarika:v2.5
- **Sample Rate**: 16kHz input
- **Languages**: Telugu, Hindi, English
- **Latency**: Real-time streaming (~100-200ms)

#### Language Model (LLM)
- **API**: HTTP REST
- **Model**: sarvam-m
- **Context**: Conversation history
- **Features**: RAG-enhanced responses
- **Latency**: 400-800ms

#### Text-to-Speech (TTS)
- **API**: WebSocket streaming
- **Voice**: bulbul:v2
- **Sample Rate**: 8kHz output
- **Languages**: Telugu, Hindi, English
- **Latency**: Real-time streaming (~100-200ms)

---

## Data Flow

### Complete Conversation Cycle

```
1. User speaks
   ↓
2. Twilio captures audio → mulaw chunks (base64-encoded)
   ↓
3. Server receives via WebSocket ('media' events)
   ↓
4. TwilioFrameSerializer decodes mulaw → PCM 16kHz
   ↓
5. VAD detects speech (optional, can use STT VAD)
   ↓
6. SarvamSTTService transcribes (WebSocket API)
   ↓
7. TranscriptionFrame → LLMUserContextAggregator
   ↓
8. Aggregator accumulates text → OpenAILLMContextFrame
   ↓
9. SarvamLLMService processes (with optional RAG)
   ↓
10. LLM generates response → LLMTextFrame(s)
    ↓
11. LLMAssistantContextAggregator forwards to TTS
    ↓
12. SarvamTTSService synthesizes (WebSocket API)
    ↓
13. TTS returns PCM audio → TTSAudioRawFrame
    ↓
14. TwilioFrameSerializer encodes PCM → mulaw (base64)
    ↓
15. Send to Twilio via WebSocket (160-byte chunks)
    ↓
16. User hears response
```

**Total Time**: 500-800ms typical (optimized pipeline)

---

## Configuration Management

### Environment Variables (.env)
**Credentials and Secrets**:
```env
# Twilio
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1234567890

# Sarvam AI
SARVAM_API_KEY=xxx
SARVAM_API_URL=https://api.sarvam.ai

# Server
SERVER_URL=https://your-domain.com

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
```

### Application Settings (config.yaml)
**Tunable Parameters**:
```yaml
# STT Configuration
stt:
  model: saarika:v2.5
  sample_rate: 16000
  strict_language_mode: true

# LLM Configuration
llm:
  model: sarvam-m
  max_tokens: 512
  temperature: 0.7
  retry_count: 2
  timeout: 15

# TTS Configuration
tts:
  voice: bulbul:v2
  sample_rate: 8000

# VAD Configuration
vad:
  enabled: false  # Using STT VAD instead
  confidence: 0.85
  stop_secs: 1.5

# Pipeline Configuration
pipeline:
  aggregation_timeout: 2.0
  max_silence_duration: 300.0

# Knowledge Base
knowledge:
  base_path: knowledge/Querie.json
  search_limit: 3
  min_score: 10.0
```

### Pydantic Settings
All configuration merged and validated using Pydantic:
```python
from app.config import settings

# Access configuration
settings.TWILIO_ACCOUNT_SID
settings.STT_MODEL
settings.LLM_TEMPERATURE
```

---

## Error Handling

### WebSocket Lifecycle
- Proper connection acceptance
- Event-based message handling (connected, start, media, stop)
- Graceful disconnection on errors
- Automatic cleanup on pipeline completion

### API Retry Logic
**STT Service**:
- Built-in reconnection for WebSocket
- Automatic retry on transient failures

**LLM Service**:
- Configurable retry count (default: 2)
- Timeout handling (default: 15s)
- Fallback responses on persistent failures

**TTS Service**:
- WebSocket with automatic reconnection
- HTTP fallback if WebSocket fails
- Graceful degradation

### Pipeline Error Handling
- `CancelFrame` for interruptions
- Proper cleanup in finally blocks
- Session state tracking (ACTIVE, ENDED, ERROR)
- Analytics logging on all exit paths

---

## Performance Optimizations

### Streaming Architecture
- **WebSocket Streaming**: Real-time audio for STT and TTS
- **Frame-based Processing**: Pipecat's efficient frame pipeline
- **Async/Await**: Non-blocking I/O throughout
- **Zero-copy Audio**: TwilioFrameSerializer minimizes memory allocation

### Latency Breakdown
| Component | Latency | Notes |
|-----------|---------|-------|
| Audio Conversion | ~20ms | TwilioFrameSerializer |
| STT | ~100-200ms | WebSocket streaming |
| LLM | ~400-800ms | HTTP API |
| TTS | ~100-200ms | WebSocket streaming |
| **Total** | **500-800ms** | **Typical end-to-end** |

### Sample Rate Strategy
- **Twilio**: 8kHz mulaw (telephony standard)
- **Pipecat Internal**: 16kHz PCM (better quality)
- **STT**: 16kHz input (optimal for Sarvam)
- **TTS**: 8kHz output (matches Twilio)
- **Conversion**: Automatic by TwilioFrameSerializer

### Resource Usage (Per Call)
- **CPU**: ~10-20% per call
- **Memory**: ~100-200 MB per call
- **Network**: ~64 kbps (audio streaming)
- **Concurrent Calls**: 50-100 per instance (2-4 CPU cores)

---

## Scalability

### Horizontal Scaling
- **Load Balancer**: Distribute calls across instances
- **Sticky Sessions**: WebSocket connections need session affinity
- **Redis**: Optional for shared session storage
- **Database**: PostgreSQL for analytics (optional)

### Vertical Scaling
- **Recommended**: 2-4 CPU cores, 2-4 GB RAM per instance
- **Concurrent Calls**: 50-100 per instance
- **Network**: High bandwidth for audio streaming

### Current Architecture
- **Stateless**: Each call is independent
- **In-memory**: Conversation context per call
- **No Persistence**: By design (privacy-focused)
- **Easy to Scale**: Add more instances behind load balancer

---

## Security

### Credentials Management
- **Environment Variables**: All secrets in `.env` file
- **Never Committed**: `.env` in `.gitignore`
- **Pydantic Validation**: Type-safe configuration loading
- **Secrets Manager**: Ready for AWS Secrets Manager / Vault

### Network Security
- **HTTPS/WSS Only**: No unencrypted connections
- **CORS Configuration**: Controlled origins
- **Rate Limiting**: Middleware-based (60 req/min default)
- **Input Validation**: All API endpoints validated

### Data Privacy
- **No Recording**: Audio not stored by default
- **In-memory Only**: Conversation context cleared on call end
- **No Persistence**: Privacy-focused design
- **GDPR Ready**: No PII storage

### WebSocket Security
- **Origin Validation**: Check request origins
- **Connection Timeout**: 5-minute inactivity limit
- **Stream SID Validation**: Twilio-provided identifiers
- **Graceful Disconnection**: Proper cleanup on errors

---

## Monitoring & Observability

### Logging
- **Structured Logging**: Loguru with JSON output
- **Log Levels**: INFO for operations, DEBUG for development
- **Log Rotation**: 10 MB per file, 7-day retention
- **Separate Logs**: app.log, errors.log, tts.log, etc.

### Metrics
- **Prometheus**: Available at `/metrics` endpoint
- **Custom Metrics**: Call duration, API latency, error rates
- **Middleware**: Automatic request/response tracking
- **Analytics**: Per-language call statistics

### Health Checks
- **Endpoint**: `GET /health`
- **Response**: System status, uptime, configuration
- **Kubernetes Ready**: Liveness and readiness probes
- **Monitoring**: Integrate with Datadog, New Relic, etc.

---

## Summary

### Architecture Highlights

1. **Modern Stack**: FastAPI + Pipecat + Sarvam AI
2. **Built-in Services**: Minimal custom code, maximum reliability
3. **Streaming**: Real-time audio with WebSocket
4. **Scalable**: Stateless design, easy horizontal scaling
5. **Configurable**: YAML + .env for all settings
6. **Observable**: Comprehensive logging and metrics
7. **Secure**: HTTPS/WSS, no data persistence
8. **Production-Ready**: Error handling, retry logic, cleanup

### Key Design Decisions

- **Pipecat Built-in Services**: Use SarvamSTTService and SarvamTTSService (not custom)
- **TwilioFrameSerializer**: Handles all audio conversion automatically
- **Stream SID Extraction**: From Twilio's 'start' message before pipeline creation
- **Path-based Language**: `/media-stream/{language}` (not query params)
- **Shared Context**: Single OpenAILLMContext shared between aggregators
- **Patched Aggregator**: LLMAssistantContextAggregator forwards frames to TTS
- **Config Management**: Pydantic Settings with .env + config.yaml

---

**Last Updated**: December 18, 2025  
**Status**: ✅ Production Ready  
**Pipecat Version**: 0.0.95
- Cleared on call end
