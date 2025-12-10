"""Main FastAPI application."""
import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.logging_config import app_logger
from app.middleware import MetricsMiddleware, RateLimitMiddleware, get_limiter
from api.routes import voice, health, websocket

try:
    from prometheus_client import make_asgi_app
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Voice AI Bot Application")
    logger.info("=" * 60)
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info(f"Server URL: {settings.SERVER_URL}")
    logger.info(f"Twilio Phone: {settings.TWILIO_PHONE_NUMBER}")
    logger.info(f"STT Model: {settings.STT_MODEL}")
    logger.info(f"LLM Model: {settings.LLM_MODEL}")
    logger.info(f"TTS Model: {settings.TTS_MODEL}")
    logger.info(f"VAD Enabled: {settings.VAD_ENABLED}")
    logger.info(f"Supported Languages: {list(settings.SUPPORTED_LANGUAGES.keys())}")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down Voice AI Bot Application")
    logger.info("=" * 60)


# Create FastAPI app
app = FastAPI(
    title="Voice AI Bot",
    description="Production-ready voice AI bot using Twilio, Pipecat, and Sarvam AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics middleware
app.add_middleware(MetricsMiddleware)

# Rate limiting middleware (from config.yaml)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)

# Include routers
app.include_router(voice.router)
app.include_router(health.router)
app.include_router(websocket.router)

# Prometheus metrics endpoint
if PROMETHEUS_AVAILABLE:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    logger.info("📊 Prometheus metrics available at /metrics")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Voice AI Bot",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"  # Changed from "debug" to hide WebSocket frame logs
    )
