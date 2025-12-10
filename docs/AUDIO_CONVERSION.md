# Audio Format Conversion

## Overview

Twilio and Sarvam AI use different audio formats. This document explains the conversion process.

---

## Twilio → Sarvam (Incoming Audio)

### Flow
```
Twilio sends: Base64-encoded mulaw (8kHz, mono)
    ↓
Decode: decode_mulaw_base64() → raw mulaw bytes
    ↓
Convert: mulaw_to_wav() → WAV format (16kHz for better STT)
    ↓
Send to Sarvam STT: WAV file
```

### Why 16kHz for STT?
- Better transcription quality
- Sarvam STT performs better with higher sample rates
- Minimal overhead in conversion

---

## Sarvam → Twilio (Outgoing Audio)

### Flow
```
Sarvam TTS returns: WAV (8kHz, mono, 16-bit PCM with headers)
    ↓
Convert: wav_to_mulaw() → raw mulaw bytes (8kHz, mono, NO headers)
    - Extract PCM data from WAV
    - Convert 16-bit PCM → 8-bit mulaw
    - Strip all WAV headers
    ↓
Encode: encode_mulaw_base64() → base64 string
    ↓
Send to Twilio: In 160-byte chunks (20ms at 8kHz)
```

---

## Twilio Requirements (STRICT)

Twilio only accepts:
- **Sample rate**: 8000 Hz
- **Encoding**: μ-law (mulaw)
- **Channels**: Mono
- **Format**: Raw bytes (NO WAV headers)
- **Transport**: Base64-encoded
- **Chunk size**: 160 bytes = 20ms at 8kHz

---

## Conversion Functions

### `decode_mulaw_base64(data: str) -> bytes`
Decodes base64 mulaw from Twilio to raw bytes.

### `mulaw_to_wav(mulaw_data: bytes) -> bytes`
Converts mulaw to WAV format:
- Decodes mulaw → 16-bit PCM
- Resamples 8kHz → 16kHz (for STT)
- Adds WAV headers

### `wav_to_mulaw(wav_data: bytes) -> bytes`
Converts WAV to raw mulaw:
- Extracts PCM from WAV
- Handles stereo → mono conversion
- Resamples to 8kHz if needed
- Converts 16-bit PCM → 8-bit mulaw
- Strips all headers

### `encode_mulaw_base64(mulaw_data: bytes) -> str`
Encodes raw mulaw bytes to base64 for Twilio.

---

## Audio Quality Settings

### Sarvam TTS Configuration
```python
# Configured to output 8kHz (matching Twilio)
# Minimizes resampling overhead
sample_rate = 8000
```

### STT Input
```python
# Uses 16kHz for better transcription
# Upsampled from Twilio's 8kHz
sample_rate = 16000
```

---

## Verified Format

✅ **Sarvam TTS Output**: WAV (8000Hz, 1ch, 16-bit PCM)  
✅ **Conversion Output**: Raw mulaw (8000Hz, 1ch, 8-bit)  
✅ **Chunk Size**: 160 bytes = 20ms at 8kHz  
✅ **No Headers**: Pure mulaw data for Twilio  

---

## Common Issues

### Audio Sounds Distorted
- Check sample rate conversion (must be 8kHz for Twilio)
- Verify mulaw encoding is correct
- Ensure WAV headers are stripped

### Audio Too Fast/Slow
- Sample rate mismatch
- Check resampling logic in `wav_to_mulaw()`

### No Audio
- Verify base64 encoding/decoding
- Check chunk size (must be 160 bytes)
- Ensure WebSocket is sending media messages

---

## Testing

To verify audio conversion:

```python
# Test mulaw → WAV → mulaw roundtrip
original = b'\x00\x01\x02...'  # mulaw data
wav = mulaw_to_wav(original)
converted = wav_to_mulaw(wav)
assert len(converted) > 0
```

---

## Performance

- **Mulaw → WAV**: ~10ms for 1 second of audio
- **WAV → Mulaw**: ~15ms for 1 second of audio
- **Total overhead**: ~25ms per audio chunk
- **Negligible impact** on overall response time (2-4 seconds)
