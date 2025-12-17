"""Clean pipeline builder using built-in Pipecat services only."""
import asyncio
from typing import Optional
from loguru import logger
import aiohttp

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams

# Built-in Pipecat services
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService, SarvamHttpTTSService
from pipecat.transcriptions.language import Language

# Aggregators and context
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMAssistantContextAggregator,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
from pipecat.frames.frames import StartFrame

from transport.twilio import create_twilio_transport
from services.llm.sarvam_llm import SarvamLLMService

from app.config import settings
from app.constants import get_system_prompt


class PipelineBuilder:
    """
    Clean Pipecat pipeline builder (0.0.95 compatible).

    Flow:
    Transport → STT → LLMUserContextAggregator → SarvamLLMService
    → LLMAssistantContextAggregator → TTS → Transport
    """

    def __init__(
        self,
        websocket,
        stream_sid: str,
        language: str,
        system_prompt: Optional[str] = None,
    ):
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.language = language
        self.system_prompt = system_prompt or get_system_prompt(language)

        self._aiohttp_session = None
        self.pipeline_ready = asyncio.Event()

        logger.info(
            f"✨ PipelineBuilder initialized | stream={stream_sid}, language={language}"
        )

    async def build(self) -> tuple[Pipeline, PipelineTask]:
        logger.info("🚀 Building Pipecat pipeline...")

        # Transport
        transport = create_twilio_transport(
            self.websocket,
            self.stream_sid,
            self.language,
        )

        # Language mapping
        language_map = {
            "te-IN": Language.TE_IN,
            "hi-IN": Language.HI_IN,
            "en-IN": Language.EN_IN,
        }
        if self.language not in language_map:
            logger.warning(
                f"⚠️ Unknown language '{self.language}', defaulting to hi-IN"
            )
        language_enum = language_map.get(self.language, Language.HI_IN)

        # STT
        stt_service = SarvamSTTService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.STT_MODEL,
            sample_rate=settings.STT_SAMPLE_RATE,
            params=SarvamSTTService.InputParams(
                language=language_enum,
                vad_signals=True,
                high_vad_sensitivity=False,
            ),
        )

        # Shared context (message container only)
        context = OpenAILLMContext(
            [
                {
                    "role": "system",
                    "content": self.system_prompt,
                }
            ]
        )

        # Aggregator params
        user_params = LLMUserAggregatorParams(
            aggregation_timeout=settings.AGGREGATION_TIMEOUT
        )
        assistant_params = LLMAssistantAggregatorParams(
            expect_stripped_words=True
        )

        # User aggregator → emits OpenAILLMContextFrame
        user_aggregator = LLMUserContextAggregator(
            context=context,
            params=user_params,
        )

        # Custom Sarvam LLM (OpenAILLMContextFrame in → text frames out)
        llm_service = SarvamLLMService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.LLM_MODEL,
            language=self.language,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            knowledge_base_path=settings.KNOWLEDGE_BASE_PATH,
        )

        # Assistant aggregator → handles interruption + TTS routing
        assistant_aggregator = LLMAssistantContextAggregator(
            context=context,
            params=assistant_params,
        )

        # TTS
        tts_service = await self._create_tts_service()

        pipeline = Pipeline(
            [
                transport.input(),
                stt_service,
                user_aggregator,
                llm_service,
                assistant_aggregator,
                tts_service,
                transport.output(),
            ]
        )

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=settings.AUDIO_SAMPLE_RATE_IN,
                audio_out_sample_rate=settings.AUDIO_SAMPLE_RATE_OUT,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )

        logger.info("✅ Pipeline built successfully")
        return pipeline, task

    async def _create_tts_service(self):
        try:
            logger.info("🔊 Using Sarvam WebSocket TTS")
            return SarvamTTSService(
                api_key=settings.SARVAM_API_KEY,
                voice=settings.TTS_VOICE,
                sample_rate=settings.TTS_SAMPLE_RATE,
            )
        except Exception as e:
            logger.warning(f"⚠️ WS TTS failed, falling back to HTTP: {e}")

        self._aiohttp_session = aiohttp.ClientSession()
        return SarvamHttpTTSService(
            api_key=settings.SARVAM_API_KEY,
            voice=settings.TTS_VOICE,
            sample_rate=settings.TTS_SAMPLE_RATE,
            aiohttp_session=self._aiohttp_session,
        )

    async def ensure_pipeline_ready(self):
        self.pipeline_ready.set()
        logger.info("✅ Pipeline ready")

    async def cleanup(self):
        if self._aiohttp_session:
            await self._aiohttp_session.close()
            logger.info("🧹 HTTP TTS session closed")
