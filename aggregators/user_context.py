"""User context aggregator with logging."""
from loguru import logger
from pipecat.processors.aggregators.llm_response import LLMUserResponseAggregator
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import Frame, TranscriptionFrame, UserStoppedSpeakingFrame, LLMMessagesFrame


class LoggingUserAggregator(LLMUserResponseAggregator):
    """
    User context aggregator with enhanced logging.
    
    Extends Pipecat's LLMUserResponseAggregator to add logging
    for debugging and monitoring.
    """
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frame with logging."""
        frame_type = type(frame).__name__
        
        # Log BEFORE processing
        if isinstance(frame, TranscriptionFrame):
            logger.info("=" * 80)
            logger.info("📥 [CHECKPOINT 9] AGGREGATOR RECEIVED TRANSCRIPTION!")
            logger.info(f"📥 [AGGREGATOR] Received TranscriptionFrame: '{frame.text}'")
            logger.info(f"📥 [AGGREGATOR] Current aggregation BEFORE: '{self._aggregation}'")
            logger.info(f"📊 [AGGREGATOR] Context has {len(self._context.messages)} messages")
            
        elif isinstance(frame, LLMMessagesFrame):
            logger.info("=" * 80)
            logger.info("📤 [CHECKPOINT 10] AGGREGATOR PUSHING TO LLM!")
            logger.info(f"📤 [AGGREGATOR] Pushing LLMMessagesFrame with {len(frame.context.messages)} messages")
            logger.info(f"📝 [AGGREGATOR] Conversation history:")
            logger.info("=" * 80)
            for i, msg in enumerate(frame.context.messages):
                logger.info(f"  [{i}] {msg.get('role')}: {msg.get('content', '')[:100]}")
                
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info("=" * 80)
            logger.info(f"📥 [AGGREGATOR] Received UserStoppedSpeakingFrame")
            logger.info(f"📥 [AGGREGATOR] Current aggregation: '{self._aggregation}'")
            logger.info(f"📥 [AGGREGATOR] User speaking: {getattr(self, '_user_speaking', 'N/A')}")
            logger.info("=" * 80)
        
        # Process the frame
        result = await super().process_frame(frame, direction)
        
        # Log AFTER processing to see what changed
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"✅ [AGGREGATOR] After TranscriptionFrame - aggregation: '{self._aggregation}'")
            logger.info("=" * 80)
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info(f"✅ [AGGREGATOR] After UserStoppedSpeakingFrame - aggregation: '{self._aggregation}'")
            logger.info("=" * 80)
        
        return result
    
    async def push_aggregation(self):
        """Override to add logging when aggregation is pushed."""
        logger.info("=" * 80)
        logger.info("📤 [CHECKPOINT 10] AGGREGATOR PUSHING TO LLM!")
        logger.info(f"📤 [AGGREGATOR] Pushing aggregation: '{self._aggregation}'")
        
        # Get message count safely
        try:
            msg_count = len(self._context.messages) if hasattr(self._context, 'messages') else 0
            logger.info(f"📤 [AGGREGATOR] Context has {msg_count} messages before push")
        except:
            logger.info(f"📤 [AGGREGATOR] Context messages not accessible")
        
        logger.info("=" * 80)
        
        # Call parent's push_aggregation
        await super().push_aggregation()
        
        try:
            msg_count = len(self._context.messages) if hasattr(self._context, 'messages') else 0
            logger.info(f"✅ [AGGREGATOR] Aggregation pushed! Context now has {msg_count} messages")
        except:
            logger.info(f"✅ [AGGREGATOR] Aggregation pushed!")
