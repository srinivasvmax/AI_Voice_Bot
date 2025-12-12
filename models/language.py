"""Language models and enums."""
from enum import Enum
from typing import Dict
from pydantic import BaseModel


class LanguageCode(str, Enum):
    """Supported language codes."""
    TELUGU = "te-IN"
    HINDI = "hi-IN"
    ENGLISH = "en-IN"


class Language(BaseModel):
    """Language configuration."""
    code: LanguageCode
    name: str
    digit: str  # DTMF digit for selection
    
    class Config:
        frozen = True


# Language mappings
LANGUAGE_MAP: Dict[str, Language] = {
    "1": Language(code=LanguageCode.TELUGU, name="Telugu", digit="1"),
    "2": Language(code=LanguageCode.HINDI, name="Hindi", digit="2"),
    "3": Language(code=LanguageCode.ENGLISH, name="English", digit="3"),
}


def get_language_by_digit(digit: str) -> Language:
    """Get language configuration by DTMF digit."""
    if digit not in LANGUAGE_MAP:
        raise ValueError(f"Invalid language digit: {digit}. Must be 1, 2, or 3.")
    return LANGUAGE_MAP[digit]
