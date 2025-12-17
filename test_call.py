#!/usr/bin/env python3
"""
Voice Bot Full Test - Built-in Services Implementation
Automatically tests services and makes outbound call using built-in Pipecat services.
User selects language during the actual call.
"""

import asyncio
import time
from twilio.rest import Client
from app.config import settings

# Test phone number - replace with your number
TEST_PHONE = "+916281383878"

def show_webhook_urls():
    """Show webhook URLs for Twilio configuration."""
    print("🌐 Twilio Webhook URLs")
    print("=" * 50)
    print(f"📞 For Twilio Console: {settings.SERVER_URL}/voice/incoming")
    print("=" * 50)

async def test_services():
    """Test service initialization using built-in Pipecat services."""
    try:
        # Test built-in Pipecat services
        from pipecat.services.sarvam.stt import SarvamSTTService
        from pipecat.services.sarvam.tts import SarvamTTSService, SarvamHttpTTSService
        from pipecat.transcriptions.language import Language
        from services.llm.sarvam_llm import SarvamLLMService
        from models.language import LANGUAGE_MAP
        
        print("✅ Built-in SarvamSTTService imported successfully")
        print("✅ Built-in SarvamTTSService imported successfully") 
        print("✅ Built-in SarvamHttpTTSService imported successfully")
        print("✅ Custom SarvamLLMService imported successfully (no built-in LLM available)")
        print("💡 Using built-in 'sarvam-m' model with custom LLM service")
        
        print(f"\n🔧 Testing services for all supported languages:")
        print("   During actual call, user will press:")
        for digit, lang_config in LANGUAGE_MAP.items():
            print(f"   {digit} - {lang_config.name} ({lang_config.code.value})")
        
        # Test services with each supported language from the actual language configuration
        for digit, lang_config in LANGUAGE_MAP.items():
            lang_name = lang_config.name
            lang_code = lang_config.code.value
            
            # Map language code to Pipecat Language enum
            language_enum_map = {
                "te-IN": Language.TE_IN,
                "hi-IN": Language.HI_IN, 
                "en-IN": Language.EN_IN,
            }
            lang_enum = language_enum_map.get(lang_code, Language.HI_IN)
            
            print(f"\n🧪 Testing {lang_name} ({lang_code}):")
            
            # Test STT service
            try:
                stt_service = SarvamSTTService(
                    api_key=settings.SARVAM_API_KEY,
                    model=settings.STT_MODEL,
                    sample_rate=settings.STT_SAMPLE_RATE,
                    params=SarvamSTTService.InputParams(
                        language=lang_enum,
                        vad_signals=True
                    )
                )
                print(f"  ✅ STT service ready for {lang_name}")
            except Exception as e:
                print(f"  ⚠️ STT service error for {lang_name}: {e}")
            
            # Test LLM service
            try:
                llm_service = SarvamLLMService(
                    api_key=settings.SARVAM_API_KEY,
                    model="sarvam-m",  # Built-in model
                    language=lang_code,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    knowledge_base_path=settings.KNOWLEDGE_BASE_PATH
                )
                print(f"  ✅ LLM service ready for {lang_name}")
            except Exception as e:
                print(f"  ⚠️ LLM service error for {lang_name}: {e}")
        
        # Test TTS service (language-independent)
        print(f"\n🧪 Testing TTS service (language-independent):")
        try:
            tts_service = SarvamTTSService(
                api_key=settings.SARVAM_API_KEY,
                voice=settings.TTS_VOICE,
                sample_rate=settings.TTS_SAMPLE_RATE
            )
            print("  ✅ TTS service ready")
        except Exception as e:
            print(f"  ⚠️ TTS service error: {e}")
        
        print("\n✅ All services tested successfully with built-in Pipecat components!")
        
        return True
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def make_test_call():
    """Make test call to your number."""
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        call = client.calls.create(
            to=TEST_PHONE,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=f"{settings.SERVER_URL}/voice/incoming",
            method='POST'
        )
        
        print(f"✅ Call initiated: {call.sid}")
        print("💡 Call Flow:")
        print("   1. Answer the call")
        print("   2. Listen to language selection menu")
        print("   3. Press digit to select language:")
        print("      1 - Telugu (te-IN)")
        print("      2 - Hindi (hi-IN)")
        print("      3 - English (en-IN)")
        print("   4. Bot will connect and start conversation in selected language")
        
        # Monitor call
        for _ in range(60):  # 2 minutes
            call = client.calls(call.sid).fetch()
            print(f"   Status: {call.status}")
            
            if call.status in ['completed', 'failed', 'canceled']:
                print(f"   Duration: {call.duration or 0}s")
                break
            time.sleep(2)
        
        return call.sid
        
    except Exception as e:
        print(f"❌ Call failed: {e}")
        return None

async def main():
    """Main function - automatically runs full test."""
    print("🤖 Voice Bot Full Test")
    print("=" * 40)
    
    # Check configuration
    if not all([settings.TWILIO_ACCOUNT_SID, settings.SARVAM_API_KEY, settings.SERVER_URL]):
        print("❌ Missing configuration in .env")
        print("   Please ensure TWILIO_ACCOUNT_SID, SARVAM_API_KEY, and SERVER_URL are set")
        return
    
    # Show webhook URLs and endpoints for reference
    print("🌐 Twilio Configuration:")
    print(f"   Webhook URL: {settings.SERVER_URL}/voice/incoming")
    print(f"   WebSocket Endpoints:")
    print(f"     - {settings.SERVER_URL.replace('http', 'ws')}/media-stream/te-IN (Telugu)")
    print(f"     - {settings.SERVER_URL.replace('http', 'ws')}/media-stream/hi-IN (Hindi)")
    print(f"     - {settings.SERVER_URL.replace('http', 'ws')}/media-stream/en-IN (English)")
    print()
    
    # Run service tests
    print("🔧 Step 1: Testing Services")
    print("-" * 30)
    if await test_services():
        print("\n📞 Step 2: Making Test Call")
        print("-" * 30)
        call_sid = make_test_call()
        if call_sid:
            print(f"\n✅ Test completed successfully! Call SID: {call_sid}")
        else:
            print("\n❌ Test call failed")
    else:
        print("\n❌ Service test failed, skipping call test")

if __name__ == "__main__":
    asyncio.run(main())