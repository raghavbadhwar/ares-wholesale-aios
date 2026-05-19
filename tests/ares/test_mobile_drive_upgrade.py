from __future__ import annotations

import json
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.drive_sync import sync_drive_manifest
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.face.mobile_approval import MobileApprovalAdapter, parse_mobile_reply
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_mobile_reply_parser_supports_hinglish_approval_commands() -> None:
    assert parse_mobile_reply("approve APPR_123") == {"decision": "approve", "approval_id": "appr_123", "edit_text": ""}
    assert parse_mobile_reply("haan appr_123") == {"decision": "approve", "approval_id": "appr_123", "edit_text": ""}
    assert parse_mobile_reply("reject appr_123") == {"decision": "reject", "approval_id": "appr_123", "edit_text": ""}
    assert parse_mobile_reply("edit appr_123 thoda soft tone me bhejo") == {
        "decision": "edit",
        "approval_id": "appr_123",
        "edit_text": "thoda soft tone me bhejo",
    }
    assert parse_mobile_reply("later appr_123") == {"decision": "ask_later", "approval_id": "appr_123", "edit_text": ""}


def test_mobile_approval_adapter_renders_numbered_mobile_prompt_and_executes_reply(tmp_path: Path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    approvals = ApprovalService(repo)
    approval = approvals.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send payment reminder",
        data={"customer": "Raj", "draft": "Payment status confirm karein"},
        reason="Payment overdue",
        source="payment_radar",
        confidence=0.9,
        dedupe_key="mobile:1",
    )
    adapter = MobileApprovalAdapter(repo, approvals)

    prompt = adapter.render_pending_prompt()
    result = adapter.handle_reply(f"approve {approval.id}", decided_by="owner")

    assert "1) Send payment reminder" in prompt
    assert f"approve {approval.id}" in prompt
    assert result["decision"] == "approved"
    assert result["execution"]["status"] == "executed"
    assert repo.list_action_logs()[0].action_type == "send_customer_message"


def test_drive_manifest_sync_downloads_new_files_and_ingests_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    remote = tmp_path / "remote_drive"
    remote.mkdir()
    outstanding = remote / "today_outstanding.csv"
    outstanding.write_text("id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj,1500,overdue\n", encoding="utf-8")
    message = remote / "order.txt"
    message.write_text("Raj 3 pkt Parle bhejna", encoding="utf-8")
    manifest = tmp_path / "drive_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {"id": "file_outstanding", "name": "today_outstanding.csv", "path": str(outstanding), "kind": "export"},
                {"id": "file_message", "name": "order.txt", "path": str(message), "kind": "message"},
            ]
        ),
        encoding="utf-8",
    )
    repo = JsonClientRepository(tmp_path / ".ares" / "clients" / "demo" / "data")

    first = sync_drive_manifest(client_id="demo", manifest_path=manifest, repository=repo)
    second = sync_drive_manifest(client_id="demo", manifest_path=manifest, repository=repo)

    assert first["files_synced"] == 2
    assert first["ingestion"]["exports_imported"] == 1
    assert first["ingestion"]["orders_captured"] == 1
    assert second["files_synced"] == 0
    assert second["ingestion"]["exports_imported"] == 0
    assert repo.get_outstanding()[0].amount == 1500
    assert repo.list_orders()[0].items[0].name == "Parle"
