"""Sarvam AI LLM service with function calling support."""
import re
from typing import Optional
from loguru import logger

from pipecat.frames.frames import (
    LLMMessagesFrame,
    LLMTextFrame,
    StartFrame,
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame

from services.base import LLMService
from app.config import settings
from services.llm.sarvam_llm_client import SarvamLLMClient
from knowledge.loader import load_knowledge_base
from knowledge.rag_search import create_rag_search


class SarvamLLMService(LLMService):
    """
    Custom Sarvam LLM service for Pipecat 0.0.95.

    Contract:
    - INPUT  : OpenAILLMContextFrame (from LLMUserContextAggregator)
    - OUTPUT : LLMFullResponseStartFrame
               → LLMTextFrame (streaming)
               → LLMFullResponseEndFrame

    TTS is handled downstream by LLMAssistantContextAggregator.
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
        **kwargs,
    ):
        super().__init__(run_in_parallel=run_in_parallel, **kwargs)

        self._client = SarvamLLMClient()
        self._language = language
        self._model = model or settings.LLM_MODEL
        self._max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        self._temperature = temperature or settings.LLM_TEMPERATURE

        self.set_model_name(self._model)

        # Optional RAG
        self._rag_search = None
        if knowledge_base_path:
            try:
                kb = load_knowledge_base(knowledge_base_path)
                self._rag_search = create_rag_search(kb)
                logger.info(f"✅ [LLM] Knowledge base loaded ({len(kb.entries)} entries)")
            except Exception as e:
                logger.warning(f"⚠️ [LLM] KB load failed: {e}")

        logger.info(
            f"🤖 [LLM] SarvamLLMService initialized | model={self._model}, lang={self._language}"
        )

    async def process_frame(self, frame, direction: FrameDirection):
        # 1️⃣ Let base class register StartFrame (MANDATORY)
        if isinstance(frame, StartFrame):
            logger.info("🔥 [LLM] Received StartFrame - passing to base class")
            await super().process_frame(frame, direction)
            logger.info("🔥 [LLM] StartFrame processed by base class")
            # ✅ CRITICAL: Push StartFrame downstream so other processors can initialize!
            await self.push_frame(frame, direction)
            logger.info("🔥 [LLM] StartFrame pushed downstream")
            return

        # 2️⃣ Handle context frame produced by LLMUserContextAggregator (0.0.95 behavior)
        if isinstance(frame, OpenAILLMContextFrame):
            messages = frame.context.messages
            logger.info(f"📥 [LLM] Received OpenAILLMContextFrame with {len(messages)} messages")
            await self._handle_messages(messages)  # call your inference path
            return

        # 3️⃣ EVERYTHING ELSE → base class
        await super().process_frame(frame, direction)

    async def _handle_messages(self, messages: list):
        try:

            if not messages:
                logger.warning("[LLM] Empty message list")
                await self._close_response_window()
                return

            last_user = next(
                (m.get("content", "").strip()
                 for m in reversed(messages)
                 if m.get("role") == "user"),
                None,
            )

            if not last_user:
                logger.warning("[LLM] Empty user message (VAD noise?)")
                await self._close_response_window()
                return

            fixed_messages = self._fix_message_alternation(messages)
            enhanced_messages = self._enhance_with_knowledge(fixed_messages)

            logger.info("🤖 [LLM] Calling Sarvam API...")
            response = await self._call_llm(enhanced_messages)

            if not response:
                logger.warning("❌ [LLM] No response from model")
                await self._close_response_window()
                return

            logger.info(f"✅ [LLM] Generated response: {response[:100]}...")
            await self._stream_response(response)

        except Exception as e:
            logger.error(f"❌ [LLM] Fatal error: {e}", exc_info=True)
            await self._close_response_window()

    async def _close_response_window(self):
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

    async def _stream_response(self, text: str):
        logger.info(f"📤 [LLM] Starting to stream response: {len(text)} chars")
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        logger.info("📤 [LLM] Pushed LLMFullResponseStartFrame")

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        logger.info(f"📤 [LLM] Split into {len(sentences)} sentences")
        for i, sentence in enumerate(sentences):
            if sentence:
                logger.info(f"📤 [LLM] Pushing sentence {i+1}/{len(sentences)}: {sentence[:50]}...")
                await self.push_frame(
                    LLMTextFrame(sentence),
                    FrameDirection.DOWNSTREAM,
                )
                logger.info(f"✅ [LLM] Sentence {i+1} pushed successfully")

        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        logger.info("📤 [LLM] Pushed LLMFullResponseEndFrame - streaming complete")

    def _fix_message_alternation(self, messages: list) -> list:
        fixed, last_role = [], None

        for msg in messages:
            role, content = msg.get("role"), msg.get("content", "").strip()
            if not content:
                continue

            if role == last_role and fixed:
                if role == "user":
                    fixed[-1]["content"] += f"\n{content}"
                elif role == "assistant":
                    fixed[-1] = msg
            else:
                fixed.append(msg)
                last_role = role

        return fixed

    def _enhance_with_knowledge(self, messages: list) -> list:
        if not self._rag_search:
            return messages

        user_query = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            None,
        )

        if not user_query:
            return messages

        entries = self._rag_search.search(
            user_query,
            language=self._language,
            limit=settings.KNOWLEDGE_SEARCH_LIMIT,
            min_score=settings.KNOWLEDGE_MIN_SCORE,
        )

        if not entries:
            return messages

        kb_block = "\n\n📚 RELEVANT KNOWLEDGE:\n"
        for e in entries:
            kb_block += f"\nQ: {e.question}\nA: {e.answer}\n"

        enriched = messages.copy()
        for i in range(len(enriched) - 1, -1, -1):
            if enriched[i]["role"] == "user":
                enriched[i]["content"] += kb_block
                break

        return enriched

    async def _call_llm(self, messages: list) -> Optional[str]:
        return await self._client.chat(messages)

    async def cleanup(self):
        await self._client.close()
        logger.debug("[LLM] Cleanup complete")
