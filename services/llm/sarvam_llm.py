"""Sarvam AI LLM service with function calling support."""
import re
from typing import Optional
from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantAggregatorParams,
    LLMUserAggregatorParams,
)
from pipecat.frames.frames import LLMMessagesFrame, LLMTextFrame, StartFrame
from pipecat.processors.frame_processor import FrameDirection

from services.base import LLMService
from app.config import settings
from services.sarvam_ai import SarvamAI
from knowledge.loader import load_knowledge_base
from knowledge.rag_search import create_rag_search


class SarvamLLMService(LLMService):
    """Sarvam AI LLM service with function calling support.
    
    Provides LLM inference using Sarvam AI's chat completion API with:
    - Function calling support (parallel and sequential execution)
    - Knowledge base integration via RAG search
    - Message alternation fixing for API compliance
    - Comprehensive error handling and retry logic
    
    Inherits from the base LLMService which handles:
    - Function registration and execution
    - Frame processing and routing
    - Event handling and metrics
    - Interruption management
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = None,
        language: str = None,
        max_tokens: int = None,
        temperature: float = None,
        knowledge_base_path: Optional[str] = None,
        run_in_parallel: bool = True,
        **kwargs
    ):
        """Initialize Sarvam LLM service."""
        from app.config import settings
        
        # Use config defaults if not provided
        model = model or settings.LLM_MODEL
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        temperature = temperature or settings.LLM_TEMPERATURE
        
        super().__init__(run_in_parallel=run_in_parallel, **kwargs)
        
        # WORKAROUND: Ensure _FrameProcessor__process_queue is initialized
        # This fixes the Pipecat 0.0.97 compatibility issue
        if not hasattr(self, '_FrameProcessor__process_queue'):
            import asyncio
            self._FrameProcessor__process_queue = asyncio.Queue()
            logger.debug("🔧 [LLM] Applied _FrameProcessor__process_queue workaround")
        
        self._sarvam = SarvamAI()
        self._language = language
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        
        # Set model name for metrics
        self.set_model_name(model)
        
        # Load knowledge base
        self._rag_search = None
        if knowledge_base_path:
            try:
                knowledge_base = load_knowledge_base(knowledge_base_path)
                self._rag_search = create_rag_search(knowledge_base)
                logger.info(f"✅ [LLM] Loaded knowledge base with {len(knowledge_base.entries)} entries")
            except Exception as e:
                logger.warning(f"⚠️ [LLM] Failed to load knowledge base: {e}")
        
        logger.info(f"🤖 [LLM] Initialized SarvamLLMService: language={self._language}, model={self._model}")
    
    def create_context_aggregator(
        self,
        context: OpenAILLMContext,
        *,
        user_params: LLMUserAggregatorParams = LLMUserAggregatorParams(),
        assistant_params: LLMAssistantAggregatorParams = LLMAssistantAggregatorParams(),
    ):
        """WORKAROUND: Bypass problematic LLMAssistantContextAggregator.
        
        This fixes the Pipecat compatibility issue:
        'LLMAssistantContextAggregator' object has no attribute '_FrameProcessor__process_queue'
        """
        logger.warning("⚠️ Using aggregator workaround to bypass Pipecat compatibility issue")
        
        # Proper workaround aggregator that inherits from FrameProcessor
        from pipecat.processors.frame_processor import FrameProcessor
        from pipecat.frames.frames import Frame
        
        class WorkaroundAggregator(FrameProcessor):
            def __init__(self):
                super().__init__()
                self._user_aggregator = self
                self._assistant_aggregator = self
            
            def user(self):
                return self._user_aggregator
            
            def assistant(self):
                return self._assistant_aggregator
            
            async def process_frame(self, frame: Frame, direction):
                # Just pass frames through without aggregation
                await self.push_frame(frame, direction)
        
        return WorkaroundAggregator()
    
    async def process_frame(self, frame, direction: FrameDirection):
        """Process frames, specifically handling LLMMessagesFrame."""
        # Only log important frames, not audio frames
        if not type(frame).__name__.endswith('AudioRawFrame'):
            logger.info(f"🤖 [LLM] Received frame: {type(frame).__name__} (direction: {direction})")
        
        if isinstance(frame, LLMMessagesFrame):
            logger.info("🤖 [CHECKPOINT 8] LLM received LLMMessagesFrame!")
            logger.info(f"🤖 [LLM] Processing {len(frame.messages)} messages")
            
            # Log message details (disabled to reduce verbosity)
            # for i, msg in enumerate(frame.messages):
            #     logger.info(f"🤖 [LLM] Message {i}: role={msg.get('role')}, content='{msg.get('content', '')[:100]}...'")
            
            # Handle LLMMessagesFrame ourselves since base class might not
            try:
                # Create context from messages
                context = OpenAILLMContext(frame.messages)
                
                # Run inference
                response = await self.run_inference(context)
                
                if response:
                    logger.info(f"🤖 [LLM] Generated response: {response[:100]}...")
                    # Break long output into TTS-friendly chunks
                    await self._push_chunked_response(response)
                else:
                    logger.warning("🤖 [LLM] No response generated")
            except Exception as e:
                logger.error(f"❌ [LLM] Error processing LLMMessagesFrame: {e}")
                import traceback
                logger.error(traceback.format_exc())
        elif hasattr(frame, '__class__') and 'LLMContext' in frame.__class__.__name__:
            # Handle OpenAILLMContextFrame or similar context frames
            logger.info(f"🤖 [CHECKPOINT 8B] LLM received context frame: {type(frame).__name__}")
            
            try:
                # Inspect the frame to understand its structure (disabled to reduce verbosity)
                # logger.info(f"🤖 [LLM] Frame attributes: {[attr for attr in dir(frame) if not attr.startswith('_')]}")
                
                # Check if frame has context or messages
                if hasattr(frame, 'context'):
                    context = frame.context
                    logger.info(f"🤖 [LLM] Context frame has context with {len(context.messages)} messages")
                    
                    # Log context messages (disabled to reduce verbosity)
                    # for i, msg in enumerate(context.messages):
                    #     logger.info(f"🤖 [LLM] Context Message {i}: {msg}")
                        
                elif hasattr(frame, 'messages'):
                    context = OpenAILLMContext(frame.messages)
                    logger.info(f"🤖 [LLM] Context frame has {len(frame.messages)} messages")
                    
                    # Log frame messages (disabled to reduce verbosity)
                    # for i, msg in enumerate(frame.messages):
                    #     logger.info(f"🤖 [LLM] Frame Message {i}: {msg}")
                        
                else:
                    logger.warning(f"🤖 [LLM] Unknown context frame structure")
                    logger.info(f"🤖 [LLM] Frame type: {type(frame)}")
                    logger.info(f"🤖 [LLM] Frame dir: {dir(frame)}")
                    await super().process_frame(frame, direction)
                    return
                
                # Run inference
                response = await self.run_inference(context)
                
                if response:
                    logger.info(f"🤖 [LLM] Generated response: {response[:100]}...")
                    # Break long output into TTS-friendly chunks
                    await self._push_chunked_response(response)
                else:
                    logger.warning("🤖 [LLM] No response generated")
            except Exception as e:
                logger.error(f"❌ [LLM] Error processing context frame: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            # Call parent for all other frames (including StartFrame)
            if isinstance(frame, StartFrame):
                logger.info("🤖 [LLM] Forwarding StartFrame to next service")
            await super().process_frame(frame, direction)
    
    async def run_inference(self, context: LLMContext | OpenAILLMContext) -> Optional[str]:
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
            logger.info(f"🤖 [LLM] Context type: {type(context)}")
            logger.info(f"🤖 [LLM] Context has {len(context.messages)} messages")
            
            # Log context messages (disabled to reduce verbosity)
            # for i, msg in enumerate(context.messages):
            #     logger.info(f"🤖 [LLM] Context Message {i}: {msg}")
            
            logger.info("=" * 80)
            
            # Get messages from context
            messages = context.messages
            
            if not messages:
                logger.warning("[LLM] No messages in context")
                return None
            
            # Fix message alternation: ensure user and assistant messages alternate
            fixed_messages = self._fix_message_alternation(messages)
            
            # Get last user message for RAG
            user_message = None
            for msg in reversed(fixed_messages):
                if msg.get('role') == 'user':
                    user_message = msg.get('content')
                    break
            
            # Enhance with knowledge base
            enhanced_messages = self._enhance_with_knowledge(fixed_messages, user_message)
            
            # Call LLM API
            response_text = await self._call_llm(enhanced_messages)
            
            if response_text:
                logger.info(f"✅ [LLM] Generated response: {response_text[:100]}...")
                return response_text
            else:
                logger.warning("[LLM] No response generated")
                return None
                
        except Exception as e:
            logger.error(f"❌ [LLM] Error in run_inference: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _fix_message_alternation(self, messages: list) -> list:
        """Fix message alternation for API compliance."""
        if not messages:
            return messages
        
        fixed = []
        last_role = None
        
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '').strip()
            
            if not content:
                continue
            
            if role == 'system':
                fixed.append(msg)
                last_role = role
                continue
            
            if role == last_role:
                if role == 'user' and fixed and fixed[-1].get('role') == 'user':
                    # Merge consecutive user messages
                    fixed[-1]['content'] += f"\n{content}"
                elif role == 'assistant' and fixed and fixed[-1].get('role') == 'assistant':
                    # Replace with newer assistant message
                    fixed[-1] = msg
                else:
                    fixed.append(msg)
            else:
                fixed.append(msg)
                last_role = role
        
        # Ensure starts with user message (after system)
        first_non_system_idx = None
        for i, msg in enumerate(fixed):
            if msg.get('role') != 'system':
                first_non_system_idx = i
                break
        
        if first_non_system_idx is not None and fixed[first_non_system_idx].get('role') != 'user':
            fixed.pop(first_non_system_idx)
        
        return fixed
    
    def _enhance_with_knowledge(self, messages: list, user_query: Optional[str]) -> list:
        """Enhance messages with knowledge base context."""
        if not self._rag_search or not messages:
            return messages
        
        try:
            # Get last user message
            user_query = None
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_query = msg.get('content')
                    break
            
            if not user_query:
                return messages
            
            # Search knowledge base
            relevant_entries = self._rag_search.search(
                user_query,
                language=self._language,
                limit=settings.KNOWLEDGE_SEARCH_LIMIT,
                min_score=settings.KNOWLEDGE_MIN_SCORE
            )
            
            if relevant_entries:
                # Add knowledge context to last user message
                kb_context = "\n\n📚 RELEVANT KNOWLEDGE:\n"
                for entry in relevant_entries:
                    kb_context += f"\nQ: {entry.question}\nA: {entry.answer}\n"
                
                enhanced = messages.copy()
                for i in range(len(enhanced) - 1, -1, -1):
                    if enhanced[i].get('role') == 'user':
                        enhanced[i] = {
                            'role': 'user',
                            'content': enhanced[i].get('content', '') + kb_context
                        }
                        break
                
                logger.info(f"📚 [LLM] Enhanced with {len(relevant_entries)} knowledge entries")
                return enhanced
            
        except Exception as e:
            logger.warning(f"[LLM] Knowledge enhancement failed: {e}")
        
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
            logger.info(f"🤖 [CHECKPOINT 10] Calling Sarvam LLM API with {len(messages)} messages")
            
            # Log the exact payload being sent
            for i, msg in enumerate(messages):
                logger.info(f"🤖 [LLM API] Message {i}: {msg}")
            
            # Use Sarvam AI wrapper with retry logic
            result = await self._sarvam.chat(
                messages,
                retry_count=settings.LLM_RETRY_COUNT,
                timeout=settings.LLM_TIMEOUT
            )
            
            # Parse Sarvam chat response safely
            content = self._parse_sarvam_response(result)
            
            logger.info(f"🤖 [CHECKPOINT 11] LLM API returned: {content[:200] if content else 'None'}...")
            
            return content if content else None
            
        except Exception as e:
            logger.error(f"❌ [LLM] Generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _parse_sarvam_response(self, result) -> Optional[str]:
        """Parse Sarvam chat response safely."""
        if isinstance(result, dict):
            # Try standard chat completion structure
            choices = result.get("choices") or []
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content") or choices[0].get("text")
                if content:
                    return content
            
            # Fallback to direct text field
            content = result.get("text")
            if content:
                return content
        
        # If it's already a string, use it
        if isinstance(result, str):
            return result
        
        # Last resort - convert to string
        return str(result) if result else None
    
    async def _push_chunked_response(self, response: str):
        """Break long output into TTS-friendly chunks and push as LLMTextFrames."""
        logger.info(f"🚨 [LLM] _push_chunked_response called with: {response[:100]}...")
        
        # Naive sentence split for better TTS interruption/latency handling
        sentences = re.split(r'(?<=[.!?])\s+', response.strip())
        
        logger.info(f"🚨 [LLM] Split into {len(sentences)} sentences")
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if sentence:  # Only push non-empty sentences
                logger.info(f"🚨 [LLM] Pushing sentence {i+1}: {sentence[:50]}...")
                await self.push_frame(LLMTextFrame(sentence))
                logger.info(f"✅ [LLM] Successfully pushed LLMTextFrame {i+1}")
            else:
                logger.warning(f"⚠️ [LLM] Skipping empty sentence {i+1}")
        
        logger.info(f"🎉 [LLM] Finished pushing {len([s for s in sentences if s.strip()])} LLMTextFrames")
    
    async def cleanup(self):
        """Cleanup resources."""
        await self._sarvam.close()
        logger.debug("[LLM] Cleanup complete")