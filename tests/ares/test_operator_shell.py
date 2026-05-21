from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.cli import main
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import Invoice, Order, ProductSKU, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.face.operator_shell import LOCAL_OPERATOR_SHELL_LIMITATION, build_operator_shell
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_should_build_local_operator_shell_across_benchmark_surfaces() -> None:
    repo = InMemoryRepository.from_records(
        products=[ProductSKU(id="sku_soap", name="Soap Case", current_stock=4, reorder_level=10)],
        stock_records=[StockRecord(sku_id="sku_soap", name="Soap Case", current_stock=4, reorder_level=10)],
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=12000, status="overdue")],
        orders=[Order(id="ord_1", customer_id="cust_1", status="pending")],
    )
    approvals = ApprovalService(repo)
    approvals.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send payment reminder",
        data={"customer": "cust_1"},
        reason="Payment overdue",
        source="test",
        confidence=0.9,
    )
    profile = ClientProfile(client_slug="demo", business_name="Demo Distributors", owner_name="Owner")

    shell = build_operator_shell(profile=profile, repository=repo, approvals=approvals)

    assert shell["mode"] == "local_operator_shell"
    assert shell["client"]["business_name"] == "Demo Distributors"
    assert shell["metrics"] == {
        "pending_approvals": 1,
        "pending_orders": 1,
        "overdue_invoices": 1,
        "low_stock_skus": 1,
        "action_logs": 0,
    }
    assert [section["id"] for section in shell["sections"]] == [
        "command_center",
        "owner_approvals",
        "collections",
        "inventory",
        "compliance",
        "integrations",
    ]
    assert shell["readiness"] == {
        "local_operator_shell": True,
        "hosted_saas": False,
        "production_auth": False,
        "billing": False,
        "live_external_integrations": False,
    }
    assert shell["audit"]["limitation"] == LOCAL_OPERATOR_SHELL_LIMITATION


def test_operator_shell_cli_outputs_json_without_saas_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    repo = JsonClientRepository(tmp_path / ".ares" / "clients" / "demo" / "data")
    repo.upsert_invoice(Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=1000, status="overdue"))
    monkeypatch.setattr("sys.argv", ["ares", "operator-shell", "--client", "demo", "--json"])

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "local_operator_shell"
    assert payload["metrics"]["overdue_invoices"] == 1
    assert payload["readiness"]["hosted_saas"] is False
    assert payload["readiness"]["live_external_integrations"] is False
