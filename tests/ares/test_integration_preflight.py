from __future__ import annotations

import json

from apps.ares.ares.cli import main
from apps.ares.ares.workflows.integration_preflight import (
    INTEGRATION_PREFLIGHT_LIMITATION,
    PROVIDER_REQUIREMENTS,
    build_integration_env_template,
    build_integration_provider_catalog,
    build_integration_prerequisite_preflight,
    build_integration_readiness_packet,
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
    assert preflight["providers"]["razorpay"]["can_run_sandbox_adapter_tests"] is True
    assert preflight["providers"]["razorpay"]["blocked_reasons"] == []
    assert preflight["providers"]["razorpay"]["allowed_sandbox_test_scope"] == [
        "instantiate_provider_sandbox_client",
        "validate_local_request_signing_or_payload_shape",
        "run_mock_or_provider_sandbox_health_checks_after_operator_confirmation",
    ]
    assert "production submissions" in preflight["providers"]["razorpay"]["forbidden_test_scope"]
    assert preflight["providers"]["razorpay"]["benchmark_feature_rows"] == [
        "UPI Payment Reconciliation",
        "UPI & Payment Gateway",
    ]
    assert preflight["providers"]["razorpay"]["production_blockers_addressed"] == [
        "live_payment_gateway_webhooks"
    ]


def test_should_filter_preflight_to_selected_provider_for_sandbox_rollout() -> None:
    preflight = build_integration_prerequisite_preflight(
        configured_env_names=set(),
        selected_providers={"razorpay"},
    )

    assert preflight["provider_scope"] == ["razorpay"]
    assert list(preflight["providers"]) == ["razorpay"]
    assert preflight["ready_provider_count"] == 0
    assert preflight["blocked_provider_count"] == 1
    assert preflight["providers"]["razorpay"]["status"] == "missing_credentials"
    assert preflight["providers"]["razorpay"]["can_run_sandbox_adapter_tests"] is False
    assert preflight["providers"]["razorpay"]["blocked_reasons"] == [
        "missing sandbox environment names: RAZORPAY_SANDBOX_KEY_ID, RAZORPAY_SANDBOX_KEY_SECRET, RAZORPAY_SANDBOX_WEBHOOK_SECRET",
        "safe non-production sandbox tenant not confirmed for razorpay",
    ]
    assert preflight["providers"]["razorpay"]["next_required_actions"] == [
        "configure sandbox-only environment variable names for razorpay",
        "confirm razorpay is a safe non-production sandbox tenant before adapter tests",
    ]


def test_should_reject_unknown_selected_provider() -> None:
    try:
        build_integration_prerequisite_preflight(selected_providers={"stripe"})
    except ValueError as exc:
        assert "Unknown integration provider: stripe" in str(exc)
        assert "razorpay" in str(exc)
    else:
        raise AssertionError("Expected unknown provider to be rejected")


def test_should_reject_unknown_safe_sandbox_confirmation_provider() -> None:
    try:
        build_integration_prerequisite_preflight(
            selected_providers={"razorpay"},
            safe_test_environment_confirmations={"stripe"},
        )
    except ValueError as exc:
        assert "Unknown safe sandbox confirmation provider: stripe" in str(exc)
        assert "razorpay" in str(exc)
    else:
        raise AssertionError("Expected unknown safe sandbox confirmation provider to be rejected")


def test_should_reject_safe_sandbox_confirmation_outside_selected_provider_scope() -> None:
    try:
        build_integration_prerequisite_preflight(
            selected_providers={"razorpay"},
            safe_test_environment_confirmations={"cashfree"},
        )
    except ValueError as exc:
        assert "Safe sandbox confirmation provider outside selected provider scope: cashfree" in str(exc)
        assert "razorpay" in str(exc)
    else:
        raise AssertionError("Expected out-of-scope safe sandbox confirmation provider to be rejected")


def test_should_build_provider_catalog_for_operator_sandbox_setup() -> None:
    catalog = build_integration_provider_catalog(selected_providers={"razorpay"})

    assert catalog["mode"] == "local_preflight_provider_catalog"
    assert catalog["provider_scope"] == ["razorpay"]
    assert catalog["provider_count"] == 1
    assert catalog["providers"]["razorpay"] == {
        "provider": "razorpay",
        "required_env_names": [
            "RAZORPAY_SANDBOX_KEY_ID",
            "RAZORPAY_SANDBOX_KEY_SECRET",
            "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
        ],
        "scope_flag": "--provider razorpay",
        "confirmation_flag": "--confirm-safe-sandbox razorpay",
        "requires_sandbox_named_env": True,
        "secret_values_inspected": False,
        "live_api_called": False,
        "sandbox_submission_performed": False,
        "allowed_sandbox_test_scope": [
            "instantiate_provider_sandbox_client",
            "validate_local_request_signing_or_payload_shape",
            "run_mock_or_provider_sandbox_health_checks_after_operator_confirmation",
        ],
        "forbidden_test_scope": [
            "production submissions",
            "live filings",
            "real payment collection",
            "customer or supplier messaging",
            "secret value printing or persistence",
        ],
        "next_required_actions": [
            "configure sandbox-only environment variable names for razorpay",
            "confirm razorpay is a safe non-production sandbox tenant before adapter tests",
        ],
        "benchmark_feature_rows": [
            "UPI Payment Reconciliation",
            "UPI & Payment Gateway",
        ],
        "production_blockers_addressed": [
            "live_payment_gateway_webhooks",
        ],
    }
    assert catalog["audit"]["secret_values_inspected"] is False
    assert catalog["audit"]["live_api_called"] is False
    assert catalog["audit"]["sandbox_submission_performed"] is False


def test_should_build_provider_readiness_packet_for_sandbox_adapter_handoff() -> None:
    packet = build_integration_readiness_packet(
        configured_env_names=set(),
        selected_providers={"razorpay"},
    )

    assert packet["mode"] == "local_preflight_readiness_packet"
    assert packet["status"] == "blocked"
    assert packet["provider_scope"] == ["razorpay"]
    assert packet["ready_provider_count"] == 0
    assert packet["blocked_provider_count"] == 1

    razorpay = packet["providers"]["razorpay"]
    assert razorpay["status"] == "missing_credentials"
    assert razorpay["can_run_sandbox_adapter_tests"] is False
    assert razorpay["adapter_hardening_gate"] == "blocked_until_checklist_passes"
    assert razorpay["setup_checklist"] == [
        {
            "id": "sandbox_environment_names",
            "status": "blocked",
            "required_env_names": [
                "RAZORPAY_SANDBOX_KEY_ID",
                "RAZORPAY_SANDBOX_KEY_SECRET",
                "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
            ],
            "missing_env_names": [
                "RAZORPAY_SANDBOX_KEY_ID",
                "RAZORPAY_SANDBOX_KEY_SECRET",
                "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
            ],
        },
        {
            "id": "safe_non_production_sandbox_confirmation",
            "status": "blocked",
            "confirmation_flag": "--confirm-safe-sandbox razorpay",
        },
    ]
    assert razorpay["operator_commands"] == [
        "ares integration-preflight --list-providers --provider razorpay --json",
        "ares integration-preflight --provider razorpay --json",
        "ares integration-preflight --provider razorpay --confirm-safe-sandbox razorpay --json",
    ]
    assert razorpay["benchmark_feature_rows"] == [
        "UPI Payment Reconciliation",
        "UPI & Payment Gateway",
    ]
    assert razorpay["production_blockers_addressed"] == [
        "live_payment_gateway_webhooks",
    ]
    assert "provider sandbox account or tenant identifier" in razorpay["required_external_artifacts"]
    assert "production submissions" in razorpay["forbidden_test_scope"]
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
    assert packet["audit"]["sandbox_submission_performed"] is False


def test_should_build_sandbox_env_template_without_secret_values() -> None:
    template = build_integration_env_template(selected_providers={"razorpay"})

    assert template["mode"] == "local_preflight_env_template"
    assert template["provider_scope"] == ["razorpay"]
    assert template["format"] == "dotenv"
    assert template["providers"]["razorpay"]["env_template_lines"] == [
        "# razorpay sandbox integration",
        "RAZORPAY_SANDBOX_KEY_ID=",
        "RAZORPAY_SANDBOX_KEY_SECRET=",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET=",
    ]
    assert template["providers"]["razorpay"]["env_names"] == [
        "RAZORPAY_SANDBOX_KEY_ID",
        "RAZORPAY_SANDBOX_KEY_SECRET",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
    ]
    assert template["providers"]["razorpay"]["values_included"] is False
    assert template["audit"]["secret_values_inspected"] is False
    assert template["audit"]["live_api_called"] is False
    assert template["audit"]["sandbox_submission_performed"] is False


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


def test_integration_preflight_cli_can_scope_to_one_provider(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["ares", "integration-preflight", "--provider", "razorpay", "--json"])

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["provider_scope"] == ["razorpay"]
    assert list(payload["providers"]) == ["razorpay"]
    assert payload["blocked_provider_count"] == 1
    assert payload["providers"]["razorpay"]["secret_values_inspected"] is False
    assert payload["providers"]["razorpay"]["live_api_called"] is False


def test_integration_preflight_cli_can_list_provider_catalog(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "integration-preflight", "--list-providers", "--provider", "razorpay", "--json"],
    )

    assert main() == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["mode"] == "local_preflight_provider_catalog"
    assert payload["provider_scope"] == ["razorpay"]
    assert payload["providers"]["razorpay"]["required_env_names"] == [
        "RAZORPAY_SANDBOX_KEY_ID",
        "RAZORPAY_SANDBOX_KEY_SECRET",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
    ]
    assert payload["providers"]["razorpay"]["secret_values_inspected"] is False
    assert payload["providers"]["razorpay"]["live_api_called"] is False


