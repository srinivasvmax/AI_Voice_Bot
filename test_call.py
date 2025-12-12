#!/usr/bin/env python3
"""
Simple Voice Bot Test - Clean Implementation
Makes outbound call for testing.
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
    """Test service initialization."""
    try:
        from services.sarvam_ai import SarvamAI
        from services.stt.sarvam_stt import SarvamSTTService
        from services.llm.sarvam_llm import SarvamLLMService
        from services.tts.sarvam_tts_processor import SarvamTTSProcessor
        
        # Test service initialization (without language - just check imports)
        sarvam = SarvamAI()
        print("✅ SarvamAI service imported successfully")
        
        # Test that service classes can be imported (don't initialize without language)
        print("✅ STT service class imported successfully")
        print("✅ LLM service class imported successfully") 
        print("✅ TTS processor class imported successfully")
        
        print("✅ All service classes available")
        
        # Cleanup
        await sarvam.close()
        
        return True
    except Exception as e:
        print(f"❌ Service test failed: {e}")
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
        print("💡 Answer and select your language:")
        print("   1 - Telugu")
        print("   2 - Hindi") 
        print("   3 - English")
        
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
    """Main function."""
    print("🤖 Voice Bot Test")
    print("=" * 30)
    
    if not all([settings.TWILIO_ACCOUNT_SID, settings.SARVAM_API_KEY, settings.SERVER_URL]):
        print("❌ Missing configuration in .env")
        return
    
    print("1. 🔧 Test services")
    print("2. 📞 Make test call") 
    print("3. 🌐 Show webhook URLs")
    print("4. 🚀 Full test")
    
    choice = input("\nChoice (1-4): ").strip()
    
    if choice == "1":
        await test_services()
    elif choice == "2":
        make_test_call()
    elif choice == "3":
        show_webhook_urls()
    elif choice == "4":
        if await test_services():
            make_test_call()

if __name__ == "__main__":
    asyncio.run(main())