"""Voice call handling routes (Twilio webhooks)."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from loguru import logger
from twilio.twiml.voice_response import VoiceResponse, Gather

from app.config import settings
from models.language import get_language_by_digit
from models.call_session import CallSession, CallState
from api.dependencies import store_session

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/incoming")
async def handle_incoming_call(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...)
):
    """
    Handle incoming call - play language selection menu.
    
    This is the initial Twilio webhook when a call comes in.
    """
    logger.info(f"Incoming call: CallSid={CallSid}, From={From}, To={To}")
    
    # Create session
    session = CallSession(
        call_sid=CallSid,
        state=CallState.LANGUAGE_SELECTION,
        metadata={"from": From, "to": To}
    )
    await store_session(session)
    
    # Build TwiML response
    response = VoiceResponse()
    
    # Language selection menu
    gather = Gather(
        num_digits=1,
        action=f"{settings.SERVER_URL}/voice/language-selected",
        method="POST",
        timeout=10
    )
    
    # Multi-language prompt - separate say tags for each language
    gather.say("Welcome to Electrical Department Customer Support.", voice="Polly.Aditi", language="en-IN")
    gather.pause(length=1)
    gather.say("Telugu kosam okati nokkandi.", voice="Polly.Aditi", language="en-IN")
    gather.say("हिंदी के लिए 2 दबाएं.", voice="Polly.Aditi", language="hi-IN")
    gather.say("Press 3 for English.", voice="Polly.Aditi", language="en-IN")
    
    response.append(gather)
    
    # Fallback if no input - repeat language selection
    response.say("No input received. Please select your language.", voice="Polly.Aditi", language="en-IN")
    response.say("कृपया अपनी भाषा चुनें।", voice="Polly.Aditi", language="hi-IN")
    response.say("దయచేసి మీ భాషను ఎంచుకోండి।", voice="Polly.Aditi", language="te-IN")
    response.redirect(f"{settings.SERVER_URL}/voice/incoming")
    
    logger.info(f"Sent language selection menu for call {CallSid}")
    
    return Response(content=str(response), media_type="application/xml")


@router.post("/language-selected")
async def handle_language_selection(
    request: Request,
    CallSid: str = Form(...),
    Digits: str = Form(...)
):
    """
    Handle language selection - confirm and connect to WebSocket.
    
    This webhook is called after user presses a digit.
    """
    logger.info(f"Language selected: CallSid={CallSid}, Digits={Digits}")
    
    # Get language
    language = get_language_by_digit(Digits)
    
    logger.info(f"🌐 User selected language: {language.name} ({language.code})")
    
    # Build TwiML response
    response = VoiceResponse()
    
    # Connect immediately without greeting - bot will greet via WebSocket
    
    # Build WebSocket URL
    # CRITICAL: Use full URL for WebSocket - works with ngrok and other proxies
    base_url = settings.SERVER_URL
    
    # Convert http:// to wss:// for WebSocket
    ws_url = base_url.replace("http://", "wss://").replace("https://", "wss://")
    if not ws_url.startswith("wss://"):
        ws_url = f"wss://{ws_url}"
    
    # Build WebSocket URL - pass language as query parameter
    # CRITICAL: Use language.code.value to get the actual string value (e.g., "en-IN")
    lang_code = language.code.value if hasattr(language.code, 'value') else str(language.code)
    # Don't use {{StreamSid}} template - Twilio rejects it as invalid URL
    stream_url = f'{ws_url}/media-stream?language={lang_code}'
    
    logger.info(f"🔗 WebSocket URL: {stream_url}")
    logger.info(f"🔗 Request URL: {request.url}")
    logger.info(f"🔗 Call SID: {CallSid}")
    
    # Connect to WebSocket for conversation
    # Per Twilio Media Streams docs: https://www.twilio.com/docs/voice/twiml/stream
    # CRITICAL: Twilio strips query params from WebSocket URLs
    # Solution: Pass language in the URL path instead
    connect = response.connect()
    connect.stream(url=f'{ws_url}/media-stream/{lang_code}')
    
    logger.info(f"✅ TwiML Connect tag created with stream URL")
    
    # Log the TwiML response for debugging
    twiml_xml = str(response)
    logger.info(f"📋 TwiML Response:\n{twiml_xml}")
    logger.info(f"🔗 Final WebSocket URL in TwiML: {ws_url}/media-stream/{lang_code}")
    
    logger.info(f"Connecting call {CallSid} to WebSocket with language {language.code}")
    
    return Response(content=twiml_xml, media_type="application/xml")


@router.post("/outbound")
async def handle_outbound_call(
    request: Request,
    CallSid: str = Form(...),
    To: str = Form(...),
    language: str = Form(...)
):
    """
    Handle outbound call - directly connect to WebSocket.
    
    For outbound calls, skip language selection.
    """
    logger.info(f"Outbound call: CallSid={CallSid}, To={To}, Language={language}")
    
    # Create session
    session = CallSession(
        call_sid=CallSid,
        language=language,
        state=CallState.ACTIVE,
        metadata={"to": To, "direction": "outbound"}
    )
    await store_session(session)
    
    # Build TwiML response
    response = VoiceResponse()
    
    # Connect directly to WebSocket
    connect = response.connect()
    connect.stream(
        url=f"wss://{settings.SERVER_URL.replace('https://', '').replace('http://', '')}/media-stream?language={language}&call_sid={CallSid}"
    )
    
    logger.info(f"Connected outbound call {CallSid} to WebSocket")
    
    return Response(content=str(response), media_type="application/xml")
