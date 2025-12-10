"""Pipeline builder for assembling Pipecat pipelines."""
from typing import Optional
from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.aggregators.llm_response import LLMUserAggregatorParams
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import Frame

from transport.twilio import create_twilio_transport
from services.stt.sarvam_stt import SarvamSTTService
from services.llm.sarvam_llm import SarvamLLMService
from services.tts.sarvam_tts import SarvamTTSService
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
        language: str = "en-IN",
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
        
        # Create STT service
        stt_service = SarvamSTTService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.STT_MODEL,
            language=self.language,
            sample_rate=settings.STT_SAMPLE_RATE
        )
        
        # Create shared context using LLMContext (not OpenAILLMContext)
        messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]
        context = LLMContext(messages)
        
        # Configure user aggregator with timeout from settings
        # CRITICAL: aggregation_timeout is how long to wait after UserStoppedSpeaking
        # before sending accumulated transcriptions to LLM
        user_params = LLMUserAggregatorParams(
            aggregation_timeout=settings.AGGREGATION_TIMEOUT
        )
        
        logger.info(f"🔧 Aggregator config: timeout={settings.AGGREGATION_TIMEOUT}s")
        
        # Create context aggregator pair (replaces deprecated user/assistant aggregators)
        context_aggregator = LLMContextAggregatorPair(
            context,
            user_params=user_params
        )
        
        # Add logging to user aggregator via monkey-patching
        user_aggregator = context_aggregator.user()
        original_process_frame = user_aggregator.process_frame
        original_push_frame = user_aggregator.push_frame
        
        async def logged_process_frame(frame: Frame, direction: FrameDirection):
            frame_type = type(frame).__name__
            
            # Only log critical frames (transcription and user stopped speaking)
            if frame_type == 'TranscriptionFrame':
                logger.info(f"📥 [AGGREGATOR] Received TranscriptionFrame: '{frame.text}'")
            elif frame_type == 'UserStoppedSpeakingFrame':
                logger.info(f"📥 [AGGREGATOR] User stopped speaking - aggregating transcriptions")
            
            # Call original
            result = await original_process_frame(frame, direction)
            
            # Log completion
            if frame_type == 'UserStoppedSpeakingFrame':
                logger.info(f"⏱️ [AGGREGATOR] Will wait {settings.AGGREGATION_TIMEOUT}s before sending to LLM")
            
            return result
        
        async def logged_push_frame(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
            frame_type = type(frame).__name__
            # Only log critical frames
            if frame_type == 'LLMContextFrame':
                logger.info(f"🚀 [AGGREGATOR] ⭐ Sending LLMContextFrame to LLM ({len(frame.context.messages)} messages)")
            elif frame_type in ['UserStartedSpeakingFrame', 'InterruptionFrame']:
                logger.info(f"🚀 [AGGREGATOR] {frame_type}")
            return await original_push_frame(frame, direction)
        
        # Replace methods
        user_aggregator.process_frame = logged_process_frame
        user_aggregator.push_frame = logged_push_frame
        
        logger.info(f"✅ Created LLMContextAggregatorPair with aggregation_timeout={settings.AGGREGATION_TIMEOUT}s")
        logger.info(f"✅ System prompt: {self.system_prompt[:100]}...")
        logger.info(f"✅ Context has {len(context.messages)} initial messages")
        
        # Create LLM service
        llm_service = SarvamLLMService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.LLM_MODEL,
            language=self.language,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            knowledge_base_path=settings.KNOWLEDGE_BASE_PATH
        )
        
        # Create TTS service
        tts_service = SarvamTTSService(
            api_key=settings.SARVAM_API_KEY,
            model=settings.TTS_MODEL,
            voice=settings.TTS_VOICE,
            language=self.language,
            target_sample_rate=settings.TTS_SAMPLE_RATE
        )
        
        # Assemble pipeline (following official Pipecat reference pattern)
        # CRITICAL: assistant aggregator MUST be AFTER transport.output()
        # It captures LLM text frames for context but doesn't block them from TTS
        # Reference: https://github.com/pipecat-ai/pipecat/tree/main/examples
        pipeline = Pipeline([
            transport.input(),           # Receive audio from Twilio
            stt_service,                 # Speech-to-Text
            user_aggregator,             # User context aggregation (with logging)
            llm_service,                 # Generate response
            tts_service,                 # Text-to-Speech (receives LLMTextFrame from LLM)
            transport.output(),          # Send audio to Twilio
            context_aggregator.assistant(),  # Assistant context aggregation (captures LLM text for context)
        ])
        
        logger.info("[CHECKPOINT 2] Creating pipeline task...")
        
        # Create pipeline task with proper audio parameters
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=8000,   # Twilio sends at 8kHz
                audio_out_sample_rate=8000,  # Twilio expects 8kHz
                enable_metrics=True,
                enable_usage_metrics=True,
            )
        )
        
        logger.info("Pipeline built successfully")
        
        return pipeline, task, transport, [stt_service, llm_service, tts_service]
