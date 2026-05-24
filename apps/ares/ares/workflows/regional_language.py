"""Local phrasebook translation helpers for Ares regional-language flows."""

from __future__ import annotations

PHRASES = {
    "payment_reminder": {
        "tamil": "உங்கள் பாக்கி தொகை நிலுவையில் உள்ளது.",
        "gujarati": "તમારી ઉધાર રકમ બાકી છે.",
        "marathi": "तुमची उधारी रक्कम बाकी आहे.",
        "kannada": "ನಿಮ್ಮ ಬಾಕಿ ಮೊತ್ತ ಪಾವತಿಸಬೇಕಿದೆ.",
        "english_hinglish": "Aapka outstanding pending hai.",
    },
    "order_confirmation": {
        "marathi": "तुमचा ऑर्डर कन्फर्म झाला आहे.",
        "tamil": "உங்கள் ஆர்டர் உறுதி செய்யப்பட்டது.",
        "gujarati": "તમારો ઓર્ડર કન્ફર્મ થયો છે.",
        "kannada": "ನಿಮ್ಮ ಆರ್ಡರ್ ದೃಢೀಕರಿಸಲಾಗಿದೆ.",
        "english_hinglish": "Aapka order confirm ho gaya hai.",
    },
    "stock_alert": {
        "kannada": "ಸ್ಟಾಕ್ ಕಡಿಮೆ ಇದೆ.",
        "tamil": "ஸ்டாக் குறைவாக உள்ளது.",
        "gujarati": "સ્ટોક ઓછો છે.",
        "marathi": "स्टॉक कमी आहे.",
        "english_hinglish": "Stock low hai.",
    },
}

VOCABULARY = {
    "hindi": {"order": "order", "invoice": "bill", "outstanding": "baki"},
    "english_hinglish": {"order": "order", "invoice": "bill", "outstanding": "baki"},
}


def _normalise_language(language: str | None) -> str:
    value = (language or "english_hinglish").strip().lower().replace("-", "_")
    if value in {"hindi", "hinglish", "english"}:
        return "english_hinglish"
    return value


def detect_language(text: str) -> str:
    if any("\u0b80" <= ch <= "\u0bff" for ch in text):
        return "tamil"
    if any("\u0a80" <= ch <= "\u0aff" for ch in text):
        return "gujarati"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "marathi"
    if any("\u0c80" <= ch <= "\u0cff" for ch in text):
        return "kannada"
    return "english_hinglish"


def translate_to_regional(
    *,
    text: str,
    target_language: str,
    phrase_key: str | None = None,
) -> dict:
    language = _normalise_language(target_language)
    phrase = PHRASES.get(phrase_key or "", {}).get(language)
    if phrase:
        return {
            "mode": "local_phrasebook",
            "translation_method": "phrasebook_lookup",
            "target_language": language,
            "translated_text": phrase,
            "audit": {"translation_provider_called": False},
        }

    translated = text
    for english, local in VOCABULARY.get(language, {}).items():
        translated = translated.replace(english, local)
    return {
        "mode": "local_vocabulary",
        "translation_method": "vocabulary_substitution",
        "target_language": language,
        "translated_text": translated,
        "audit": {"translation_provider_called": False},
    }


def translate_from_regional(*, text: str, source_language: str | None = None) -> dict:
    detected = _normalise_language(source_language) if source_language else detect_language(text)
    if detected == "english_hinglish":
        return {
            "mode": "local_passthrough",
            "detected_language": detected,
            "normalised_text": text,
            "audit": {"translation_provider_called": False},
        }
    replacements = {
        "ஆர்டர்": "order",
        "பில்": "invoice",
        "ಉಧಾರಿ": "outstanding",
        "ઓર્ડર": "order",
        "ऑर्डर": "order",
    }
    normalised = text
    for source, target in replacements.items():
        normalised = normalised.replace(source, target)
    return {
        "mode": "local_vocabulary_reverse",
        "detected_language": detected,
        "normalised_text": normalised,
        "audit": {"translation_provider_called": False},
    }
