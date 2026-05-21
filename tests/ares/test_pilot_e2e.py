from __future__ import annotations

from pathlib import Path

import pytest

from apps.ares.ares.cli import main
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_pilot_operator_flow_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    root = tmp_path / ".ares" / "clients" / "demo"

    (root / "exports" / "tally_outstanding.csv").write_text(
        "id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj,2500,overdue\n",
        encoding="utf-8",
    )
    (root / "exports" / "stock_export.csv").write_text(
        "sku_id,name,current_stock,reorder_level\nsurf,Surf,2,10\n",
        encoding="utf-8",
    )
    (root / "inbox" / "order_1.txt").write_text("Raj 5 box Surf kal bhejna", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["ares", "validate-inputs", "--client", "demo"])
    assert main() == 0
    assert "Inputs look ready for processing" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["ares", "morning-run", "--client", "demo"])
    assert main() == 0
    morning_output = capsys.readouterr().out
    assert "Ares morning run for demo" in morning_output
    assert "Approvals created: 1" in morning_output

    repo = JsonClientRepository(root / "data")
    approval = repo.list_pending_approvals()[0]

    monkeypatch.setattr("sys.argv", ["ares", "mobile-reply", "--client", "demo", "--reply", f"haan {approval.id}"])
    assert main() == 0
    mobile_output = capsys.readouterr().out
    assert "approved" in mobile_output.lower()

    reloaded = JsonClientRepository(root / "data")
    assert reloaded.list_pending_approvals() == []
    assert reloaded.list_action_logs()[0].action_type == "send_customer_message"
    assert reloaded.list_orders()[0].items[0].name == "Surf"
