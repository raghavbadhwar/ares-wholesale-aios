from __future__ import annotations

import json

from apps.ares.ares.cli import main
from apps.ares.ares.workflows.benchmark_audit import (
    BENCHMARK_AUDIT_LIMITATION,
    build_benchmark_completion_audit,
)


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
    assert payload["ship_ready"] is False
    assert payload["benchmark_parity"] is False
    assert "live_whatsapp_business_api" in payload["production_blockers"]
    assert payload["audit"]["local_tests_are_sufficient_for_ship_ready_claim"] is False
