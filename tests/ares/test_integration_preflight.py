from __future__ import annotations

import json

from apps.ares.ares.cli import main
from apps.ares.ares.workflows.integration_preflight import (
    INTEGRATION_PREFLIGHT_LIMITATION,
    PROVIDER_REQUIREMENTS,
    build_integration_prerequisite_preflight,
)


def test_should_block_live_integration_hardening_when_required_sandbox_env_names_are_missing() -> None:
    preflight = build_integration_prerequisite_preflight(configured_env_names=set())

    assert preflight["mode"] == "local_preflight"
    assert preflight["status"] == "blocked"
    assert preflight["ready_provider_count"] == 0
    assert preflight["providers"]["gstn_nic"]["status"] == "missing_credentials"
    assert preflight["providers"]["gstn_nic"]["missing_env_names"] == [
        "GSTN_SANDBOX_BASE_URL",
        "GSTN_SANDBOX_CLIENT_ID",
        "GSTN_SANDBOX_CLIENT_SECRET",
        "NIC_SANDBOX_BASE_URL",
        "NIC_SANDBOX_CLIENT_ID",
        "NIC_SANDBOX_CLIENT_SECRET",
    ]
    assert preflight["providers"]["razorpay"]["secret_values_inspected"] is False
    assert preflight["audit"] == {
        "secret_values_inspected": False,
        "live_api_called": False,
        "sandbox_submission_performed": False,
        "limitation": INTEGRATION_PREFLIGHT_LIMITATION,
    }


def test_should_require_explicit_safety_confirmation_even_when_env_names_exist() -> None:
    preflight = build_integration_prerequisite_preflight(
        configured_env_names={
            "RAZORPAY_SANDBOX_KEY_ID",
            "RAZORPAY_SANDBOX_KEY_SECRET",
            "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
        }
    )

    assert preflight["status"] == "blocked"
    assert preflight["providers"]["razorpay"]["status"] == "needs_safety_confirmation"
    assert preflight["providers"]["razorpay"]["missing_env_names"] == []
    assert preflight["providers"]["razorpay"]["safe_test_environment_confirmed"] is False


def test_should_mark_provider_ready_when_env_names_and_safety_confirmation_are_present() -> None:
    preflight = build_integration_prerequisite_preflight(
        configured_env_names={
            "RAZORPAY_SANDBOX_KEY_ID",
            "RAZORPAY_SANDBOX_KEY_SECRET",
            "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
        },
        safe_test_environment_confirmations={"razorpay"},
    )

    assert preflight["status"] == "partial_ready"
    assert preflight["ready_provider_count"] == 1
    assert preflight["providers"]["razorpay"]["status"] == "ready_for_sandbox_adapter_tests"


def test_should_not_mark_generic_production_credential_names_ready() -> None:
    preflight = build_integration_prerequisite_preflight(
        configured_env_names={"RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"},
        safe_test_environment_confirmations={"razorpay"},
    )

    assert preflight["status"] == "blocked"
    assert preflight["providers"]["razorpay"]["status"] == "missing_credentials"
    assert preflight["providers"]["razorpay"]["missing_env_names"] == [
        "RAZORPAY_SANDBOX_KEY_ID",
        "RAZORPAY_SANDBOX_KEY_SECRET",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
    ]


def test_should_return_ready_when_all_providers_have_sandbox_env_names_and_confirmations() -> None:
    configured_env_names = {name for required in PROVIDER_REQUIREMENTS.values() for name in required}

    preflight = build_integration_prerequisite_preflight(
        configured_env_names=configured_env_names,
        safe_test_environment_confirmations=set(PROVIDER_REQUIREMENTS),
    )

    assert preflight["status"] == "ready"
    assert preflight["ready_provider_count"] == len(PROVIDER_REQUIREMENTS)
    assert preflight["blocked_provider_count"] == 0


def test_all_provider_requirements_are_sandbox_named() -> None:
    for provider, required_env_names in PROVIDER_REQUIREMENTS.items():
        assert all("SANDBOX" in name for name in required_env_names), provider


def test_integration_preflight_cli_reports_missing_env_names_without_secret_values(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_ID", "should-not-print")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "should-not-print")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "should-not-print")
    monkeypatch.setattr("sys.argv", ["ares", "integration-preflight", "--json"])

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["providers"]["razorpay"]["status"] == "missing_credentials"
    assert "should-not-print" not in output
    assert payload["audit"]["secret_values_inspected"] is False
