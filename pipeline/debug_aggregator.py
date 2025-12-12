"""Debug wrapper for user aggregator to trace transcription flow."""
from loguru import logger
from pipecat.processors.aggregators.llm_response import LLMUserContextAggregator
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import Frame, TranscriptionFrame, LLMMessagesFrame


class DebugUserContextAggregator(LLMUserContextAggregator):
    """Debug wrapper for LLMUserContextAggregator to trace frame flow."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("🔍 [DEBUG] DebugUserContextAggregator initialized")
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames with detailed logging."""
        # Only log important frames, not audio frames
        if not type(frame).__name__.endswith('AudioRawFrame'):
            logger.info(f"🔍 [USER_AGG] Received frame: {type(frame).__name__} (direction: {direction})")
        
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"🔍 [USER_AGG] TranscriptionFrame: text='{frame.text}', user_id={frame.user_id}")
        
        # Call parent implementation
        await super().process_frame(frame, direction)
        
        # Log if we're about to send LLMMessagesFrame
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"🔍 [USER_AGG] After processing TranscriptionFrame, context has {len(self._context.messages)} messages")
    
    async def push_frame(self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        """Push frames with detailed logging."""
        # Only log important frames, not audio frames
        if not type(frame).__name__.endswith('AudioRawFrame'):
            logger.info(f"🔍 [USER_AGG] Pushing frame: {type(frame).__name__} (direction: {direction})")
        
        if isinstance(frame, LLMMessagesFrame):
            logger.info(f"🔍 [USER_AGG] Pushing LLMMessagesFrame with {len(frame.messages)} messages!")
            for i, msg in enumerate(frame.messages):
                logger.info(f"🔍 [USER_AGG] Message {i}: role={msg.get('role')}, content='{msg.get('content', '')[:100]}...'")
        
        await super().push_frame(frame, direction)