"""Sarvam AI API wrapper with retry logic and error handling."""
import asyncio
import aiohttp
import base64
from typing import Optional, Tuple, List, Dict, Any
from loguru import logger

from app.config import settings


class SarvamAI:
    """
    Wrapper for Sarvam AI API with retry logic and statistics tracking.
    
    Provides:
    - Speech-to-Text (STT)
    - Language Model (LLM)
    - Text-to-Speech (TTS)
    - Automatic retries
    - Statistics tracking
    """
    
    def __init__(self):
        """Initialize Sarvam AI client."""
        self.api_key = settings.SARVAM_API_KEY
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable is required")
        
        self.stt_url = f"{settings.SARVAM_API_URL}/speech-to-text"
        self.tts_url = f"{settings.SARVAM_API_URL}/text-to-speech"
        self.llm_url = f"{settings.SARVAM_API_URL}/v1/chat/completions"
        
        self.session = None
        self._session_lock = False
        
        # Statistics tracking
        self.stats = {
            "stt_calls": 0,
            "stt_success": 0,
            "stt_failures": 0,
            "llm_calls": 0,
            "llm_success": 0,
            "llm_failures": 0,
            "tts_calls": 0,
            "tts_success": 0,
            "tts_failures": 0,
            "total_audio_bytes_processed": 0
        }
    
    async def get_session(self):
        """Get or create aiohttp session with proper error handling."""
        try:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession(
                    headers={"API-Subscription-Key": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            return self.session
        except Exception as e:
            logger.error(f"❌ Failed to create aiohttp session: {e}")
            raise
    
    async def speech_to_text(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
        retry_count: int = 2,
        timeout: int = 15
    ) -> Tuple[str, str]:
        """
        Convert speech to text with language detection, retry logic, and timeout.
        
        Args:
            audio_bytes: WAV audio bytes
            language: Language code (if None, tries multiple languages)
            retry_count: Number of retries
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (transcription, detected_language)
        """
        self.stats["stt_calls"] += 1
        self.stats["total_audio_bytes_processed"] += len(audio_bytes)
        
        for attempt in range(retry_count):
            try:
                logger.info(f"🎤 STT: Received {len(audio_bytes)} bytes of audio (attempt {attempt + 1}/{retry_count})")
                
                session = await self.get_session()
                
                # If no language specified, try multiple languages
                if language is None:
                    languages = ["te-IN", "hi-IN", "en-IN"]
                    default_language = "te-IN"
                else:
                    languages = [language]
                    default_language = language
                
                best_result = ""
                best_language = default_language
                results = []
                
                for lang in languages:
                    try:
                        data = aiohttp.FormData()
                        data.add_field('file', audio_bytes, filename='audio.wav', content_type='audio/wav')
                        data.add_field('language_code', lang)
                        data.add_field('model', settings.STT_MODEL)
                        
                        logger.debug(f"📤 Sending STT request for {lang}: {len(audio_bytes)} bytes")
                        
                        async with session.post(
                            self.stt_url,
                            data=data,
                            timeout=aiohttp.ClientTimeout(total=timeout)
                        ) as response:
                            response_text = await response.text()
                            
                            if response.status == 200:
                                result = await response.json() if response_text else {}
                                logger.debug(f"📥 Full STT response: {result}")
                                
                                text = result.get("transcript", "")
                                logger.info(f"📥 STT response ({lang}): status={response.status}, transcript='{text}'")
                                
                                if text and len(text.strip()) > 0:
                                    results.append({
                                        'lang': lang,
                                        'text': text,
                                        'length': len(text)
                                    })
                                    logger.info(f"✅ STT success ({lang}): '{text}' (length: {len(text)})")
                                    
                                    # If language was specified, use first valid result
                                    if language:
                                        best_result = text
                                        best_language = lang
                                        break
                                else:
                                    logger.warning(f"⚠️ STT returned empty transcript for {lang}")
                            else:
                                logger.error(f"❌ STT API error for {lang}: {response.status}")
                                logger.error(f"Response body: {response_text[:500]}")
                                
                    except asyncio.TimeoutError:
                        logger.warning(f"⏱️ STT timeout for {lang}")
                        continue
                    except Exception as lang_error:
                        logger.warning(f"⚠️ STT error for {lang}: {lang_error}")
                        import traceback
                        logger.debug(traceback.format_exc())
                        continue
                
                # If no language specified, pick the first result
                if not language and results:
                    best_result = results[0]['text']
                    best_language = results[0]['lang']
                    logger.info(f"✅ Using first result ({best_language}) as most likely correct")
                
                if best_result:
                    logger.info(f"✅ STT Final ({best_language}): {best_result}")
                    self.stats["stt_success"] += 1
                    return best_result, best_language
                else:
                    logger.warning(f"⚠️ STT: No speech detected in any language (tried: {', '.join(languages)})")
                    if attempt < retry_count - 1:
                        logger.info(f"🔄 Retrying STT...")
                        await asyncio.sleep(0.5)
                        continue
                    
                    self.stats["stt_failures"] += 1
                    return "", default_language
                    
            except Exception as e:
                logger.error(f"❌ STT exception (attempt {attempt + 1}/{retry_count}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                self.stats["stt_failures"] += 1
                return "", language or "en-IN"
        
        self.stats["stt_failures"] += 1
        return "", language or "en-IN"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        retry_count: int = 2,
        timeout: int = 15
    ) -> str:
        """
        Get LLM response with retry logic and timeout handling.
        
        Args:
            messages: Conversation messages
            retry_count: Number of retries
            timeout: Request timeout in seconds
            
        Returns:
            Generated response text
        """
        self.stats["llm_calls"] += 1
        
        # Fallback responses based on language
        fallback_responses = {
            "en": "I'm having trouble processing your request right now. Please try again or contact customer support.",
            "te": "నేను ప్రస్తుతం మీ అభ్యర్థనను ప్రాసెస్ చేయడంలో ఇబ్బంది పడుతున్నాను. దయచేసి మళ్లీ ప్రయత్నించండి లేదా కస్టమర్ సపోర్ట్‌ను సంప్రదించండి.",
            "hi": "मुझे अभी आपके अनुरोध को संसाधित करने में परेशानी हो रही है। कृपया पुनः प्रयास करें या ग्राहक सहायता से संपर्क करें।"
        }
        
        # Detect language from messages
        detected_lang = "en"
        for msg in messages:
            content = msg.get("content", "")
            if "Telugu" in content:
                detected_lang = "te"
                break
            elif "Hindi" in content:
                detected_lang = "hi"
                break
        
        for attempt in range(retry_count):
            try:
                session = await self.get_session()
                
                payload = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_tokens": settings.LLM_MAX_TOKENS,
                    "top_p": settings.LLM_TOP_P,
                    "frequency_penalty": settings.LLM_FREQUENCY_PENALTY,
                    "presence_penalty": settings.LLM_PRESENCE_PENALTY
                }
                
                # Use Authorization header for LLM endpoint
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    self.llm_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result["choices"][0]["message"]["content"]
                        logger.info(f"LLM: {text}")
                        self.stats["llm_success"] += 1
                        return text
                    else:
                        error_text = await response.text()
                        logger.error(f"LLM error {response.status}: {error_text}")
                        
                        if attempt < retry_count - 1:
                            logger.info(f"🔄 Retrying LLM...")
                            await asyncio.sleep(0.5)
                            continue
                        
                        # Return language-appropriate fallback
                        self.stats["llm_failures"] += 1
                        return fallback_responses.get(detected_lang, fallback_responses["en"])
                        
            except asyncio.TimeoutError:
                logger.error(f"⏱️ LLM timeout (attempt {attempt + 1}/{retry_count})")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                # Return language-appropriate timeout message
                timeout_msgs = {
                    "en": "I'm taking too long to respond. Please ask your question again.",
                    "te": "నేను స్పందించడానికి చాలా సమయం తీసుకుంటున్నాను. దయచేసి మీ ప్రశ్నను మళ్లీ అడగండి.",
                    "hi": "मुझे जवाब देने में बहुत समय लग रहा है। कृपया अपना प्रश्न फिर से पूछें।"
                }
                return timeout_msgs.get(detected_lang, timeout_msgs["en"])
                
            except Exception as e:
                logger.error(f"LLM exception (attempt {attempt + 1}/{retry_count}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                self.stats["llm_failures"] += 1
                return fallback_responses.get(detected_lang, fallback_responses["en"])
        
        self.stats["llm_failures"] += 1
        return fallback_responses.get(detected_lang, fallback_responses["en"])
    
    async def text_to_speech(
        self,
        text: str,
        language: str = "hi-IN",
        retry_count: int = 2,
        timeout: int = 20
    ) -> bytes:
        """
        Convert text to speech with retry logic and timeout handling.
        
        Args:
            text: Text to synthesize
            language: Language code
            retry_count: Number of retries
            timeout: Request timeout in seconds
            
        Returns:
            WAV audio bytes (empty bytes if failed)
        """
        self.stats["tts_calls"] += 1
        
        for attempt in range(retry_count):
            try:
                session = await self.get_session()
                
                payload = {
                    "inputs": [text],
                    "target_language_code": language,
                    "speaker": "anushka",  # Valid speaker from API
                    "pitch": 0,
                    "pace": 1.0,
                    "loudness": 1.5,
                    "speech_sample_rate": 8000,  # 8kHz for Twilio
                    "enable_preprocessing": True,
                    "model": settings.TTS_MODEL
                }
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    self.tts_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        audio_base64 = result["audios"][0]
                        audio_bytes = base64.b64decode(audio_base64)
                        logger.info(f"TTS: Generated {len(audio_bytes)} bytes")
                        self.stats["tts_success"] += 1
                        return audio_bytes
                    else:
                        error_text = await response.text()
                        logger.error(f"TTS error {response.status}: {error_text}")
                        
                        if attempt < retry_count - 1:
                            logger.info(f"🔄 Retrying TTS...")
                            await asyncio.sleep(0.5)
                            continue
                        
                        logger.error("❌ TTS failed after all retries - returning empty audio")
                        self.stats["tts_failures"] += 1
                        return b""
                        
            except asyncio.TimeoutError:
                logger.error(f"⏱️ TTS timeout (attempt {attempt + 1}/{retry_count})")
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                logger.error("❌ TTS timeout after all retries - returning empty audio")
                return b""
                
            except Exception as e:
                logger.error(f"TTS exception (attempt {attempt + 1}/{retry_count}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                if attempt < retry_count - 1:
                    await asyncio.sleep(0.5)
                    continue
                
                logger.error("❌ TTS exception after all retries - returning empty audio")
                self.stats["tts_failures"] += 1
                return b""
        
        logger.error("❌ TTS failed completely - returning empty audio")
        self.stats["tts_failures"] += 1
        return b""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return self.stats.copy()
    
    async def close(self):
        """Close session safely."""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("✅ Sarvam AI session closed")
        except Exception as e:
            logger.warning(f"⚠️ Error closing session: {e}")
