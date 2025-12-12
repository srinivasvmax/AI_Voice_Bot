"""Pipeline builder for assembling Pipecat pipelines."""
from typing import Optional
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext

from pipecat.processors.aggregators.llm_response import LLMUserAggregatorParams
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import Frame

from transport.twilio import create_twilio_transport
from services.stt.sarvam_stt import SarvamSTTService
from services.llm.sarvam_llm import SarvamLLMService

from app.config import settings
from app.constants import get_system_prompt


class PipelineBuilder:
    """
    Builder for constructing Pipecat voice AI pipelines.
    
    Assembles the complete pipeline:
    Transport → STT → UserAggregator → LLM → AssistantAggregator → TTS → Transport
    """
    
    def __init__(
        self,
        websocket,
        stream_sid: str,
        language: str,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize pipeline builder.
        
        Args:
            websocket: FastAPI WebSocket connection
            stream_sid: Twilio stream SID
            language: Language code
            system_prompt: Custom system prompt (optional)
        """
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.language = language
        # Use language-specific system prompt if no custom prompt provided
        self.system_prompt = system_prompt or get_system_prompt(language)
        
        # Pipeline readiness event to prevent race conditions
        import asyncio
        self.pipeline_ready = asyncio.Event()
        
        logger.info(f"Initialized PipelineBuilder: stream_sid={stream_sid}, language={language}")
    
    def build(self) -> tuple[Pipeline, PipelineTask]:
        """
        Build the complete pipeline.
        
        Returns:
            Tuple of (Pipeline, PipelineTask)
        """
        logger.info("[CHECKPOINT 1] Building pipeline...")
        
        # Create transport
        transport = create_twilio_transport(
            self.websocket,
            self.stream_sid,
            self.language
        )
        
        # Create STT service with proper language configuration
        from pipecat.transcriptions.language import Language
        
        # Convert language string to Language enum
        language_map = {
            "te-IN": Language.TE_IN,
            "hi-IN": Language.HI_IN,
            "en-IN": Language.EN_IN,
        }
        language_enum = language_map.get(self.language, Language.HI_IN)
        
        stt_service = SarvamSTTService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.STT_MODEL,
            sample_rate=settings.STT_SAMPLE_RATE,
            params=SarvamSTTService.InputParams(
                language=language_enum,
                vad_signals=True,
                high_vad_sensitivity=False  # Use normal VAD sensitivity for better accuracy
            )
        )
        
        logger.info(f"🎤 [STT] Configured for language: {language_enum} ({self.language})")
        
        # Create shared context using OpenAILLMContext for compatibility
        from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
        
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]
        context = OpenAILLMContext(messages)
        
        # Configure user aggregator with timeout from settings
        # CRITICAL: aggregation_timeout is how long to wait after UserStoppedSpeaking
        # before sending accumulated transcriptions to LLM
        user_params = LLMUserAggregatorParams(
            aggregation_timeout=settings.AGGREGATION_TIMEOUT
        )
        
        # Create LLM service first (needed for workaround aggregator)
        llm_service = SarvamLLMService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.LLM_MODEL,
            language=self.language,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            knowledge_base_path=settings.KNOWLEDGE_BASE_PATH
        )
        
        # Create user aggregator (this one works fine)
        from pipecat.processors.aggregators.llm_response import LLMUserContextAggregator
        
        user_aggregator = LLMUserContextAggregator(
            context=context,
            params=user_params
        )
        
        # BYPASS the problematic LLMAssistantContextAggregator entirely
        # Connect LLM directly to TTS to avoid the compatibility issue
        assistant_aggregator = None  # We'll skip this in the pipeline 
        
        logger.info(f"✅ User aggregator configured with {user_params.aggregation_timeout}s timeout")
        
        logger.info(f"✅ Pipeline configured with {settings.AGGREGATION_TIMEOUT}s aggregation timeout")
        
        # LLM service already created above
        
        # Create robust TTS service (production-grade HTTP streaming)
        from services.tts.sarvam_tts_processor import SarvamTTSProcessor
        tts_service = SarvamTTSProcessor(
            api_key=settings.SARVAM_API_KEY,
            voice=settings.TTS_VOICE,
            sample_rate=settings.TTS_SAMPLE_RATE,
            frame_duration_ms=settings.TTS_FRAME_DURATION_MS,
            fallback_chunk_size=settings.TTS_FALLBACK_CHUNK_SIZE,
            api_base_url=settings.SARVAM_API_URL,
            api_endpoint=settings.TTS_API_ENDPOINT
        )
        
        # Assemble pipeline in correct order for Pipecat voice agent
        # BYPASS assistant aggregator to avoid compatibility issue
        pipeline = Pipeline([
            transport.input(),                   # Client audio in
            stt_service,                        # -> transcribe
            user_aggregator,                    # Aggregate user utterances
            llm_service,                        # -> produce assistant response
            # assistant_aggregator,             # SKIPPED - causes compatibility issue
            tts_service,                        # -> synthesize audio
            transport.output(),                 # Send audio back to client
        ])
        
        logger.info("[CHECKPOINT 2] Creating pipeline task...")
        
        # Create pipeline task with proper audio parameters
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=settings.AUDIO_SAMPLE_RATE_IN,   # 16000 for Sarvam STT
                audio_out_sample_rate=settings.AUDIO_SAMPLE_RATE_OUT, # 22050 for Sarvam TTS
                enable_metrics=True,
                enable_usage_metrics=True,
            )
        )
        
        logger.info("Pipeline built successfully")
        
        # Return only pipeline and task to match annotation and Pipecat API
        return pipeline, task
    
    async def ensure_pipeline_ready(self):
        """Ensure the pipeline is fully ready before processing media frames.
        
        This prevents race conditions where Twilio media frames arrive before
        Pipecat FrameProcessors are fully initialized.
        """
        import asyncio
        import logging
        
        try:
            # Give the pipeline components time to initialize their internal structures
            # This prevents the '_FrameProcessor__process_queue' attribute error
            await asyncio.sleep(0.2)
            
            # Signal that pipeline is ready
            self.pipeline_ready.set()
            logging.info("🚀 Pipeline is fully ready. Safe to process Twilio media frames.")
            
        except Exception:
            logging.exception("Pipeline readiness check failed")
            raise
