"""Sarvam AI LLM service using Pipecat LLMService."""
from typing import Optional
from loguru import logger
from pipecat.services.llm_service import LLMService
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import (
    LLMContextFrame,
    UserSpeakingFrame,
    BotSpeakingFrame,
    UserStartedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
    InterruptionFrame,
    StartFrame,
    MetricsFrame
)

from app.config import settings
from knowledge.loader import load_knowledge_base
from knowledge.rag_search import create_rag_search


class SarvamLLMService(LLMService):
    """
    Sarvam AI LLM service using Pipecat's LLMService base class.
    
    Follows Pipecat's standard pattern:
    - Extends LLMService
    - Implements run_inference() to generate responses
    - Base class handles message processing and function calls
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "sarvam-m",
        language: str = "en-IN",
        max_tokens: int = 512,
        temperature: float = 0.7,
        knowledge_base_path: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Sarvam LLM service.
        
        Args:
            api_key: Sarvam API key
            model: LLM model name
            language: Language code
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            knowledge_base_path: Path to knowledge base file
        """
        super().__init__(**kwargs)
        
        from services.sarvam_ai import SarvamAI
        
        self._sarvam = SarvamAI()
        self._language = language
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        
        # Set model name for metrics
        self.set_model_name(model)
        
        # Load knowledge base with enhanced RAG search
        self._knowledge_base = None
        self._rag_search = None
        if knowledge_base_path:
            try:
                self._knowledge_base = load_knowledge_base(knowledge_base_path)
                self._rag_search = create_rag_search(self._knowledge_base)
                logger.info(f"✅ [LLM] Loaded knowledge base with {len(self._knowledge_base.entries)} entries")
                logger.info(f"✅ [LLM] Enhanced RAG search initialized")
            except Exception as e:
                logger.warning(f"⚠️ [LLM] Failed to load knowledge base: {e}")
        
        logger.info(f"🤖 [LLM] Initialized SarvamLLMService: language={language}, model={model}")
    
    async def process_frame(self, frame, direction):
        """Process frames - handle LLMContextFrame manually."""
        from pipecat.frames.frames import LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame
        
        frame_type = type(frame).__name__
        
        # Only log critical frames (LLMContextFrame, VAD events, interruptions)
        # Skip: UserSpeakingFrame, BotSpeakingFrame, StartFrame, MetricsFrame
        if isinstance(frame, (LLMContextFrame, UserStartedSpeakingFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame, InterruptionFrame)):
            logger.info(f"🎯 [LLM] Received frame: {frame_type}")
        
        # Handle LLMContextFrame manually (base class doesn't handle it)
        if isinstance(frame, LLMContextFrame):
            logger.info(f"🎯 [LLM] LLMContextFrame received - processing manually")
            context = frame.context
            logger.info(f"🎯 [LLM] Context has {len(context.messages)} messages")
            # Log the messages for debugging
            for i, msg in enumerate(context.messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:80]
                logger.info(f"  📝 Message {i}: [{role}] {content}...")
            
            try:
                # Start response
                await self.push_frame(LLMFullResponseStartFrame())
                await self.start_processing_metrics()
                
                # Run inference
                response_text = await self.run_inference(context)
                
                if response_text:
                    # Push response as text frames (TTS will handle it)
                    await self.push_frame(LLMTextFrame(response_text))
                
            except Exception as e:
                logger.error(f"❌ [LLM] Error processing context: {e}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                await self.stop_processing_metrics()
                await self.push_frame(LLMFullResponseEndFrame())
            
            return  # Don't call super() for LLMContextFrame
        
        # For all other frames, call base class
        await super().process_frame(frame, direction)
    
    async def run_inference(self, context: LLMContext) -> Optional[str]:
        """
        Run LLM inference on the given context.
        
        This is called by the base LLMService when it receives an LLMMessagesFrame.
        
        Args:
            context: LLM context containing conversation messages
            
        Returns:
            Generated response text or None
        """
        try:
            logger.info("=" * 80)
            logger.info("🤖 [CHECKPOINT 9] LLM RUNNING INFERENCE!")
            logger.info(f"🤖 [LLM] Context has {len(context.messages)} messages")
            logger.info("=" * 80)
            
            # Get messages from context
            messages = context.messages
            
            if not messages:
                logger.warning("[LLM] No messages in context")
                return None
            
            # Get last user message for RAG
            user_message = None
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_message = msg.get('content', '')
                    break
            
            # Enhance with knowledge base
            enhanced_messages = self._enhance_with_knowledge(messages, user_message)
            
            # Call LLM API
            response_text = await self._call_llm(enhanced_messages)
            
            if response_text:
                logger.info(f"✅ [LLM] Generated response: {response_text[:100]}...")
                return response_text
            else:
                logger.warning("[LLM] Empty response generated")
                return None
                
        except Exception as e:
            logger.error(f"❌ [LLM] Error in run_inference: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _enhance_with_knowledge(self, messages: list, user_query: Optional[str]) -> list:
        """
        Enhance messages with knowledge base context using enhanced RAG.
        
        Args:
            messages: Conversation messages
            user_query: Latest user query
            
        Returns:
            Enhanced messages list
        """
        if not self._rag_search or not user_query:
            return messages
        
        try:
            # Search knowledge base with enhanced RAG
            relevant_entries = self._rag_search.search(
                user_query,
                language=self._language,
                limit=3,
                min_score=10.0  # Minimum relevance score
            )
            
            if relevant_entries:
                # Build context from knowledge base
                kb_context = "\n\n📚 RELEVANT KNOWLEDGE BASE:\n"
                for entry in relevant_entries:
                    kb_context += f"\nQ: {entry.question}\nA: {entry.answer}\n"
                
                logger.info(f"📚 [LLM] Found {len(relevant_entries)} relevant Q&A pairs for user query")
                
                # Enhance the last user message with knowledge base context
                enhanced = messages.copy()
                
                # Find last user message index
                last_user_idx = None
                for i in range(len(enhanced) - 1, -1, -1):
                    if enhanced[i].get('role') == 'user':
                        last_user_idx = i
                        break
                
                if last_user_idx is not None:
                    # Append knowledge base context to user message
                    original_content = enhanced[last_user_idx].get('content', '')
                    enhanced[last_user_idx] = {
                        'role': 'user',
                        'content': original_content + kb_context
                    }
                    logger.info(f"📚 [LLM] Enhanced user query with knowledge base context")
                
                return enhanced
            
        except Exception as e:
            logger.warning(f"[LLM] Failed to enhance with knowledge base: {e}")
        
        return messages
    
    async def _call_llm(self, messages: list) -> Optional[str]:
        """
        Call Sarvam LLM API.
        
        Args:
            messages: Conversation messages
            
        Returns:
            Generated response text or None
        """
        try:
            logger.debug(f"[LLM] Calling Sarvam API for chat completion")
            
            # Use Sarvam AI wrapper with retry logic
            response = await self._sarvam.chat(
                messages,
                retry_count=2,
                timeout=15
            )
            
            return response if response else None
            
        except Exception as e:
            logger.error(f"[LLM] Generation failed: {e}")
            return None
    
    async def cleanup(self):
        """Cleanup resources."""
        await self._sarvam.close()
        logger.debug("[LLM] Cleanup complete")
