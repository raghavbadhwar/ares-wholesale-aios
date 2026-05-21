from __future__ import annotations

import json

from apps.ares.ares.cli import main
from apps.ares.ares.workflows.benchmark_audit import (
    BENCHMARK_AUDIT_LIMITATION,
    build_benchmark_completion_audit,
)
from apps.ares.ares.workflows.integration_preflight import build_integration_prerequisite_preflight


def test_should_map_local_feature_coverage_without_claiming_benchmark_parity() -> None:
    audit = build_benchmark_completion_audit(latest_local_test_result="153 passed")

    assert audit["mode"] == "local_audit"
    assert audit["feature_rows_total"] == 48
    assert audit["local_or_contract_rows_covered"] == 48
    assert audit["benchmark_parity"] is False
    assert audit["ship_ready"] is False
    assert audit["latest_local_test_result"] == "153 passed"
    assert audit["done_state_gates"] == [
        {"gate": "small_wholesaler_no_training", "status": "not_proven"},
        {"gate": "large_distributor_monthly_compliance", "status": "not_proven"},
        {"gate": "ca_closes_books_without_reentry", "status": "not_proven"},
        {"gate": "zero_gst_penalty_12_months", "status": "not_proven"},
        {"gate": "every_rupee_udhaar_settled", "status": "not_proven"},
        {"gate": "reliable_7am_owner_briefing", "status": "not_proven"},
    ]
    assert "hosted_saas_auth_billing" in audit["production_blockers"]
    assert "live_gstn_nic_integration" in audit["production_blockers"]
    assert audit["audit"]["limitation"] == BENCHMARK_AUDIT_LIMITATION


def test_should_trace_every_source_of_truth_feature_row_to_local_evidence_without_production_proof() -> None:
    audit = build_benchmark_completion_audit(latest_local_test_result="180 passed")

    assert audit["feature_evidence"] == {
        "source_of_truth_feature_rows_traced": True,
        "feature_rows_with_evidence": 48,
        "feature_rows_missing_evidence": [],
        "feature_rows_with_production_proof": 0,
    }

    rows = {row["name"]: row for row in audit["feature_rows"]}
    assert len(rows) == 48
    assert all(row["implementation_slice"] for row in rows.values())
    assert all(row["workflow_files"] for row in rows.values())
    assert all(row["test_files"] for row in rows.values())
    assert all(row["coverage_type"] in {"local", "contract_only", "local_or_contract"} for row in rows.values())
    assert all(row["production_proof"]["status"] == "not_proven" for row in rows.values())

    assert rows["GSTR-1 Auto-Preparation"] == {
        "name": "GSTR-1 Auto-Preparation",
        "module": "MOD-01 — GST & Compliance Engine",
        "priority": "P0",
        "status": "local_or_contract_covered",
        "coverage_type": "local_or_contract",
        "implementation_slice": "A7",
        "workflow_files": ["apps/ares/ares/workflows/gstr1.py"],
        "test_files": ["tests/ares/test_gstr1_preparation.py"],
        "current_limitation": "Local filing-preparation contract only; no GSTN submission, portal state, upload JSON, or filing certification.",
        "production_proof": {
            "status": "not_proven",
            "required_evidence": [
                "GSTN/NIC sandbox adapter run with approved non-production credentials",
                "Accountant-reviewed filing artifact for the target return period",
            ],
        },
    }
    assert rows["WhatsApp Business Integration"]["coverage_type"] == "contract_only"
    assert rows["WhatsApp Business Integration"]["production_proof"]["required_evidence"] == [
        "Meta/WhatsApp Business sandbox or production test tenant",
        "Approved template registration and delivery/webhook evidence without customer-impacting sends",
    ]


