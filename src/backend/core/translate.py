import os
import logging
from functools import lru_cache
from typing import Optional, Tuple

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


def _norm_lang(code: Optional[str]) -> str:
    if not code:
        return "en"
    code = code.strip().lower()
    if code in {"auto", "und", "unknown"}:
        return "auto"
    # Normalize common formats like en-US -> en
    if "-" in code:
        code = code.split("-", 1)[0]
    return code or "en"


@lru_cache(maxsize=1)
def _translation_enabled() -> bool:
    # Enabled by default for your requirement; can be disabled if needed.
    return os.getenv("ENABLE_TRANSLATION", "1") == "1"


def detect_language(text: str) -> str:
    """
    Lightweight language detection.
    Uses `langdetect` when available; otherwise falls back to 'auto'.
    """
    if not text or not text.strip():
        return "en"

    try:
        from langdetect import detect  # type: ignore

        lang = detect(text)
        return _norm_lang(lang)
    except Exception:
        return "auto"


@lru_cache(maxsize=2048)
def _translate_cached(text: str, source: str, target: str) -> str:
    translator = GoogleTranslator(source=source, target=target)
    return translator.translate(text)


def translate(text: str, source: str, target: str) -> str:
    """
    Translate text using GoogleTranslator with caching and safe fallbacks.
    Returns original text on failure.
    """
    if not _translation_enabled():
        return text

    source = _norm_lang(source)
    target = _norm_lang(target)

    if not text or not text.strip():
        return text
    if target == "auto":
        return text
    if source != "auto" and source == target:
        return text

    try:
        return _translate_cached(text, source, target)
    except Exception as e:
        logger.warning(f"Translation failed ({source}->{target}); returning original text: {e}")
        return text


def to_english(user_text: str, user_lang_hint: str = "auto") -> Tuple[str, str]:
    """
    Returns (english_text, detected_user_lang).
    If language is English (detected or hinted), returns original.
    """
    if not _translation_enabled():
        return user_text, _norm_lang(user_lang_hint) if user_lang_hint else "en"

    hint = _norm_lang(user_lang_hint)
    
    # If hint is auto, we try to be smart.
    # langdetect is notoriously bad for Roman Urdu or short Spanish.
    # If the text is short (< 30 chars) and hint is auto, we favor 'auto' for GoogleTranslate
    # which is often more robust than a local detector.
    detected = hint
    if hint == "auto":
        detected = detect_language(user_text)
        # If detected as English but very short, it might be a false positive (e.g. 'hi' or Roman Urdu)
        if detected == "en" and len(user_text) < 25:
            # Check for non-English looking words commonly found in Roman Urdu
            roman_urdu_hints = {"kia", "kya", "hal", "hai", "mera", "hai", "shukria", "theek", "acha"}
            words = set(user_text.lower().split())
            if words.intersection(roman_urdu_hints):
                detected = "auto" # Force auto-detect for translation
            elif len(user_text) < 10:
                # Very short strings should just go through auto-translation if not obviously English
                detected = "auto"

    # If hint is provided (e.g. 'ur' from UI) but the text looks like standard English,
    # we should skip translating TO english to avoid mangling it.
    if hint != "auto" and hint != "en":
        # Simple heuristic: if it's mostly common English words, it's English
        common_eng = {"how", "are", "you", "what", "is", "the", "this", "that", "order", "can", "help"}
        if any(w in common_eng for w in user_text.lower().split()):
            return user_text, hint

    if detected == "en" and hint == "auto":
        return user_text, "en"

    # If we know the language is NOT English, or we are in 'auto' mode
    english = translate(user_text, source=detected, target="en")
    
    # If translation didn't change anything, it might already be English
    if english.lower().strip() == user_text.lower().strip() and detected == "auto":
        return user_text, "en"

    return english, (detected if detected != "auto" else "auto")


def from_english(english_text: str, target_lang: str) -> str:
    """
    Translate bot output back to the user's language (if not English).
    """
    target = _norm_lang(target_lang)
    if not _translation_enabled() or target in {"en", "auto"}:
        return english_text
    return translate(english_text, source="en", target=target)

