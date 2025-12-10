# Troubleshooting Guide

## Common Issues and Solutions

---

## Server Issues

### Server Won't Start

**Symptoms:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solutions:**
1. Activate virtual environment:
   ```bash
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Check Python version (needs 3.10+):
   ```bash
   python --version
   ```

---

### Port Already in Use

**Symptoms:**
```
OSError: [Errno 48] Address already in use
```

**Solutions:**
1. Kill process using port 8000:
   ```bash
   # Windows
   netstat -ano | findstr :8000
   taskkill /PID <PID> /F
   ```

2. Or use a different port:
   ```bash
   uvicorn twilio_server:app --port 8001
   ```

---

## Twilio Issues

### No Audio from Bot

**Symptoms:**
- User hears silence after speaking
- Logs show "📤 Sending audio to Twilio" but no sound

**Solutions:**
1. Check Twilio webhook URL is correct:
   - Should be: `https://your-domain.com/voice/incoming`
   - Must be HTTPS (not HTTP)

2. Verify WebSocket connection:
   - Look for "🔌 WebSocket connected" in logs
   - Check for "❌ WebSocket error" messages

3. Check audio format:
   - Must be mulaw, 8kHz, mono
   - Verify `wav_to_mulaw()` is working

---

### IVR Menu Not Playing

**Symptoms:**
- Call connects but no menu heard
- Immediate disconnect

**Solutions:**
1. Check Twilio webhook configuration:
   - Voice webhook: `https://your-domain.com/voice/incoming`
   - Method: POST
   - Webhook type: TwiML

2. Verify server is accessible:
   ```bash
   curl https://your-domain.com/voice/incoming
   ```

3. Check logs for errors:
   - Look for "📞 Incoming call" message
   - Check for TwiML generation errors

---

### Language Selection Not Working

**Symptoms:**
- User presses key but nothing happens
- Always defaults to Telugu

**Solutions:**
1. Check DTMF gathering timeout (should be 10s)
2. Verify language mapping in code:
   ```python
   language_map = {
       "1": "te-IN",
       "2": "hi-IN",
       "3": "en-IN",
       "4": "gu-IN"
   }
   ```
3. Check logs for "🌐 Language selected" message

---

## Sarvam AI Issues

### STT Errors (400 Bad Request)

**Symptoms:**
```
❌ STT API error: 400 - "body.language_code : Input should be..."
```

**Solutions:**
1. Verify language code is supported:
   - Valid: te-IN, hi-IN, en-IN, gu-IN
   - Invalid: ur-IN (not supported)

2. Check audio format:
   - Must be WAV file
   - Should be 16kHz for best results

3. Verify API key in `.env`:
   ```ini
   SARVAM_API_KEY=sk_...
   ```

---

### LLM Errors (404 Not Found)

**Symptoms:**
```
❌ LLM API error: 404 - Model not found
```

**Solutions:**
1. Check model name:
   - Valid: `sarvam-m`, `gemma-4b`, `gemma-12b`
   - Invalid: `sarvam-2b` (old name)

2. Verify endpoint URL:
   ```python
   base_url = "https://api.sarvam.ai/v1"
   ```

---

### TTS Errors (400 Bad Request)

**Symptoms:**
```
❌ TTS API error: 400 - Invalid speaker
```

**Solutions:**
1. Check speaker name:
   - Valid: anushka, meera, arvind, karun
   - Case-sensitive!

2. Verify model version:
   - Use: `bulbul:v2`
   - Not: `bulbul:v1` (deprecated)

---

## Audio Quality Issues

### Robotic/Distorted Audio

**Symptoms:**
- Audio sounds choppy or robotic
- Words are cut off

**Solutions:**
1. Check sample rate conversion:
   - Should be 8kHz for Twilio
   - Verify `wav_to_mulaw()` resampling

2. Verify chunk size:
   - Must be 160 bytes (20ms at 8kHz)
   - Check chunking logic in send loop

3. Check network latency:
   - High latency can cause buffering issues
   - Consider using a CDN or closer server

---

### Audio Too Fast/Slow

**Symptoms:**
- Speech sounds sped up or slowed down

**Solutions:**
1. Check sample rate mismatch:
   - Twilio expects 8kHz
   - Verify no accidental resampling

2. Check TTS pace parameter:
   ```python
   pace=1.0  # Normal speed (0.3-3.0)
   ```

---

### No Audio Detected from User

**Symptoms:**
- User speaks but bot doesn't respond
- Logs show "🔇 Silence detected" immediately

**Solutions:**
1. Check VAD thresholds:
   ```python
   min_speech_length = 6000  # 0.75 seconds
   ```

2. Verify audio amplification:
   - Should boost quiet audio by 2x
   - Check `mulaw_to_wav()` logic

3. Check microphone/phone quality:
   - Test with different phone
   - Verify Twilio is receiving audio

---

## Performance Issues

### Slow Response Time (>5 seconds)

**Symptoms:**
- Long delay between user speech and bot response

**Solutions:**
1. Check API latencies in logs:
   ```
   ⏱️ Total response time: X.XXs (STT: X.XXs, LLM: X.XXs, TTS: X.XXs)
   ```

2. Optimize if needed:
   - STT: Use 8kHz instead of 16kHz (faster but lower quality)
   - LLM: Use smaller model (sarvam-m is fastest)
   - TTS: Reduce audio quality if acceptable

3. Check network latency:
   - Deploy server closer to Sarvam AI (India region)
   - Use faster hosting provider

---

### High Memory Usage

**Symptoms:**
- Server crashes after many calls
- Memory keeps increasing

**Solutions:**
1. Check for memory leaks:
   - Ensure `audio_buffer` is cleared after processing
   - Verify WebSocket cleanup in `finally` block

2. Limit conversation history:
   ```python
   if len(messages) > 20:
       messages = messages[-20:]  # Keep last 20 messages
   ```

---

## Debugging Tips

### Enable Detailed Logging

Add to `twilio_server.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test Individual Components

**Test STT:**
```python
from sarvam_ai import transcribe_audio
result = transcribe_audio("test.wav", "en-IN")
print(result)
```

**Test TTS:**
```python
from sarvam_ai import generate_speech
audio = generate_speech("Hello world", "en-IN")
print(len(audio))
```

**Test Audio Conversion:**
```python
from audio_utils import mulaw_to_wav, wav_to_mulaw
wav = mulaw_to_wav(mulaw_data)
mulaw = wav_to_mulaw(wav)
assert len(mulaw) > 0
```

---

## Getting Help

If issues persist:

1. **Check logs** for error messages
2. **Test with curl** to isolate issues:
   ```bash
   curl -X POST https://your-domain.com/voice/incoming
   ```
3. **Verify environment**:
   - Python version
   - Dependency versions
   - API key validity
4. **Contact support**:
   - Sarvam AI: [docs.sarvam.ai](https://docs.sarvam.ai/)
   - Twilio: [support.twilio.com](https://support.twilio.com/)

---

## Emergency Fixes

### Quick Restart
```bash
# Kill server
Ctrl+C

# Restart
python twilio_server.py
```

### Reset Everything
```bash
# Deactivate venv
deactivate

# Delete venv
rmdir /s venv

# Recreate
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Restart
python twilio_server.py
```

### Fallback to Human Agent

If AI fails repeatedly, add transfer logic:
```python
if failed_stt_count >= 3:
    # Transfer to human
    response.say("Transferring to agent")
    response.dial("+1234567890")  # Your support number
```
