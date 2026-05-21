"""Local regional-language operations contract."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_REGIONAL_LANGUAGE_LIMITATION = (
    "Local regional-language operations contract only; no translation provider, WhatsApp Business API, or voice stack was called."
)

SUPPORTED_LANGUAGES = [
    "english_hinglish",
    "tamil",
    "telugu",
    "kannada",
    "marathi",
    "gujarati",
    "bengali",
    "punjabi",
]

SCRIPT_RANGES = {
    "tamil": re.compile(r"[\u0b80-\u0bff]"),
    "telugu": re.compile(r"[\u0c00-\u0c7f]"),
    "kannada": re.compile(r"[\u0c80-\u0cff]"),
    "gujarati": re.compile(r"[\u0a80-\u0aff]"),
    "bengali": re.compile(r"[\u0980-\u09ff]"),
    "punjabi": re.compile(r"[\u0a00-\u0a7f]"),
    "marathi": re.compile(r"[\u0900-\u097f]"),
}

ROMANIZED_KEYWORDS = {
    "english_hinglish": {"bhai", "bhejna", "udhaar", "jama", "maal", "kal", "aaj"},
    "tamil": {"vanakkam", "anuppu", "kadai", "bill", "panam"},
    "telugu": {"namaskaram", "pampandi", "dukanam", "dabbu"},
    "kannada": {"namaskara", "kalisi", "angadi", "hana"},
    "marathi": {"namaskar", "pathva", "dukan", "udhari", "kiti"},
    "gujarati": {"kem", "moklo", "dukan", "udhar", "jama"},
    "bengali": {"nomoskar", "pathan", "dokaan", "baki"},
    "punjabi": {"sat", "bhejo", "dukan", "udhaar"},
}

BUSINESS_VOCABULARY = {
    "english_hinglish": {"order": "order", "invoice": "bill", "outstanding": "udhaar", "stock": "stock"},
    "tamil": {"order": "ஆர்டர்", "invoice": "பில்", "outstanding": "பாக்கி", "stock": "ஸ்டாக்"},
    "telugu": {"order": "ఆర్డర్", "invoice": "బిల్", "outstanding": "బాకీ", "stock": "స్టాక్"},
    "kannada": {"order": "ಆರ್ಡರ್", "invoice": "ಬಿಲ್", "outstanding": "ಬಾಕಿ", "stock": "ಸ್ಟಾಕ್"},
    "marathi": {"order": "ऑर्डर", "invoice": "बिल", "outstanding": "उधारी", "stock": "स्टॉक"},
    "gujarati": {"order": "ઓર્ડર", "invoice": "બિલ", "outstanding": "ઉધાર", "stock": "સ્ટોક"},
    "bengali": {"order": "অর্ডার", "invoice": "বিল", "outstanding": "বাকি", "stock": "স্টক"},
    "punjabi": {"order": "ਆਰਡਰ", "invoice": "ਬਿੱਲ", "outstanding": "ਉਧਾਰ", "stock": "ਸਟਾਕ"},
}

DOCUMENT_LABELS = {
    "english_hinglish": {"invoice": "Bill", "statement": "Ledger statement", "due_amount": "Udhaar amount"},
    "tamil": {"invoice": "பில்", "statement": "கணக்கு அறிக்கை", "due_amount": "பாக்கி தொகை"},
    "telugu": {"invoice": "బిల్", "statement": "ఖాతా స్టేట్మెంట్", "due_amount": "బాకీ మొత్తం"},
    "kannada": {"invoice": "ಬಿಲ್", "statement": "ಖಾತೆ ವಿವರ", "due_amount": "ಬಾಕಿ ಮೊತ್ತ"},
    "marathi": {"invoice": "बिल", "statement": "खाते विवरण", "due_amount": "उधारी रक्कम"},
    "gujarati": {"invoice": "બિલ", "statement": "ખાતા સ્ટેટમેન્ટ", "due_amount": "ઉધાર રકમ"},
    "bengali": {"invoice": "বিল", "statement": "খাতা বিবরণ", "due_amount": "বাকি টাকা"},
    "punjabi": {"invoice": "ਬਿੱਲ", "statement": "ਖਾਤਾ ਵੇਰਵਾ", "due_amount": "ਉਧਾਰ ਰਕਮ"},
}

SAMPLE_MESSAGES = {
    "english_hinglish": {
        "payment_reminder": "Namaste ji, aapka udhaar amount pending hai.",
        "order_confirmation": "Order mil gaya hai, dispatch se pehle confirm kar rahe hain.",
    },
    "tamil": {
        "payment_reminder": "வணக்கம், உங்கள் பாக்கி தொகை நிலுவையில் உள்ளது.",
        "order_confirmation": "உங்கள் ஆர்டர் கிடைத்தது; அனுப்புவதற்கு முன் உறுதி செய்கிறோம்.",
    },
    "telugu": {
        "payment_reminder": "నమస్కారం, మీ బాకీ మొత్తం పెండింగ్ లో ఉంది.",
        "order_confirmation": "మీ ఆర్డర్ వచ్చింది; పంపే ముందు నిర్ధారిస్తున్నాము.",
    },
    "kannada": {
        "payment_reminder": "ನಮಸ್ಕಾರ, ನಿಮ್ಮ ಬಾಕಿ ಮೊತ್ತ ಬಾಕಿಯಿದೆ.",
        "order_confirmation": "ನಿಮ್ಮ ಆರ್ಡರ್ ಬಂದಿದೆ; ಕಳುಹಿಸುವ ಮೊದಲು ದೃಢಪಡಿಸುತ್ತಿದ್ದೇವೆ.",
    },
    "marathi": {
        "payment_reminder": "नमस्कार, तुमची उधारी रक्कम बाकी आहे.",
        "order_confirmation": "तुमची ऑर्डर मिळाली; पाठवण्याआधी खात्री करत आहोत.",
    },
    "gujarati": {
        "payment_reminder": "નમસ્તે, તમારી ઉધાર રકમ બાકી છે.",
        "order_confirmation": "તમારો ઓર્ડર મળ્યો છે; મોકલતા પહેલા ખાતરી કરીએ છીએ.",
    },
    "bengali": {
        "payment_reminder": "নমস্কার, আপনার বাকি টাকা এখনও বাকি আছে.",
        "order_confirmation": "আপনার অর্ডার পাওয়া গেছে; পাঠানোর আগে নিশ্চিত করছি.",
    },
    "punjabi": {
        "payment_reminder": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਹਾਡੀ ਉਧਾਰ ਰਕਮ ਬਾਕੀ ਹੈ.",
        "order_confirmation": "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਹੈ; ਭੇਜਣ ਤੋਂ ਪਹਿਲਾਂ ਪੁਸ਼ਟੀ ਕਰ ਰਹੇ ਹਾਂ.",
    },
}


def detect_language(text: str) -> dict[str, Any]:
    """Detect a supported operations language using local script and keyword rules."""
    if not text.strip():
        return {"language": "english_hinglish", "confidence": 0.35, "method": "fallback"}
    for language, pattern in SCRIPT_RANGES.items():
        if pattern.search(text):
            return {"language": language, "confidence": 0.92, "method": "unicode_script"}

    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    keyword_hits = {
        language: len(tokens & keywords)
        for language, keywords in ROMANIZED_KEYWORDS.items()
    }
    best_language, hit_count = max(keyword_hits.items(), key=lambda item: item[1])
    if hit_count:
        return {"language": best_language, "confidence": 0.72, "method": "romanized_keyword"}
    return {"language": "english_hinglish", "confidence": 0.45, "method": "fallback"}


def _customer_by_id(repository: BusinessRepository, customer_id: str | None) -> Customer | None:
    if not customer_id:
        return None
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    return None


def _normalize_language(language: str | None) -> str | None:
    normalized = (language or "").strip().lower().replace("-", "_")
    if normalized in {"hinglish", "hindi", "english"}:
        return "english_hinglish"
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return None


def prepare_regional_language_packet(
    *,
    repository: BusinessRepository,
    customer_id: str | None,
    incoming_text: str,
    document_type: str,
) -> dict[str, Any]:
    """Prepare local language metadata and business labels for owner-approved communication."""
    detection = detect_language(incoming_text)
    customer = _customer_by_id(repository, customer_id)
    customer_language = _normalize_language(customer.preferred_language if customer else None)
    detected_language = _normalize_language(str(detection["language"])) or "english_hinglish"
    selected_language = customer_language or detected_language
    labels = DOCUMENT_LABELS[selected_language]
    vocabulary = BUSINESS_VOCABULARY[selected_language]
    return {
        "mode": "local_contract_mock",
        "supported_languages": SUPPORTED_LANGUAGES,
        "detected_language": detected_language,
        "selected_language": selected_language,
        "detection": detection,
        "document_type": document_type,
        "document_labels": labels,
        "business_vocabulary": vocabulary,
        "sample_messages": SAMPLE_MESSAGES[selected_language],
        "audit": {
            "translation_provider_called": False,
            "whatsapp_business_api_called": False,
            "voice_transcription_performed": False,
            "limitation": LOCAL_REGIONAL_LANGUAGE_LIMITATION,
        },
    }


def build_language_operations_matrix(*, repository: BusinessRepository) -> dict[str, Any]:
    """Summarize customer language readiness using local profile preferences."""
    counts: Counter[str] = Counter()
    fallback_customers: list[dict[str, str]] = []
    for customer in repository.get_customers():
        normalized = _normalize_language(customer.preferred_language)
        if normalized is None:
            counts["english_hinglish"] += 1
            fallback_customers.append(
                {
                    "customer_id": customer.id,
                    "preferred_language": customer.preferred_language,
                    "fallback_language": "english_hinglish",
                    "code": "unsupported_language_preference",
                }
            )
            continue
        counts[normalized] += 1

    language_counts = {language: counts.get(language, 0) for language in SUPPORTED_LANGUAGES}
    return {
        "mode": "local_contract_mock",
        "supported_languages": SUPPORTED_LANGUAGES,
        "language_counts": language_counts,
        "fallback_customers": fallback_customers,
        "summary": {
            "supported_languages": len(SUPPORTED_LANGUAGES),
            "customers_with_supported_language": sum(language_counts.values()) - len(fallback_customers),
            "customers_using_fallback": len(fallback_customers),
        },
        "audit": {
            "translation_provider_called": False,
            "whatsapp_business_api_called": False,
            "voice_transcription_performed": False,
            "limitation": LOCAL_REGIONAL_LANGUAGE_LIMITATION,
        },
    }
