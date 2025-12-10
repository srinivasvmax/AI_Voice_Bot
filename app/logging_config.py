"""Logging configuration using loguru with separate log files per module."""
import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logging():
    """Configure loguru logging with module-specific files and high-level console output."""
    
    # Remove default handler
    logger.remove()
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Console handler - High level logs only (INFO and above)
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",  # Only INFO and above in terminal
        colorize=True,
        filter=lambda record: record["level"].no >= 20  # INFO=20
    )
    
    # Detailed format for file logs
    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    
    # Main application log - All levels (overwrite on each run)
    logger.add(
        log_dir / "app.log",
        format=file_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        mode="w",  # Overwrite mode
        enqueue=True
    )
    
    # STT service log (overwrite on each run)
    logger.add(
        log_dir / "stt.log",
        format=file_format,
        level="DEBUG",
        mode="w",  # Overwrite mode
        filter=lambda record: "stt" in record["name"].lower() or "[STT]" in record["message"],
        enqueue=True
    )
    
    # LLM service log (overwrite on each run)
    logger.add(
        log_dir / "llm.log",
        format=file_format,
        level="DEBUG",
        mode="w",  # Overwrite mode
        filter=lambda record: "llm" in record["name"].lower() or "[LLM]" in record["message"],
        enqueue=True
    )
    
    # TTS service log (overwrite on each run)
    logger.add(
        log_dir / "tts.log",
        format=file_format,
        level="DEBUG",
        mode="w",  # Overwrite mode
        filter=lambda record: "tts" in record["name"].lower() or "[TTS]" in record["message"],
        enqueue=True
    )
    
    # Pipeline log (overwrite on each run)
    logger.add(
        log_dir / "pipeline.log",
        format=file_format,
        level="DEBUG",
        mode="w",  # Overwrite mode
        filter=lambda record: "pipeline" in record["name"].lower() or "CHECKPOINT" in record["message"],
        enqueue=True
    )
    
    # API/WebSocket log (overwrite on each run)
    logger.add(
        log_dir / "api.log",
        format=file_format,
        level="DEBUG",
        mode="w",  # Overwrite mode
        filter=lambda record: "api" in record["name"].lower() or "websocket" in record["name"].lower(),
        enqueue=True
    )
    
    # Error log - Only errors and critical (overwrite on each run)
    logger.add(
        log_dir / "errors.log",
        format=file_format,
        level="ERROR",
        mode="w",  # Overwrite mode
        backtrace=True,
        diagnose=True,
        enqueue=True
    )
    
    logger.info("Logging configured successfully")
    logger.info(f"Log files location: {log_dir.absolute()}")
    return logger


# Initialize logging
app_logger = setup_logging()
