from __future__ import annotations

from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.regional_language import (
    build_language_operations_matrix,
    prepare_regional_language_packet,
)


def test_should_detect_inbound_language_and_prepare_selected_language_packet() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_tn", name="Ramesh Stores", preferred_language="tamil"),
        ],
    )
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Ramesh Stores",
        message_text="ரமேஷ் கடைக்கு 5 carton Surf அனுப்பு",
        chat_hint="cust_tn",
    )

    packet = prepare_regional_language_packet(
        repository=repo,
        customer_id="cust_tn",
        incoming_text=event.raw_text,
        document_type="invoice",
    )

    assert event.metadata["detected_language"] == "tamil"
    assert packet["mode"] == "local_contract_mock"
    assert packet["supported_languages"] == [
        "english_hinglish",
        "tamil",
        "telugu",
        "kannada",
        "marathi",
        "gujarati",
        "bengali",
        "punjabi",
    ]
    assert packet["detected_language"] == "tamil"
    assert packet["selected_language"] == "tamil"
    assert packet["document_labels"]["invoice"] == "பில்"
    assert packet["business_vocabulary"]["order"] == "ஆர்டர்"
    assert packet["sample_messages"]["payment_reminder"].startswith("வணக்கம்")
    assert packet["audit"] == {
        "translation_provider_called": False,
        "whatsapp_business_api_called": False,
        "voice_transcription_performed": False,
        "limitation": "Local regional-language operations contract only; no translation provider, WhatsApp Business API, or voice stack was called.",
    }


def test_should_build_language_operations_matrix_and_fallback_unsupported_preferences() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_1", name="Ramesh", preferred_language="marathi"),
            Customer(id="cust_2", name="Kumar", preferred_language="telugu"),
            Customer(id="cust_3", name="Rahul", preferred_language="french"),
        ],
    )

    matrix = build_language_operations_matrix(repository=repo)

    assert matrix["mode"] == "local_contract_mock"
    assert matrix["summary"] == {
        "supported_languages": 8,
        "customers_with_supported_language": 2,
        "customers_using_fallback": 1,
    }
    assert matrix["language_counts"]["marathi"] == 1
    assert matrix["language_counts"]["telugu"] == 1
    assert matrix["fallback_customers"] == [
        {
            "customer_id": "cust_3",
            "preferred_language": "french",
            "fallback_language": "english_hinglish",
            "code": "unsupported_language_preference",
        }
    ]
