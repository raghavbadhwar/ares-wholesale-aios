"""Tests for Phase 3B/3C — regional translation and KYC verification."""

from __future__ import annotations

import pytest

from apps.ares.ares.workflows.regional_language import (
    translate_to_regional,
    translate_from_regional,
    detect_language,
)
from apps.ares.ares.workflows.party_onboarding import (
    verify_gstin_online,
    verify_party_pan,
    _gstin_checksum_valid,
)


# ---------------------------------------------------------------------------
# translate_to_regional
# ---------------------------------------------------------------------------

def test_translate_payment_reminder_to_tamil():
    result = translate_to_regional(
        text="Your outstanding is pending.",
        target_language="tamil",
        phrase_key="payment_reminder",
    )
    assert result["mode"] == "local_phrasebook"
    assert result["target_language"] == "tamil"
    assert "பாக்கி" in result["translated_text"]  # Tamil word for outstanding
    assert result["audit"]["translation_provider_called"] is False


def test_translate_payment_reminder_to_gujarati():
    result = translate_to_regional(
        text="Payment pending.",
        target_language="gujarati",
        phrase_key="payment_reminder",
    )
    assert result["mode"] == "local_phrasebook"
    assert "ઉધાર" in result["translated_text"]  # Gujarati outstanding


def test_translate_order_confirmation_to_marathi():
    result = translate_to_regional(
        text="Order confirmed.",
        target_language="marathi",
        phrase_key="order_confirmation",
    )
    assert result["mode"] == "local_phrasebook"
    assert "ऑर्डर" in result["translated_text"]


def test_translate_no_phrase_key_uses_vocabulary_substitution():
    result = translate_to_regional(
        text="Your order and invoice are ready.",
        target_language="hindi",  # normalised to english_hinglish
    )
    assert result["translation_method"] in ("vocabulary_substitution", "phrasebook_lookup")
    assert result["audit"]["translation_provider_called"] is False


def test_translate_stock_alert_to_kannada():
    result = translate_to_regional(
        text="Stock is low.",
        target_language="kannada",
        phrase_key="stock_alert",
    )
    assert result["mode"] == "local_phrasebook"
    assert "ಸ್ಟಾಕ್" in result["translated_text"]


# ---------------------------------------------------------------------------
# translate_from_regional
# ---------------------------------------------------------------------------

def test_translate_from_english_hinglish_passthrough():
    result = translate_from_regional(text="Your order is confirmed.")
    assert result["mode"] == "local_passthrough"
    assert result["normalised_text"] == "Your order is confirmed."


def test_translate_from_tamil_detected():
    tamil_text = "உங்கள் ஆர்டர் பில் தயார்."  # Your order bill is ready
    result = translate_from_regional(text=tamil_text, source_language="tamil")
    assert result["detected_language"] == "tamil"
    assert "order" in result["normalised_text"].lower()  # vocabulary reverse-mapped


def test_translate_from_explicit_language_override():
    result = translate_from_regional(
        text="ஆர்டர் கிடைத்தது",
        source_language="tamil",
    )
    assert result["detected_language"] == "tamil"
    assert result["audit"]["translation_provider_called"] is False


# ---------------------------------------------------------------------------
# verify_gstin_online — local format validation
# ---------------------------------------------------------------------------

def test_verify_gstin_valid_format():
    # 27AAACR5055K1Z7 — Maharashtra, check digit '7' computed by _gstin_checksum_valid
    result = verify_gstin_online("27AAACR5055K1Z7")
    assert result["mode"] == "local_format_validation"
    assert result["format_valid"] is True
    assert result["state_code"] == 27
    assert result["api_verified"] is False


def test_verify_gstin_invalid_too_short():
    result = verify_gstin_online("12345")
    assert result["format_valid"] is False


def test_verify_gstin_invalid_format_chars():
    result = verify_gstin_online("00INVALID00000X")
    assert result["format_valid"] is False


def test_verify_gstin_checksum_valid_known_gstin():
    # 27AAACR5055K1Z7 has correct check digit per _gstin_checksum_valid algorithm
    assert _gstin_checksum_valid("27AAACR5055K1Z7") is True


def test_verify_gstin_checksum_invalid():
    assert _gstin_checksum_valid("27AAACR5055K1Z5") is False  # wrong check digit (should be 7)


def test_verify_gstin_state_code_out_of_range():
    # State code 99 is not a valid Indian state code
    result = verify_gstin_online("99AAACR5055K1Z5")
    assert result.get("state_code_valid") is False or result["format_valid"] is False


def test_verify_gstin_limitation_in_local_mode():
    result = verify_gstin_online("27AAACR5055K1Z5")
    assert result["audit"]["gstn_sandbox_called"] is False


# ---------------------------------------------------------------------------
# verify_party_pan — local format validation
# ---------------------------------------------------------------------------

def test_verify_pan_valid_individual():
    # ABCFE1234X — pan[3]='F' = Firm (4th character at 0-indexed position 3)
    result = verify_party_pan("ABCFE1234X")
    assert result["format_valid"] is True
    assert result["taxpayer_type"] == "Firm"  # F = Firm
    assert result["api_verified"] is False


def test_verify_pan_valid_company():
    result = verify_party_pan("AABCS1429B")
    assert result["format_valid"] is True


def test_verify_pan_invalid_format():
    result = verify_party_pan("ABCDE12345")  # 10 chars but ends with digit not alpha
    assert result["format_valid"] is False


def test_verify_pan_invalid_too_short():
    result = verify_party_pan("ABC123")
    assert result["format_valid"] is False


def test_verify_pan_limitation_in_local_mode():
    result = verify_party_pan("ABCDE1234F")
    assert result["audit"]["it_sandbox_called"] is False
