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
│  │  API Routes (api/routes/voice.py)               │    │
│  │  • POST /voice/incoming (IVR)                   │    │
│  │  • POST /voice/language-selected                │    │
│  │  • WS /media-stream/{language}                  │    │
│  │  • GET /health, /analytics                      │    │
│  └─────────────────────────────────────────────────┘    │
│                     ↓                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Pipecat Pipeline (pipeline/builder.py)         │    │
│  │  • FastAPIWebsocketTransport                    │    │
│  │  • SileroVAD + TwilioFrameSerializer            │    │
│  │  • Real-time frame processing                   │    │
│  └─────────────────────────────────────────────────┘    │
│                     ↓                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Voice AI Pipeline Components                   │    │
│  │  • SarvamSTTService (services/stt/)             │    │
│  │  • LLMContextAggregatorPair (aggregators/)      │    │
│  │  • SarvamLLMService (services/llm/)             │    │
│  │  • SarvamTTSProcessor (services/tts/)           │    │
│  │  • Enhanced RAG search (knowledge/)             │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS API Calls
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Sarvam AI API Services                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │     STT      │  │     LLM      │  │     TTS      │  │
│  │ saarika:v2.5 │  │  sarvam-m    │  │  bulbul:v2   │  │
│  │ 16kHz input  │  │ Context-aware│  │ 8kHz output  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Twilio Platform
**Role**: Telephony infrastructure

**Responsibilities**:
- Receives incoming phone calls
- Plays IVR menu prompts
- Gathers DTMF (keypad) input
- Streams audio to/from your server via WebSocket
- Handles call routing and termination

**Audio Format**: Mulaw (8kHz, mono, base64-encoded)

---

### 2. FastAPI Server (app/main.py)
**Role**: Main application server with modular architecture

**Core Components**:
- **FastAPI Application**: Modern async web framework
- **Configuration Management**: Environment (.env) + YAML (config.yaml) configuration
- **Logging**: Structured logging with loguru (app/logging_config.py)
- **Middleware**: CORS, request tracking, analytics (app/middleware.py)

**API Endpoints**:

#### `/voice/incoming` (POST)
- Initial Twilio webhook (api/routes/voice.py)
- Plays multilingual IVR menu)
- Gathers user's language choice (1=Telish)
- Creates CallSession 

#### `/voice/language-selected` (POST)
- Receives selected language digitDTMF
- Maps to LanguageCode enum (te-IN, hi-IN, en
- Builds WebSocket URL with language in path


#### `/media-stream/{language}` (WebSo)
- Language-specific WebSocket endpoint
- Extracts real stream_sid from e
- Bidirectional audio streaming (
ner
- Real-time conversation 

#### Additional Endpoints
- `/health` - Health check and system status
 metrics
- `/voice/outboution)

**Kes**:
e/
- **Configuration Management**: Pydanticrt
- **Session Management**po supnfig.yaml .env and cottings with se/, pipelinvicessers api/,  acrosof concernsn separatioClean ture**: rchitecr A**Modula- eatur Feye selecguagskips lanndling ( hacallound ` - Outbnd

---

### 3. Audio Processing (audio_utils.py)
**Role**: Audio format conversion

**Functions**:

#### Incoming Audio (Twilio → Sarvam)
```python
decode_mulaw_base64()  # Base64 → raw mulaw
mulaw_to_wav()         # Mulaw → WAV (16kHz for STT)
```

#### Outgoing Audio (Sarvam → Twilio)
```python
wav_to_mulaw()         # WAV → raw mulaw (8kHz)
encode_mulaw_base64()  # Raw mulaw → base64
```

**Voice Activity Detection**:
- Detects speech vs silence
- Buffers audio until complete utterance
- Adaptive threshold for noise handling

---

### 4. Sarvam AI Integration (sarvam_ai.py)
**Role**: AI service wrapper

**Services**:

#### Speech-to-Text (STT)
- Model: saarika:v2.5
- Input: WAV file (16kHz)
- Output: Transcribed text
- Latency: 1-2 seconds

#### Language Model (LLM)
- Model: sarvam-m
- Input: Conversation history
- Output: AI response text
- Latency: 0.4-0.8 seconds

#### Text-to-Speech (TTS)
- Model: bulbul:v2
- Voice: anushka (female)
- Input: Text response
- Output: WAV audio (8kHz)
- Latency: 0.6-1.4 seconds

---

## Data Flow

### Complete Conversation Cycle

```
1. User speaks
   ↓
2. Twilio captures audio → mulaw chunks
   ↓
3. Server receives via WebSocket
   ↓
4. Buffer audio until silence detected
   ↓
5. Convert mulaw → WAV (16kHz)
   ↓
6. Send to Sarvam STT
   ↓
7. Receive transcribed text
   ↓
8. Add to conversation context
   ↓
9. Send to Sarvam LLM
   ↓
10. Receive AI response text
    ↓
11. Send to Sarvam TTS
    ↓
12. Receive WAV audio (8kHz)
    ↓
13. Convert WAV → mulaw
    ↓
14. Encode to base64
    ↓
15. Send to Twilio via WebSocket (160-byte chunks)
    ↓
16. User hears response
```

**Total Time**: 2-4 seconds

---

## Conversation State Management

### Variables Tracked
```python
is_speaking = False        # User currently speaking?
is_processing = False      # AI currently processing?
audio_buffer = []          # Buffered audio chunks
silence_buffer = []        # Silence detection buffer
messages = []              # Conversation history
last_user_query = ""       # Previous user input
query_count = 0            # Number of queries
failed_stt_count = 0       # Failed recognition attempts
selected_language = "te-IN" # User's chosen language
```

### Concurrency Control
- `is_processing` flag prevents concurrent processing
- Ensures one utterance processed at a time
- Prevents race conditions

---

## Error Handling

### WebSocket Errors
- Connection state checks before sending
- Graceful disconnection handling
- Timeout after 5 minutes of inactivity

### API Errors
- Retry logic for transient failures
- Fallback messages for persistent errors
- Human transfer after 3 consecutive failures

### Audio Errors
- Validation of audio format
- Minimum audio length checks
- Proper cleanup on conversion failures

---

## Performance Optimizations

### Audio Buffering
- Streams audio in 20ms chunks (160 bytes)
- Minimizes latency
- Smooth playback

### Async Processing
- Non-blocking I/O operations
- Concurrent request handling
- Efficient resource usage

### Sample Rate Strategy
- 16kHz for STT (better quality)
- 8kHz for TTS (matches Twilio)
- Minimizes unnecessary resampling

---

## Scalability Considerations

### Current Limitations
- Single-threaded audio processing per call
- In-memory conversation state
- No persistent storage

### Future Improvements
- Redis for conversation state
- Database for call analytics
- Load balancing for multiple instances
- CDN for static IVR prompts

---

## Security

### API Keys
- Stored in `.env` file
- Never committed to version control
- Loaded via environment variables

### WebSocket Security
- Origin validation
- Connection timeout
- Rate limiting (future)

### Data Privacy
- No audio recording by default
- Conversation history in memory only
- Cleared on call end
