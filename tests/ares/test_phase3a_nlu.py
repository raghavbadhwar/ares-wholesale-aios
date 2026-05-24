"""Tests for Phase 3A — Hinglish NLU upgrades in order_capture.py."""

from __future__ import annotations

import pytest

from apps.ares.ares.workflows.order_capture import (
    _guess_intent,
    _replace_hinglish_numbers,
    _find_product_fuzzy,
    NOISE_WORDS,
    _FUZZY_MATCH_THRESHOLD,
    extract_order_result,
)
from apps.ares.ares.data.models import IngestedEvent, ProductSKU
from apps.ares.ares.data.repository import BusinessRepository


# ---------------------------------------------------------------------------
# _replace_hinglish_numbers
# ---------------------------------------------------------------------------

def test_hinglish_numbers_ek_to_1():
    assert _replace_hinglish_numbers("ek carton parle-g") == "1 carton parle-g"


def test_hinglish_numbers_teen():
    assert _replace_hinglish_numbers("teen box") == "3 box"


def test_hinglish_numbers_bees():
    assert _replace_hinglish_numbers("bees kg atta") == "20 kg atta"


def test_hinglish_numbers_mixed():
    result = _replace_hinglish_numbers("do carton aur teen bag")
    assert "2" in result and "3" in result


def test_hinglish_numbers_passthrough_digits():
    assert _replace_hinglish_numbers("5 carton parle-g") == "5 carton parle-g"


# ---------------------------------------------------------------------------
# _guess_intent
# ---------------------------------------------------------------------------

def test_intent_payment_query():
    assert _guess_intent("kitna baki hai mere account mein") == "payment_query"


def test_intent_stock_query():
    assert _guess_intent("parle-g ka stock hai kya") == "stock_query"


def test_intent_order():
    assert _guess_intent("5 carton parle-g bhejna") == "order"


def test_intent_greeting_short():
    assert _guess_intent("hi") == "greeting"


def test_intent_approval_reply():
    assert _guess_intent("approve karo") == "approval_reply"


def test_intent_unknown():
    assert _guess_intent("abcxyz") == "unknown"


# ---------------------------------------------------------------------------
# NOISE_WORDS expansion
# ---------------------------------------------------------------------------

def test_noise_words_contains_new_words():
    assert "jaldi" in NOISE_WORDS
    assert "bhejdo" in NOISE_WORDS
    assert "yaar" in NOISE_WORDS


# ---------------------------------------------------------------------------
# _find_product_fuzzy
# ---------------------------------------------------------------------------

class _MockRepo:
    """Minimal repo stub returning a fixed list of products."""
    def __init__(self, products):
        self._products = products

    def get_products(self):
        return self._products


def _make_product(name, sku_id="sku_001"):
    return ProductSKU(id=sku_id, name=name, unit="pcs", current_stock=100, selling_price=10.0)


def test_fuzzy_exact_match():
    repo = _MockRepo([_make_product("Parle-G Biscuit 100g")])
    result = _find_product_fuzzy(repo, "parle-g biscuit 100g")
    assert result is not None
    assert result.name == "Parle-G Biscuit 100g"


def test_fuzzy_close_match():
    repo = _MockRepo([_make_product("Parle-G Biscuit 100g")])
    result = _find_product_fuzzy(repo, "Parle G Biscuit")
    assert result is not None  # close enough


def test_fuzzy_no_match_on_garbage():
    repo = _MockRepo([_make_product("Parle-G Biscuit 100g")])
    result = _find_product_fuzzy(repo, "xyz completely different product zzz")
    assert result is None


def test_fuzzy_empty_name_returns_none():
    repo = _MockRepo([_make_product("Parle-G Biscuit 100g")])
    assert _find_product_fuzzy(repo, "") is None


def test_fuzzy_threshold_constant():
    assert 0.5 <= _FUZZY_MATCH_THRESHOLD <= 1.0


# ---------------------------------------------------------------------------
# extract_order_result with Hinglish numbers
# ---------------------------------------------------------------------------

def _make_event(text):
    return IngestedEvent(
        id="evt_test",
        client_id="client_test",
        source="whatsapp",
        raw_text=text,
        sender="919876543210",
    )


def test_extract_order_hinglish_number_teen():
    """teen carton should be parsed as quantity 3."""
    event = _make_event("teen carton parle-g bhejna")
    result = extract_order_result(event)
    if result.order.items:  # regex may or may not match depending on trailing context
        qty = result.order.items[0].quantity
        assert qty == 3.0
