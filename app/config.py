"""Application configuration management."""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from loguru import logger


def load_yaml_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"✅ Loaded configuration from {config_path}")
                return config or {}
        else:
            logger.warning(f"⚠️ Config file not found: {config_path}, using defaults")
            return {}
    except Exception as e:
        logger.error(f"❌ Failed to load config.yaml: {e}")
        return {}


# Load YAML configuration
yaml_config = load_yaml_config()


class Settings(BaseSettings):
    """Application settings loaded from .env (credentials) and config.yaml (settings)."""
    
    # ==========================================
    # CREDENTIALS (from .env)
    # ==========================================
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio Account SID")
    TWILIO_AUTH_TOKEN: str = Field(..., description="Twilio Auth Token")
    TWILIO_PHONE_NUMBER: str = Field(..., description="Twilio Phone Number")
    SERVER_URL: str = Field(..., description="Public server URL for webhooks")
    
    # Sarvam AI Configuration
    SARVAM_API_KEY: str = Field(..., description="Sarvam AI API key")
    SARVAM_API_URL: str = Field(
        default="https://api.sarvam.ai",
        description="Sarvam AI API base URL"
    )
    
    # Redis Configuration (optional - falls back to in-memory)
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis URL for session storage (e.g., redis://localhost:6379/0)"
    )
    
    # ==========================================
    # APPLICATION SETTINGS (from config.yaml)
    # ==========================================
    
    # Server Configuration
    HOST: str = Field(
        default=yaml_config.get("server", {}).get("host", "0.0.0.0"),
        description="Server host"
    )
    PORT: int = Field(
        default=yaml_config.get("server", {}).get("port", 8000),
        description="Server port"
    )
    DEBUG: bool = Field(
        default=yaml_config.get("server", {}).get("debug", False),
        description="Debug mode"
    )
    
    # STT Configuration
    STT_MODEL: str = Field(
        default=yaml_config.get("stt", {}).get("model", "saarika:v2.5"),
        description="STT model"
    )
    STT_SAMPLE_RATE: int = Field(
        default=yaml_config.get("stt", {}).get("sample_rate", 16000),
        description="STT sample rate"
    )
    
    # LLM Configuration
    LLM_MODEL: str = Field(
        default=yaml_config.get("llm", {}).get("model", "sarvam-m"),
        description="LLM model"
    )
    LLM_MAX_TOKENS: int = Field(
        default=yaml_config.get("llm", {}).get("max_tokens", 512),
        description="LLM max tokens"
    )
    LLM_TEMPERATURE: float = Field(
        default=yaml_config.get("llm", {}).get("temperature", 0.7),
        description="LLM temperature"
    )
    LLM_TOP_P: float = Field(
        default=yaml_config.get("llm", {}).get("top_p", 0.85),
        description="LLM top_p sampling"
    )
    LLM_FREQUENCY_PENALTY: float = Field(
        default=yaml_config.get("llm", {}).get("frequency_penalty", 0.3),
        description="LLM frequency penalty"
    )
    LLM_PRESENCE_PENALTY: float = Field(
        default=yaml_config.get("llm", {}).get("presence_penalty", 0.2),
        description="LLM presence penalty"
    )
    
    # TTS Configuration
    TTS_MODEL: str = Field(
        default=yaml_config.get("tts", {}).get("model", "bulbul:v2"),
        description="TTS model"
    )
    TTS_VOICE: str = Field(
        default=yaml_config.get("tts", {}).get("voice", "anushka"),
        description="TTS voice"
    )
    TTS_SAMPLE_RATE: int = Field(
        default=yaml_config.get("tts", {}).get("sample_rate", 8000),
        description="TTS sample rate"
    )
    
    # Audio Configuration
    AUDIO_CHUNK_SIZE: int = Field(
        default=yaml_config.get("audio", {}).get("chunk_size", 160),
        description="Audio chunk size in bytes"
    )
    AUDIO_SAMPLE_RATE_IN: int = Field(
        default=yaml_config.get("audio", {}).get("sample_rate_in", 8000),
        description="Input sample rate"
    )
    AUDIO_SAMPLE_RATE_OUT: int = Field(
        default=yaml_config.get("audio", {}).get("sample_rate_out", 8000),
        description="Output sample rate"
    )
    
    # VAD Configuration
    VAD_ENABLED: bool = Field(
        default=yaml_config.get("vad", {}).get("enabled", True),
        description="Enable VAD"
    )
    VAD_STOP_SECS: float = Field(
        default=yaml_config.get("vad", {}).get("stop_secs", 0.8),
        description="VAD stop seconds"
    )
    VAD_START_SECS: float = Field(
        default=yaml_config.get("vad", {}).get("start_secs", 0.2),
        description="VAD start seconds"
    )
    VAD_MIN_VOLUME: float = Field(
        default=yaml_config.get("vad", {}).get("min_volume", 0.6),
        description="VAD minimum volume"
    )
    VAD_CONFIDENCE: float = Field(
        default=yaml_config.get("vad", {}).get("confidence", 0.7),
        description="VAD confidence threshold"
    )
    
    # Pipeline Configuration
    AGGREGATION_TIMEOUT: float = Field(
        default=yaml_config.get("pipeline", {}).get("aggregation_timeout", 0.8),
        description="Aggregation timeout"
    )
    MAX_SILENCE_DURATION: float = Field(
        default=yaml_config.get("pipeline", {}).get("max_silence_duration", 300.0),
        description="Max silence (5 min)"
    )
    
    # Feature Flags
    SAVE_DEBUG_AUDIO: bool = Field(
        default=yaml_config.get("features", {}).get("save_debug_audio", False),
        description="Save debug audio files"
    )
    DEBUG_AUDIO_DIR: str = Field(
        default=yaml_config.get("features", {}).get("debug_audio_dir", "debug_audio"),
        description="Debug audio directory"
    )
    ENABLE_ANALYTICS: bool = Field(
        default=yaml_config.get("features", {}).get("enable_analytics", True),
        description="Enable analytics"
    )
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=yaml_config.get("rate_limit", {}).get("requests_per_minute", 60),
        description="Rate limit requests per minute"
    )
    
    # Knowledge Base
    KNOWLEDGE_BASE_PATH: str = Field(
        default=yaml_config.get("knowledge", {}).get("base_path", "knowledge/Querie.json"),
        description="Knowledge base file path"
    )
    
    # Supported Languages
    SUPPORTED_LANGUAGES: dict = Field(
        default=yaml_config.get("languages", {
            "1": {"code": "te-IN", "name": "Telugu"},
            "2": {"code": "hi-IN", "name": "Hindi"},
            "3": {"code": "en-IN", "name": "English"}
        }),
        description="Supported languages mapping"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
