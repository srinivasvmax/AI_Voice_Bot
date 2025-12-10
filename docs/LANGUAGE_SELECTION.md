# Language Selection Feature

## IVR Language Menu Flow

### Call Flow

```
📞 User Calls
    ↓
🔊 IVR Menu
    "Welcome to Customer Support"
    "Press 1 for Telugu"
    "Press 2 for Hindi"
    "Press 3 for English"
    ↓
👤 User Presses Key (1-3)
    ↓
✅ Language Confirmed
    "You selected [Language]"
    ↓
🤖 AI Conversation Starts
    (All responses in selected language)
```

---

## Supported Languages

| Key | Language | Code | Example Greeting |
|-----|----------|------|------------------|
| 1 | Telugu | te-IN | "తెలుగు. మీకు ఎలా సహాయం చేయగలను?" |
| 2 | Hindi | hi-IN | "हिंदी। मैं आपकी कैसे मदद कर सकता हूं?" |
| 3 | English | en-IN | "English. How may I assist you?" |

---

## Benefits

### ✅ Accuracy
- No language detection errors
- User explicitly chooses language
- 100% accurate language matching

### ✅ Speed
- Only processes 1 language (not multiple)
- Faster STT processing (~1 second saved)
- Total response time: 2-4 seconds

### ✅ User Experience
- Clear language options
- User feels in control
- Professional IVR experience

---

## Retry Logic

### First Timeout/Invalid Input
```
User doesn't press key → Wait 10s → Retry menu
User presses invalid key (4,5,6...) → Retry menu
```

### Second Timeout/Invalid Input
```
No input again → Default to Telugu
Invalid input again → Default to Telugu
```

---

## Implementation

### Endpoints

1. **`/voice/incoming`** - Initial webhook
   - Plays language menu
   - Gathers DTMF input (1-3)
   - Timeout: 10 seconds

2. **`/voice/language-selected`** - After selection
   - Maps digit to language code
   - Confirms selection in chosen language
   - Connects to WebSocket with `?lang=` parameter

3. **`/media-stream?lang=te-IN`** - WebSocket
   - Receives selected language
   - Uses it for all STT/LLM/TTS calls
   - No language detection needed

---

## Example Call

```
📞 User calls

🔊 IVR: "Press 1 for Telugu, 2 for Hindi..."

👤 User presses: 1

🔊 IVR: "తెలుగు. మీకు ఎలా సహాయం చేయగలను?"

👤 User: "మా ఊర్లో కరెంట్ లేదు"

🤖 AI: "క్షమించండి. మీ గ్రామం పేరు చెప్పగలరా?"

✅ Entire conversation in Telugu!
```

---

## Configuration

Language mapping in `twilio_server.py`:

```python
language_map = {
    "1": "te-IN",  # Telugu
    "2": "hi-IN",  # Hindi
    "3": "en-IN"   # English
}
```

To add more languages, update this mapping and add corresponding IVR prompts.
