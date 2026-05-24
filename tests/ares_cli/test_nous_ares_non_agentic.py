"""Tests for the Nous-Ares-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"ares"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``ares-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "ares" tag namespace.

``is_nous_ares_non_agentic`` should only match the actual Nous Research
Ares-3 / Ares-4 chat family.
"""

from __future__ import annotations

import pytest

from ares_cli.model_switch import (
    _ARES_MODEL_WARNING,
    _check_ares_model_warning,
    is_nous_ares_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Ares-3-Llama-3.1-70B",
        "NousResearch/Ares-3-Llama-3.1-405B",
        "ares-3",
        "Ares-3",
        "ares-4",
        "ares-4-405b",
        "ares_4_70b",
        "openrouter/ares3:70b",
        "openrouter/nousresearch/ares-4-405b",
        "NousResearch/Ares3",
        "ares-3.1",
    ],
)
def test_matches_real_nous_ares_chat_models(model_name: str) -> None:
    assert is_nous_ares_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Ares 3/4"
    )
    assert _check_ares_model_warning(model_name) == _ARES_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "ares-brain:qwen3-14b-ctx16k",
        "ares-brain:qwen3-14b-ctx32k",
        "ares-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat Ares models we don't warn about
        "ares-llm-2",
        "ares2-pro",
        "nous-ares-2-mistral",
        # Edge cases
        "",
        "ares",  # bare "ares" isn't the 3/4 family
        "ares-brain",
        "brain-ares-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_ares_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous Ares 3/4"
    )
    assert _check_ares_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_ares_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_ares_model_warning("") == ""
