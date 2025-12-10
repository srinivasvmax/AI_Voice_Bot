"""Middleware for rate limiting and monitoring."""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import time
from collections import defaultdict
from datetime import datetime, timedelta

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("slowapi not available - rate limiting disabled")

try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available - metrics disabled")


# Rate Limiter
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None


# Prometheus Metrics
if PROMETHEUS_AVAILABLE:
    # Request metrics
    http_requests_total = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
    
    http_request_duration_seconds = Histogram(
        'http_request_duration_seconds',
        'HTTP request duration in seconds',
        ['method', 'endpoint']
    )
    
    # Call metrics
    active_calls = Gauge(
        'active_calls_total',
        'Number of active voice calls'
    )
    
    calls_total = Counter(
        'calls_total',
        'Total voice calls',
        ['language', 'status']
    )
    
    # Service metrics
    stt_requests_total = Counter(
        'stt_requests_total',
        'Total STT requests',
        ['status']
    )
    
    llm_requests_total = Counter(
        'llm_requests_total',
        'Total LLM requests',
        ['status']
    )
    
    tts_requests_total = Counter(
        'tts_requests_total',
        'Total TTS requests',
        ['status']
    )
    
    # Latency metrics
    stt_latency_seconds = Histogram(
        'stt_latency_seconds',
        'STT processing latency in seconds'
    )
    
    llm_latency_seconds = Histogram(
        'llm_latency_seconds',
        'LLM processing latency in seconds'
    )
    
    tts_latency_seconds = Histogram(
        'tts_latency_seconds',
        'TTS processing latency in seconds'
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)
        
        # Start timer
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        method = request.method
        endpoint = request.url.path
        status = response.status_code
        
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        return response


class SimpleRateLimiter:
    """Simple in-memory rate limiter fallback."""
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per IP
        """
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > cutoff
        ]
        
        # Check limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False
        
        # Add current request
        self.requests[client_ip].append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting."""
    
    def __init__(self, app, requests_per_minute: int = 60):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per IP
        """
        super().__init__(app)
        self.limiter = SimpleRateLimiter(requests_per_minute)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if not self.limiter.is_allowed(client_ip):
            logger.warning(f"⚠️ Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later."
                }
            )
        
        return await call_next(request)


def get_limiter():
    """Get rate limiter instance."""
    return limiter


def track_call_started(language: str):
    """Track call started metric."""
    if PROMETHEUS_AVAILABLE:
        active_calls.inc()
        calls_total.labels(language=language, status="started").inc()


def track_call_ended(language: str, status: str):
    """Track call ended metric."""
    if PROMETHEUS_AVAILABLE:
        active_calls.dec()
        calls_total.labels(language=language, status=status).inc()


def track_stt_request(success: bool, latency: float):
    """Track STT request metric."""
    if PROMETHEUS_AVAILABLE:
        status = "success" if success else "failure"
        stt_requests_total.labels(status=status).inc()
        stt_latency_seconds.observe(latency)


def track_llm_request(success: bool, latency: float):
    """Track LLM request metric."""
    if PROMETHEUS_AVAILABLE:
        status = "success" if success else "failure"
        llm_requests_total.labels(status=status).inc()
        llm_latency_seconds.observe(latency)


def track_tts_request(success: bool, latency: float):
    """Track TTS request metric."""
    if PROMETHEUS_AVAILABLE:
        status = "success" if success else "failure"
        tts_requests_total.labels(status=status).inc()
        tts_latency_seconds.observe(latency)