def test_integration_preflight_cli_can_emit_provider_readiness_packet(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "integration-preflight", "--readiness-packet", "--provider", "razorpay", "--json"],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["mode"] == "local_preflight_readiness_packet"
    assert payload["provider_scope"] == ["razorpay"]
    assert payload["providers"]["razorpay"]["adapter_hardening_gate"] == "blocked_until_checklist_passes"
    assert payload["providers"]["razorpay"]["secret_values_inspected"] is False
    assert payload["providers"]["razorpay"]["live_api_called"] is False


def test_integration_preflight_cli_can_emit_sandbox_env_template(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "integration-preflight", "--env-template", "--provider", "razorpay", "--json"],
    )

    assert main() == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["mode"] == "local_preflight_env_template"
    assert payload["provider_scope"] == ["razorpay"]
    assert payload["providers"]["razorpay"]["env_template_lines"] == [
        "# razorpay sandbox integration",
        "RAZORPAY_SANDBOX_KEY_ID=",
        "RAZORPAY_SANDBOX_KEY_SECRET=",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET=",
    ]
    assert payload["providers"]["razorpay"]["values_included"] is False
    assert payload["audit"]["secret_values_inspected"] is False
    assert payload["audit"]["live_api_called"] is False


def test_integration_preflight_cli_returns_json_for_unknown_provider(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["ares", "integration-preflight", "--provider", "stripe", "--json"])

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["error"]["code"] == "unknown_integration_provider"
    assert "Unknown integration provider: stripe" in payload["error"]["message"]
    assert "razorpay" in payload["error"]["valid_providers"]
    assert payload["audit"]["secret_values_inspected"] is False
    assert payload["audit"]["live_api_called"] is False


def test_integration_preflight_cli_returns_json_for_unknown_confirmation_provider(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "integration-preflight", "--provider", "razorpay", "--confirm-safe-sandbox", "stripe", "--json"],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["error"]["code"] == "unknown_integration_provider"
    assert "Unknown safe sandbox confirmation provider: stripe" in payload["error"]["message"]
    assert "razorpay" in payload["error"]["valid_providers"]
    assert payload["audit"]["secret_values_inspected"] is False
    assert payload["audit"]["live_api_called"] is False


def test_integration_preflight_cli_returns_json_for_confirmation_outside_provider_scope(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "integration-preflight", "--provider", "razorpay", "--confirm-safe-sandbox", "cashfree", "--json"],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["error"]["code"] == "invalid_integration_provider_scope"
    assert "Safe sandbox confirmation provider outside selected provider scope: cashfree" in payload["error"]["message"]
    assert payload["error"]["selected_providers"] == ["razorpay"]
    assert "cashfree" in payload["error"]["valid_providers"]
    assert payload["audit"]["secret_values_inspected"] is False
    assert payload["audit"]["live_api_called"] is False
