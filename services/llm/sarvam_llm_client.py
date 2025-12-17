"""Clean Sarvam LLM HTTP client - LLM only, no frame processing."""
import aiohttp
from typing import List, Dict, Optional
from loguru import logger

from app.config import settings


class SarvamLLMClient:
    """
    Pure HTTP client for Sarvam LLM API only.
    
    ✅ Safe for Pipecat pipelines:
    - No frame processing
    - No STT/TTS mixing
    - Pure HTTP request/response
    - No Pipecat imports
    
    ❌ Does NOT handle:
    - Audio processing
    - Frame lifecycle
    - Pipeline ordering
    """
    
    def __init__(self):
        """Initialize LLM HTTP client."""
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Validate required settings
        if not settings.SARVAM_API_KEY:
            raise ValueError("SARVAM_API_KEY is required")
        if not settings.SARVAM_API_URL:
            raise ValueError("SARVAM_API_URL is required")
        
        self._llm_url = f"{settings.SARVAM_API_URL}/v1/chat/completions"
        logger.info(f"🤖 [LLM Client] Initialized for {self._llm_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=settings.LLM_TIMEOUT)
            )
        return self._session
    
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Send chat completion request to Sarvam LLM API.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Generated response text
            
        Raises:
            RuntimeError: If API request fails
        """
        session = await self._get_session()
        
        # Prepare request payload
        payload = {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "top_p": settings.LLM_TOP_P,
            "frequency_penalty": settings.LLM_FREQUENCY_PENALTY,
            "presence_penalty": settings.LLM_PRESENCE_PENALTY
        }
        
        # LLM uses Bearer token authentication
        headers = {
            "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"🤖 [LLM Client] Sending request with {len(messages)} messages")
        
        try:
            async with session.post(
                self._llm_url,
                json=payload,
                headers=headers
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ [LLM Client] API error {response.status}: {error_text}")
                    raise RuntimeError(f"Sarvam LLM API error {response.status}: {error_text}")
                
                # Parse successful response
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                
                logger.info(f"✅ [LLM Client] Response: {content[:100]}...")
                return content
                
        except aiohttp.ClientError as e:
            logger.error(f"❌ [LLM Client] Network error: {e}")
            raise RuntimeError(f"LLM network error: {e}")
        except KeyError as e:
            logger.error(f"❌ [LLM Client] Invalid response format: {e}")
            raise RuntimeError(f"LLM response format error: {e}")
    
    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("🤖 [LLM Client] Session closed")