def test_should_embed_integration_preflight_without_claiming_external_integrations_verified() -> None:
    preflight = build_integration_prerequisite_preflight(
        configured_env_names=set(),
        selected_providers={"razorpay"},
    )

    audit = build_benchmark_completion_audit(
        latest_local_test_result="176 passed",
        integration_preflight=preflight,
    )

    assert audit["ship_ready"] is False
    assert audit["benchmark_parity"] is False
    assert audit["integration_preflight"] == {
        "included": True,
        "mode": "local_preflight",
        "status": "blocked",
        "provider_scope": ["razorpay"],
        "ready_provider_count": 0,
        "blocked_provider_count": 1,
        "blocked_providers": [
            {
                "provider": "razorpay",
                "status": "missing_credentials",
                "missing_env_names": [
                    "RAZORPAY_SANDBOX_KEY_ID",
                    "RAZORPAY_SANDBOX_KEY_SECRET",
                    "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
                ],
                "safe_test_environment_confirmed": False,
                "can_run_sandbox_adapter_tests": False,
                "blocked_reasons": [
                    "missing sandbox environment names: RAZORPAY_SANDBOX_KEY_ID, RAZORPAY_SANDBOX_KEY_SECRET, RAZORPAY_SANDBOX_WEBHOOK_SECRET",
                    "safe non-production sandbox tenant not confirmed for razorpay",
                ],
                "benchmark_feature_rows": [
                    "UPI Payment Reconciliation",
                    "UPI & Payment Gateway",
                ],
                "production_blockers_addressed": [
                    "live_payment_gateway_webhooks",
                ],
            }
        ],
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
        },
    }
    assert "external_integration_preflight_blocked" in audit["production_blockers"]
    assert audit["audit"]["external_integrations_verified"] is False


def test_benchmark_audit_cli_reports_blockers_without_claiming_ship_ready(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "benchmark-audit", "--latest-local-test-result", "162 passed", "--json"],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["latest_local_test_result"] == "162 passed"
    assert payload["feature_rows_total"] == 48
    assert payload["feature_evidence"]["feature_rows_with_evidence"] == 48
    assert payload["feature_evidence"]["feature_rows_with_production_proof"] == 0
    assert payload["ship_ready"] is False
    assert payload["benchmark_parity"] is False
    assert "live_whatsapp_business_api" in payload["production_blockers"]
    assert payload["audit"]["local_tests_are_sufficient_for_ship_ready_claim"] is False


def test_benchmark_audit_cli_can_include_scoped_integration_preflight(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "benchmark-audit",
            "--latest-local-test-result",
            "176 passed",
            "--include-integration-preflight",
            "--provider",
            "razorpay",
            "--json",
        ],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["latest_local_test_result"] == "176 passed"
    assert payload["ship_ready"] is False
    assert payload["integration_preflight"]["included"] is True
    assert payload["integration_preflight"]["provider_scope"] == ["razorpay"]
    assert payload["integration_preflight"]["status"] == "blocked"
    assert payload["integration_preflight"]["blocked_provider_count"] == 1
    assert payload["integration_preflight"]["blocked_providers"][0]["production_blockers_addressed"] == [
        "live_payment_gateway_webhooks"
    ]
    assert payload["integration_preflight"]["audit"]["secret_values_inspected"] is False
    assert payload["integration_preflight"]["audit"]["live_api_called"] is False


def test_benchmark_audit_cli_returns_json_for_unknown_embedded_preflight_provider(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "benchmark-audit",
            "--latest-local-test-result",
            "178 passed",
            "--include-integration-preflight",
            "--provider",
            "stripe",
            "--json",
        ],
    )

    assert main() == 1
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["error"]["code"] == "unknown_integration_provider"
    assert "Unknown integration provider: stripe" in payload["error"]["message"]
    assert "razorpay" in payload["error"]["valid_providers"]
    assert payload["audit"]["secret_values_inspected"] is False
    assert payload["audit"]["live_api_called"] is False


def test_benchmark_audit_text_output_includes_integration_preflight_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "benchmark-audit",
            "--latest-local-test-result",
            "178 passed",
            "--include-integration-preflight",
            "--provider",
            "razorpay",
        ],
    )

    assert main() == 1
    output = capsys.readouterr().out

    assert "Integration preflight: blocked" in output
    assert "Feature evidence traced: 48/48" in output
    assert "Production-proof feature rows: 0/48" in output
    assert "Provider scope: razorpay" in output
    assert "- razorpay: missing_credentials" in output
    assert "RAZORPAY_SANDBOX_KEY_ID" in output
    assert "safe sandbox confirmed: False" in output
    assert "benchmark feature rows: UPI Payment Reconciliation, UPI & Payment Gateway" in output
    assert "production blockers addressed: live_payment_gateway_webhooks" in output
    assert "secret values inspected: False" in output
