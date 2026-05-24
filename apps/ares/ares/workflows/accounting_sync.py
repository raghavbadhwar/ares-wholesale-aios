"""Local accounting sync export contracts."""

from __future__ import annotations

import json
from typing import Any
from xml.etree import ElementTree

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_contract_token

LOCAL_SYNC_LIMITATION = "Local accounting sync contract only; no Tally/Busy company mutation or live bridge call was performed."


def prepare_accounting_sync_export(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    system: str,
    requested_by: str,
) -> dict:
    invoices = repository.get_invoices()
    batch_id = f"acct_{stable_contract_token(client_id, system, [item.id for item in invoices])}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="modify_ledger",
        proposed_action=f"Prepare {system} accounting sync export for {len(invoices)} invoice(s)",
        data={"batch_id": batch_id, "system": system, "invoice_ids": [item.id for item in invoices]},
        reason="Accounting sync is ledger-impacting and requires approval.",
        source="accounting_sync_contract",
        confidence=1.0,
        dedupe_key=f"accounting_sync:{batch_id}",
    )
    return {
        "status": "approval_required",
        "batch_id": batch_id,
        "approval_id": approval.id,
        "invoice_count": len(invoices),
        "audit": {"requested_by": requested_by, "live_bridge_called": False, "limitation": LOCAL_SYNC_LIMITATION},
    }


def normalize_accounting_bridge_payload(
    *,
    repository: BusinessRepository,
    client_id: str,
    system: str,
    bridge_mode: str,
    payload: Any,
) -> dict:
    mode = bridge_mode.strip().lower()
    if mode == "xml_status_receipt":
        items = _parse_xml_status_items(str(payload))
    elif mode == "odbc_rowset":
        items = _parse_odbc_rows(payload)
    else:
        raise ValueError(f"Unsupported accounting bridge mode: {bridge_mode}")

    manual = [item for item in items if item.get("status") == "needs_manual_review"]
    result = {
        "mode": "local_contract_mock",
        "status": "needs_manual_review" if manual else "accepted",
        "client_id": client_id,
        "system": system.strip().lower(),
        "bridge_mode": mode,
        "items": items,
        "summary": {
            "records_total": len(items),
            "accepted_records": len([item for item in items if item.get("status") == "accepted"]),
            "manual_review_records": len(manual),
        },
        "audit": {
            "external_write_performed": False,
            "ledger_mutation_performed": False,
            "bridge_payload_processed": True,
            "manual_fallback_required": bool(manual),
            "limitation": LOCAL_SYNC_LIMITATION,
        },
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_accounting_{stable_contract_token(client_id, system, mode, result['summary'])}",
            client_id=client_id,
            action_type="normalize_accounting_bridge_payload",
            status=result["status"],
            result={"summary": result["summary"], "bridge_mode": mode},
        )
    )
    return result


def import_accounting_sync_status(
    *,
    repository: BusinessRepository,
    client_id: str,
    system: str,
    status_payload: dict,
) -> dict:
    items = list(status_payload.get("items", []))
    result = {
        "mode": "local_contract_mock",
        "status": status_payload.get("status", "accepted"),
        "client_id": client_id,
        "system": system,
        "items": items,
        "summary": {
            "records_total": len(items),
            "accepted_records": len([item for item in items if item.get("status") == "accepted"]),
            "manual_review_records": len([item for item in items if item.get("status") == "needs_manual_review"]),
        },
        "audit": {
            "external_write_performed": False,
            "ledger_mutation_performed": False,
            "limitation": LOCAL_SYNC_LIMITATION,
        },
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_accounting_status_{stable_contract_token(client_id, system, result['summary'])}",
            client_id=client_id,
            action_type="import_accounting_sync_status",
            status=result["status"],
            result={"summary": result["summary"]},
        )
    )
    return result


def _parse_xml_status_items(payload: str) -> list[dict]:
    root = ElementTree.fromstring(payload)
    items = []
    for item in root.findall(".//ITEM"):
        record_type = (item.findtext("RECORDTYPE") or "").strip().lower()
        record_id = (item.findtext("RECORDID") or "").strip()
        status = (item.findtext("STATUS") or "accepted").strip().lower()
        items.append({"record_type": record_type, "record_id": record_id, "status": status})
    return items


def _parse_odbc_rows(payload: Any) -> list[dict]:
    if isinstance(payload, str):
        payload = json.loads(payload)
    rows = payload.get("rows", []) if isinstance(payload, dict) else list(payload or [])
    items = []
    for row in rows:
        voucher = str(row.get("voucher_number") or row.get("id") or "")
        record_type = "payment" if voucher.upper().startswith("PAY") else "invoice"
        status = str(row.get("status") or "accepted").lower()
        items.append(
            {
                "record_type": record_type,
                "record_id": voucher,
                "status": status,
                "amount": float(row.get("amount") or 0),
            }
        )
    return items
