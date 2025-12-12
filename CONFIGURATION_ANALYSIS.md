# Configuration Analysis & Hardcoded Values Audit

## ✅ **ANALYSIS COMPLETE: All Configurable Values Moved to config.yaml**

This document summarizes the comprehensive audit and fixes applied to eliminate hardcoded values and ensure all future-changeable parameters are properly configured.

## 🔧 **Changes Made**

### 1. **TTS Configuration** - `services/tts/sarvam_tts_processor.py`

**BEFORE (Hardcoded):**
```python
self.frame_duration_ms = 20  # Hardcoded
chunk_size = 1024  # Hardcoded fallback
url = "https://api.sarvam.ai/text-to-speech"  # Hardcoded URL
```

**AFTER (Configurable):**
```python
# Constructor now accepts config values
def __init__(self, *, api_key: str, voice: str = "bulbul:v2", sample_rate: int = 8000, 
             frame_duration_ms: int = 20, fallback_chunk_size: int = 1024, 
             api_base_url: str = "https://api.sarvam.ai", api_endpoint: str = "/text-to-speech", **kwargs):

# Uses configurable values
self.frame_duration_ms = frame_duration_ms
self.fallback_chunk_size = fallback_chunk_size
url = f"{self.api_base_url}{self.api_endpoint}"
```

**Config.yaml additions:**
```yaml
tts:
  voice: bulbul:v2
  sample_rate: 8000
  frame_duration_ms: 20  # Audio chunk duration for streaming
  fallback_chunk_size: 1024  # Fallback chunk size if calculation fails
  api_endpoint: "/text-to-speech"  # TTS API endpoint path
```

### 2. **LLM Configuration** - `services/llm/sarvam_llm.py`

**BEFORE (Hardcoded):**
```python
retry_count=2,  # Hardcoded
timeout=15      # Hardcoded
limit=3,        # Hardcoded knowledge search limit
min_score=10.0  # Hardcoded knowledge score threshold
```

**AFTER (Configurable):**
```python
retry_count=settings.LLM_RETRY_COUNT,
timeout=settings.LLM_TIMEOUT
limit=settings.KNOWLEDGE_SEARCH_LIMIT,
min_score=settings.KNOWLEDGE_MIN_SCORE
```

**Config.yaml additions:**
```yaml
llm:
  model: sarvam-m
  max_tokens: 512
  temperature: 0.7
  top_p: 0.85
  frequency_penalty: 0.3
  presence_penalty: 0.2
  retry_count: 2  # Number of retry attempts for API calls
  timeout: 15  # API timeout in seconds
  api_endpoint: "/v1/chat/completions"  # LLM API endpoint path
```

### 3. **Knowledge Base Configuration**

**BEFORE (Hardcoded):**
```python
limit=3,        # Hardcoded in LLM service
min_score=10.0  # Hardcoded in LLM service
```

**AFTER (Configurable):**
```yaml
knowledge:
  base_path: knowledge/Querie.json
  search_limit: 3  # Number of relevant entries to retrieve
  min_score: 10.0  # Minimum relevance score for search results
```

### 4. **STT Configuration**

**BEFORE (Hardcoded):**
```python
await asyncio.sleep(0.5)  # Hardcoded retry delay
```

**AFTER (Configurable):**
```yaml
stt:
  model: saarika:v2.5
  sample_rate: 16000
  strict_language_mode: true
  retry_delay: 0.5  # Delay between retry attempts in seconds
```

## 📊 **Configuration Structure**

### ✅ **Now Configurable (in config.yaml):**
- **TTS Parameters**: Frame duration, chunk sizes, API endpoints
- **LLM Parameters**: Retry counts, timeouts, API endpoints  
- **Knowledge Base**: Search limits, score thresholds
- **STT Parameters**: Retry delays
- **All API Endpoints**: Configurable paths for future flexibility

### ✅ **Correctly Hardcoded (should NOT be configurable):**
- **Audio Format Constants**: 16-bit PCM, WAV header size (44 bytes)
- **Protocol Constants**: HTTP status codes, WebSocket protocols
- **Framework Constants**: Pipecat-specific values
- **Mathematical Constants**: Sample rate calculations, audio processing formulas

## 🎯 **Benefits Achieved**

### 🔧 **Easy Configuration Management:**
- All tunable parameters in one place (`config.yaml`)
- Environment-specific settings without code changes
- Clear documentation of all configurable values

### 🚀 **Production Flexibility:**
- Different retry strategies for different environments
- Adjustable performance parameters
- Easy API endpoint changes for testing/staging

### 🛠️ **Development Benefits:**
- No need to modify code for parameter changes
- Consistent configuration pattern across all services
- Type-safe configuration with Pydantic validation

## 📁 **Files Updated**

### **Configuration Files:**
- ✅ `config.yaml` - Added all new configurable parameters
- ✅ `app/config.py` - Added Pydantic field definitions

### **Service Files:**
- ✅ `services/tts/sarvam_tts_processor.py` - Made parameters configurable
- ✅ `services/llm/sarvam_llm.py` - Used config for retry/timeout values
- ✅ `services/sarvam_ai.py` - Used config for retry delays
- ✅ `pipeline/builder.py` - Pass config values to services

## 🎉 **Final Result**

**All future-changeable values are now properly configured!**

### ✅ **Configuration Principles Applied:**
1. **Configurable**: Values that might change between environments or need tuning
2. **Hardcoded**: Constants that are part of protocols, standards, or framework requirements
3. **Type-Safe**: All config values validated with Pydantic
4. **Documented**: Clear descriptions for all parameters
5. **Backward Compatible**: Existing code continues to work

### 🚀 **Ready for Production:**
Your voice bot now has a clean, maintainable configuration structure that supports:
- Easy deployment across different environments
- Performance tuning without code changes  
- API endpoint flexibility for testing and production
- Consistent configuration management across all services

**Perfect configuration hygiene achieved!** 🎊