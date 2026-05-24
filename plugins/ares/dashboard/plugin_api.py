"""Ares dashboard plugin API routes.

Mounted at /api/plugins/ares/ by the Ares dashboard plugin system.
The routes stay local and approval-first: they read Ares client state, run
implemented local workflows, and never call live external integrations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

ACTIVE_CONNECTIONS: set[WebSocket] = set()


async def broadcast_update() -> None:
    for ws in list(ACTIVE_CONNECTIONS):
        try:
            await ws.send_json({"type": "update"})
        except Exception:
            ACTIVE_CONNECTIONS.discard(ws)


from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.autonomy.runner import run_autonomous_cycle, run_morning_run
from apps.ares.ares.command_center import build_wholesaler_command_library, group_commands
from apps.ares.ares.connectors.auto_ingest import validate_local_inputs
from apps.ares.ares.data.factory import create_repository_for_profile
from apps.ares.ares.face.mobile_approval import MobileApprovalAdapter
from apps.ares.ares.face.operator_shell import build_operator_shell, render_operator_shell
from apps.ares.ares.hardening import (
    append_runtime_error_event,
    build_runtime_health_snapshot,
    ensure_private_directory,
    redact_mapping,
    write_private_json,
    write_private_text,
)
from apps.ares.ares.orchestrator.router import AresRouter
from apps.ares.ares.paths import client_root, get_ares_home, normalize_client_slug
from apps.ares.ares.profiles import ClientProfile, load_client_profile
from apps.ares.ares.reports.renderer import render_daily_brief
from apps.ares.ares.data.models import WorkflowRun
from apps.ares.ares.workflows.daily_brief import run_daily_brief

router = APIRouter()


LOCAL_AUDIT = {
    "local_only": True,
    "approval_first": True,
    "live_external_api_called": False,
    "limitation": "Local Ares command center only; live integrations and hosted SaaS controls are not invoked.",
}


class RunActionBody(BaseModel):
    client: str
    action: str
    params: dict[str, Any] | None = None


@router.get("/clients")
async def clients() -> dict[str, Any]:
    return {"clients": [_client_summary(profile) for profile in _list_profiles()]}


@router.get("/health")
async def health(client: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        resolved_client = normalize_client_slug(client) if client and client.strip() else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return jsonable_encoder(build_runtime_health_snapshot(client_slug=resolved_client))


@router.get("/overview")
async def overview(client: str | None = Query(default=None)) -> dict[str, Any]:
    profiles = _list_profiles()
    clients_payload = [_client_summary(profile) for profile in profiles]
    profile = _resolve_profile(client, profiles=profiles, required=False)
    if profile is None:
        return jsonable_encoder(
            {
                "clients": clients_payload,
                "selected_client": None,
                "setup_command": 'ares setup --client demo-wholesaler --business-name "Demo Wholesale" --owner-name "Owner"',
                "command_groups": [],
                "primary_commands": [],
                "operator_view": _empty_operator_view(),
                "audit": LOCAL_AUDIT,
            }
        )

    repository = create_repository_for_profile(profile)
    approvals = ApprovalService(
        repository,
        required_actions=set(profile.approval_preferences.required_actions) or None,
    )
    validation = validate_local_inputs(client_id=profile.client_slug)
    shell = build_operator_shell(profile=profile, repository=repository, approvals=approvals)
    daily = run_daily_brief(
        repository,
        approvals,
        client_id=profile.client_slug,
        language=profile.language_preference,
    )
    commands = build_wholesaler_command_library(profile.client_slug)
    root = client_root(profile.client_slug)
    inventory = _data_inventory(profile, repository, approvals, validation)
    work_queue = _work_queue(profile, inventory, validation, commands)
    recent_records = _recent_records(repository)
    command_groups = _annotate_command_groups(group_commands(commands), inventory)
    primary_commands = _annotate_commands(commands, inventory)

    metrics = dict(shell["metrics"])
    metrics.update(
        {
            "input_blockers": len(validation["blocking_errors"]),
            "parseable_exports": validation["parseable_exports"],
            "inbox_messages": validation["inbox_messages"],
            "files_found": validation["exports_found"] + validation["inbox_messages"],
        }
    )

    return jsonable_encoder(
        {
            "clients": clients_payload,
            "selected_client": _client_summary(profile),
            "metrics": metrics,
            "validation": validation,
            "daily_brief": daily,
            "daily_brief_text": render_daily_brief(daily),
            "top_actions": daily.get("top_actions", []),
            "operator_shell": shell,
            "data_inventory": inventory,
            "work_queue": work_queue,
            "recent_records": redact_mapping(recent_records),
            "command_groups": command_groups,
            "primary_commands": primary_commands,
            "operator_surface": _operator_surface(command_groups, primary_commands, inventory, validation),
            "operator_view": _operator_view(
                profile=profile,
                inventory=inventory,
                validation=validation,
                work_queue=work_queue,
                recent_records=recent_records,
                primary_commands=primary_commands,
            ),
            "paths": {
                "client_root": str(root),
                "exports": str(root / "exports"),
                "inbox": str(root / "inbox"),
                "reports": str(root / "reports"),
            },
            "audit": LOCAL_AUDIT,
        }
    )


@router.get("/report")
async def get_report(client: str, path: str) -> dict[str, Any]:
    profile = _resolve_profile(client, required=True)
    assert profile is not None
    try:
        reports_dir = (client_root(profile.client_slug) / "reports").resolve()
        resolved_path = Path(path).resolve()
        if not resolved_path.is_relative_to(reports_dir):
            raise HTTPException(status_code=400, detail="Invalid report path.")
        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail="Report not found.")
        content = resolved_path.read_text(encoding="utf-8")
        return {"name": resolved_path.name, "content": content}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ACTIVE_CONNECTIONS.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ACTIVE_CONNECTIONS.discard(websocket)


@router.post("/run")
async def run_action(body: RunActionBody) -> dict[str, Any]:
    profile = _resolve_profile(body.client, required=True)
    assert profile is not None
    action = _normalize_action(body.action)

    try:
        result = _run_local_action(profile, action, params=body.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        append_runtime_error_event(
            profile.client_slug,
            event_type="ares_dashboard_run_error",
            error=str(exc),
            context={"action": action, "client_id": profile.client_slug},
        )
        raise HTTPException(status_code=500, detail="Ares dashboard action failed") from exc

    report = _save_run_report(profile, action, result["message"], result["payload"])

    await broadcast_update()

    return jsonable_encoder(
        {
            "client_id": profile.client_slug,
            "action": action,
            "message": result["message"],
            "payload": result["payload"],
            "report": report,
            "audit": LOCAL_AUDIT,
        }
    )


def _list_profiles() -> list[ClientProfile]:
    clients_root = get_ares_home() / "clients"
    if not clients_root.exists():
        return []
    profiles: list[ClientProfile] = []
    for profile_path in sorted(clients_root.glob("*/profile.yaml")):
        try:
            profiles.append(load_client_profile(profile_path.parent.name))
        except Exception:
            continue
    return profiles


def _resolve_profile(
    client: str | None,
    *,
    profiles: list[ClientProfile] | None = None,
    required: bool,
) -> ClientProfile | None:
    candidates = profiles if profiles is not None else _list_profiles()
    if client and client.strip():
        try:
            slug = normalize_client_slug(client)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        for profile in candidates:
            if profile.client_slug == slug:
                return profile
        raise HTTPException(status_code=404, detail=f"Ares client not found: {slug}")
    if not candidates:
        if required:
            raise HTTPException(status_code=404, detail="No Ares clients found. Run ares setup first.")
        return None
    return candidates[0]


def _client_summary(profile: ClientProfile) -> dict[str, Any]:
    root = client_root(profile.client_slug)
    return {
        "client_slug": profile.client_slug,
        "business_name": profile.business_name,
        "owner_name": profile.owner_name,
        "language_preference": profile.language_preference,
        "timezone": profile.timezone,
        "connector_status": profile.connector_status.model_dump(mode="json"),
        "paths": {
            "root": str(root),
            "exports": str(root / "exports"),
            "inbox": str(root / "inbox"),
            "reports": str(root / "reports"),
        },
        "file_counts": {
            "exports": _count_files(root / "exports"),
            "inbox": _count_files(root / "inbox"),
            "reports": _count_files(root / "reports"),
        },
    }


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return len([entry for entry in path.iterdir() if entry.is_file() and entry.name != "README.md"])


def _data_inventory(
    profile: ClientProfile,
    repository: Any,
    approvals: ApprovalService,
    validation: dict[str, Any],
) -> dict[str, Any]:
    root = client_root(profile.client_slug)
    invoices = repository.get_invoices()
    outstanding = repository.get_outstanding()
    stock_records = repository.get_stock_records()
    orders = repository.list_orders()
    pending_orders = [order for order in orders if order.status == "pending"]
    low_stock = [record for record in stock_records if record.current_stock <= record.reorder_level]
    reports = _report_files(root / "reports")
    counts = {
        "customers": len(repository.get_customers()),
        "invoices": len(invoices),
        "outstanding_invoices": len(outstanding),
        "stock_records": len(stock_records),
        "low_stock_skus": len(low_stock),
        "orders": len(orders),
        "pending_orders": len(pending_orders),
        "pending_approvals": len(approvals.list_pending_requests()),
        "memories": len(repository.list_memories()),
        "workflow_runs": len(getattr(repository, "workflow_runs", {})),
        "action_logs": len(repository.list_action_logs()),
        "reports": len(reports),
        "export_files": validation["exports_found"],
        "inbox_files": validation["inbox_messages"],
        "parseable_exports": validation["parseable_exports"],
        "input_blockers": len(validation["blocking_errors"]),
    }
    return {
        "counts": counts,
        "has_business_data": any(
            counts[key] > 0
            for key in [
                "customers",
                "invoices",
                "stock_records",
                "orders",
                "pending_approvals",
                "memories",
                "workflow_runs",
                "action_logs",
            ]
        ),
        "has_input_files": counts["export_files"] > 0 or counts["inbox_files"] > 0,
        "reports": reports[:8],
        "data_files": _data_files(root / "data"),
    }


def _report_files(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for item in sorted(path.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        if not item.is_file() or item.name == "README.md":
            continue
        stat = item.stat()
        rows.append({"name": item.name, "path": str(item), "size": stat.st_size, "modified_at": stat.st_mtime})
    return rows


def _data_files(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for item in sorted(path.glob("*.json")):
        if item.name == "ingestion_state.json":
            continue
        rows.append({"name": item.name, "path": str(item), "size": item.stat().st_size})
    return rows


def _work_queue(
    profile: ClientProfile,
    inventory: dict[str, Any],
    validation: dict[str, Any],
    commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts = inventory["counts"]
    command_by_action = {command.get("action"): command for command in commands if command.get("action")}
    queue: list[dict[str, Any]] = []

    def add(status: str, title: str, detail: str, action: str | None, command: str) -> None:
        queue.append(
            {
                "status": status,
                "title": title,
                "detail": detail,
                "action": action,
                "command": command,
            }
        )

    if not inventory["has_business_data"] and not inventory["has_input_files"]:
        add(
            "needs_input",
            "Load real business files",
            "No invoices, stock records, orders, approvals, inbox messages, or exports are loaded for this client.",
            None,
            f"Drop outstanding/stock CSVs into {client_root(profile.client_slug) / 'exports'} and order/payment text into {client_root(profile.client_slug) / 'inbox'}",
        )
        add(
            "ready",
            "Validate intake folders",
            "Run the local preflight after adding files. It will report parseable exports and blocking issues.",
            "validate-inputs",
            command_by_action["validate-inputs"]["command"],
        )
        return queue

    if validation["blocking_errors"]:
        add(
            "blocked",
            "Fix input blockers",
            "; ".join(validation["blocking_errors"][:3]),
            "validate-inputs",
            command_by_action["validate-inputs"]["command"],
        )

    if validation["parseable_exports"] or validation["inbox_messages"]:
        add(
            "ready",
            "Run today's ingestion",
            f"{validation['parseable_exports']} parseable export(s) and {validation['inbox_messages']} inbox message(s) are waiting or available for validation.",
            "today",
            command_by_action["today"]["command"],
        )

    if counts["outstanding_invoices"] > 0:
        add(
            "ready",
            "Work collections",
            f"{counts['outstanding_invoices']} outstanding invoice(s) are in local data.",
            "payment-radar",
            command_by_action["payment-radar"]["command"],
        )

    if counts["low_stock_skus"] > 0:
        add(
            "ready",
            "Review stock risk",
            f"{counts['low_stock_skus']} SKU(s) are at or below reorder level.",
            "stock-radar",
            command_by_action["stock-radar"]["command"],
        )

    if counts["pending_orders"] > 0:
        add(
            "ready",
            "Review pending orders",
            f"{counts['pending_orders']} order(s) are pending dispatch/confirmation.",
            "order-capture",
            command_by_action["order-capture"]["command"],
        )

    if counts["pending_approvals"] > 0:
        add(
            "approval",
            "Clear owner approvals",
            f"{counts['pending_approvals']} approval(s) need owner decision before action.",
            "mobile-approvals",
            command_by_action["mobile-approvals"]["command"],
        )

    if not queue:
        add(
            "clear",
            "No urgent local work",
            "Current local data has no pending approvals, overdue invoices, low stock, or pending orders.",
            "daily-brief",
            command_by_action["daily-brief"]["command"],
        )
    return queue


def _recent_records(repository: Any) -> dict[str, list[dict[str, Any]]]:
    def encode(items: list[Any], limit: int = 5) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in items[:limit]]

    invoices = sorted(repository.get_invoices(), key=lambda item: item.invoice_number, reverse=True)
    stock = sorted(repository.get_stock_records(), key=lambda item: item.last_updated, reverse=True)
    orders = sorted(repository.list_orders(), key=lambda item: item.created_at, reverse=True)
    approvals = sorted(repository.list_approvals(), key=lambda item: item.created_at, reverse=True)
    action_logs = sorted(repository.list_action_logs(), key=lambda item: item.executed_at, reverse=True)
    workflow_runs = sorted(getattr(repository, "workflow_runs", {}).values(), key=lambda item: item.started_at, reverse=True)
    return {
        "invoices": encode(invoices),
        "stock_records": encode(stock),
        "orders": encode(orders),
        "approvals": encode(approvals),
        "action_logs": encode(action_logs),
        "workflow_runs": encode(workflow_runs),
    }


def _annotate_commands(commands: list[dict[str, Any]], inventory: dict[str, Any]) -> list[dict[str, Any]]:
    has_data = inventory["has_business_data"] or inventory["has_input_files"]
    annotated = []
    for command in commands:
        item = dict(command)
        requires_data = bool(item.get("requires_data"))
        item["available"] = not requires_data or has_data
        item["state"] = "ready" if item["available"] else "needs_data"
        annotated.append(item)
    return [command for command in annotated if command.get("primary")]


def _annotate_command_groups(groups: list[dict[str, Any]], inventory: dict[str, Any]) -> list[dict[str, Any]]:
    has_data = inventory["has_business_data"] or inventory["has_input_files"]
    annotated_groups = []
    for group in groups:
        commands = []
        for command in group.get("commands", []):
            item = dict(command)
            requires_data = bool(item.get("requires_data"))
            item["available"] = not requires_data or has_data
            item["state"] = "ready" if item["available"] else "needs_data"
            commands.append(item)
        annotated_groups.append({**group, "commands": commands})
    return annotated_groups


def _operator_surface(
    command_groups: list[dict[str, Any]],
    primary_commands: list[dict[str, Any]],
    inventory: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Describe the dashboard-first operator boundary without exposing secrets."""
    actions = [
        {
            "id": command["id"],
            "label": command["label"],
            "action": command.get("action"),
            "section": command.get("section", "Operator"),
            "available": command.get("available", True),
            "state": command.get("state", "ready"),
            "command": command.get("command"),
        }
        for group in command_groups
        for command in group.get("commands", [])
        if command.get("action")
    ]
    return {
        "access_model": "dashboard_first",
        "operator_home": "/ares",
        "cli_role": "admin_dev_fallback",
        "local_only": True,
        "approval_first": True,
        "live_external_api_called": False,
        "has_loaded_input": bool(inventory["has_business_data"] or inventory["has_input_files"]),
        "blocking_errors": len(validation["blocking_errors"]),
        "primary_action_ids": [command["id"] for command in primary_commands],
        "actions": actions,
    }


def _empty_operator_view() -> dict[str, Any]:
    return {
        "today_summary": {
            "headline": "Set up an Ares workspace",
            "status": "needs_input",
            "detail": "No local client profile is available yet. Create a workspace before running operator workflows.",
            "next_action": None,
        },
        "business_cards": [],
        "proof_items": [],
        "readiness_cards": [
            {
                "id": "local_boundary",
                "label": "Local boundary",
                "status": "ready",
                "tone": "emerald",
                "summary": "The dashboard uses local Ares APIs only.",
                "technical_detail": "live_external_api_called=false",
            }
        ],
        "empty_states": {
            "setup": "Create a client workspace to start running Ares from the dashboard.",
            "reports": "Reports appear after a dashboard action runs.",
            "records": "Business records appear after intake files are loaded.",
        },
    }


def _operator_view(
    *,
    profile: ClientProfile,
    inventory: dict[str, Any],
    validation: dict[str, Any],
    work_queue: list[dict[str, Any]],
    recent_records: dict[str, list[dict[str, Any]]],
    primary_commands: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build display-ready summaries so the browser does not lead with raw payloads."""
    counts = inventory["counts"]
    first_action = next((item for item in work_queue if item.get("action")), None)
    first_item = work_queue[0] if work_queue else None
    if validation["blocking_errors"]:
        headline = "Input blockers need attention"
        status = "blocked"
        detail = validation["blocking_errors"][0]
    elif first_item:
        headline = first_item["title"]
        status = first_item["status"]
        detail = first_item["detail"]
    else:
        headline = "No urgent local work"
        status = "clear"
        detail = "Ares did not find pending approvals, order issues, stock risk, or collection work in local data."

    return {
        "today_summary": {
            "headline": headline,
            "status": status,
            "detail": detail,
            "next_action": _display_action(first_action) if first_action else None,
        },
        "business_cards": _business_cards(counts, validation),
        "proof_items": _proof_items(inventory.get("reports", []), primary_commands),
        "readiness_cards": _readiness_cards(profile, inventory, validation),
        "empty_states": {
            "records": "Load invoices, stock, or orders to see business records here.",
            "reports": "Run any dashboard action to create a proof report.",
            "approvals": "Approval requests appear after Ares drafts owner-gated actions.",
            "intake": f"Add business exports to the local intake folders for {profile.business_name}.",
        },
        "record_summaries": _record_summaries(recent_records),
    }


def _display_action(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "label": item.get("title") or "Run workflow",
        "action": item.get("action"),
        "status": item.get("status", "ready"),
        "summary": item.get("detail", ""),
        "cli_fallback": item.get("command", ""),
    }


def _business_cards(counts: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = len(validation.get("blocking_errors", []))
    cards = [
        {
            "id": "collections",
            "label": "Money to collect",
            "value": counts.get("outstanding_invoices", 0),
            "status": "needs_action" if counts.get("outstanding_invoices", 0) else "clear",
            "tone": "red" if counts.get("outstanding_invoices", 0) else "emerald",
            "summary": "Outstanding invoices in local Ares records.",
            "action": "payment-radar",
        },
        {
            "id": "orders",
            "label": "Orders needing action",
            "value": counts.get("pending_orders", 0),
            "status": "ready" if counts.get("pending_orders", 0) else "clear",
            "tone": "amber" if counts.get("pending_orders", 0) else "emerald",
            "summary": "Pending orders waiting for review or confirmation.",
            "action": "order-capture",
        },
        {
            "id": "stock",
            "label": "Stock risk",
            "value": counts.get("low_stock_skus", 0),
            "status": "needs_action" if counts.get("low_stock_skus", 0) else "healthy",
            "tone": "red" if counts.get("low_stock_skus", 0) else "emerald",
            "summary": "SKUs at or below reorder level.",
            "action": "stock-radar",
        },
        {
            "id": "approvals",
            "label": "Owner approvals",
            "value": counts.get("pending_approvals", 0),
            "status": "approval" if counts.get("pending_approvals", 0) else "clear",
            "tone": "amber" if counts.get("pending_approvals", 0) else "emerald",
            "summary": "Owner decisions required before Ares can proceed.",
            "action": "mobile-approvals",
        },
        {
            "id": "reports",
            "label": "Proof reports",
            "value": counts.get("reports", 0),
            "status": "ready" if counts.get("reports", 0) else "empty",
            "tone": "blue" if counts.get("reports", 0) else "zinc",
            "summary": "Local reports generated by dashboard workflows.",
            "action": None,
        },
        {
            "id": "blockers",
            "label": "Input blockers",
            "value": blockers,
            "status": "blocked" if blockers else "clear",
            "tone": "red" if blockers else "emerald",
            "summary": "Problems found while reading local intake files.",
            "action": "validate-inputs",
        },
    ]
    return cards


def _proof_items(reports: list[dict[str, Any]], primary_commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    action_labels = {command.get("action"): command.get("label") for command in primary_commands}
    items = []
    for report in reports:
        if not str(report.get("name", "")).endswith(".md"):
            continue
        action = _infer_action_from_report_name(report.get("name", ""))
        title = action_labels.get(action) or _humanize_report_name(report.get("name", ""))
        items.append(
            {
                "id": report.get("name"),
                "title": title,
                "status": "created",
                "tone": "blue",
                "action": action,
                "created_at": report.get("modified_at"),
                "summary": "Local proof report generated by Ares.",
                "path": report.get("path"),
                "size": report.get("size", 0),
            }
        )
        if len(items) >= 8:
            break
    return items


def _readiness_cards(
    profile: ClientProfile,
    inventory: dict[str, Any],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    cards = [
        {
            "id": "local_boundary",
            "label": "Local runtime",
            "status": "ready",
            "tone": "emerald",
            "summary": "Dashboard actions run through local Ares APIs only.",
            "technical_detail": "frontend_scope=/api/plugins/ares/*; live_external_api_called=false",
        },
        {
            "id": "approval_boundary",
            "label": "Approval boundary",
            "status": "approval_first",
            "tone": "amber",
            "summary": "Owner-gated actions require approval before execution.",
            "technical_detail": "approval_first=true; no live WhatsApp, GSTN, Tally, or payment execution from React",
        },
        {
            "id": "business_data",
            "label": "Business data",
            "status": "ready" if inventory["has_business_data"] else "needs_input",
            "tone": "emerald" if inventory["has_business_data"] else "amber",
            "summary": "Invoices, stock, orders, approvals, or logs are available." if inventory["has_business_data"] else "No business records are loaded yet.",
            "technical_detail": f"data_files={len(inventory.get('data_files', []))}",
        },
        {
            "id": "intake",
            "label": "Intake folders",
            "status": "blocked" if validation["blocking_errors"] else ("ready" if inventory["has_input_files"] else "empty"),
            "tone": "red" if validation["blocking_errors"] else ("emerald" if inventory["has_input_files"] else "zinc"),
            "summary": (
                f"{len(validation['blocking_errors'])} blocker(s) found."
                if validation["blocking_errors"]
                else f"{validation['exports_found']} export file(s), {validation['inbox_messages']} inbox message(s)."
            ),
            "technical_detail": "; ".join(validation["blocking_errors"][:3]) or "No blocking intake errors.",
        },
    ]
    for name, status in profile.connector_status.model_dump(mode="json").items():
        configured = status == "configured"
        cards.append(
            {
                "id": f"connector_{name}",
                "label": name.replace("_", " ").title(),
                "status": status,
                "tone": "emerald" if configured else "zinc",
                "summary": "Configured in the local profile." if configured else "Not configured for live execution.",
                "technical_detail": f"connector_status.{name}={status}",
            }
        )
    return cards


def _record_summaries(recent_records: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    invoices = []
    for invoice in recent_records.get("invoices", []):
        amount = invoice.get("amount") or 0
        status = invoice.get("status") or "draft"
        invoices.append(
            {
                "id": invoice.get("invoice_number") or invoice.get("id"),
                "party": invoice.get("customer_id") or "Customer",
                "amount": amount,
                "status": status,
                "risk": "overdue" if status == "overdue" else ("open" if status in {"pending", "unpaid"} else "normal"),
                "next_action": "Follow up for payment" if status in {"overdue", "pending", "unpaid"} else "Keep for records",
            }
        )
    orders = []
    for order in recent_records.get("orders", []):
        status = order.get("status") or "pending"
        orders.append(
            {
                "id": order.get("id") or order.get("order_id"),
                "party": order.get("customer_id") or "Customer",
                "amount": order.get("amount") or order.get("total_amount") or 0,
                "status": status,
                "risk": "needs_action" if status == "pending" else "normal",
                "next_action": "Confirm or dispatch" if status == "pending" else "Track normally",
            }
        )
    stock = []
    for item in recent_records.get("stock_records", []):
        current = item.get("current_stock") or 0
        reorder = item.get("reorder_level") or 0
        stock.append(
            {
                "id": item.get("sku") or item.get("item_id") or item.get("item_name"),
                "party": item.get("item_name") or item.get("sku_name") or "Stock item",
                "amount": current,
                "status": "low" if current <= reorder else "healthy",
                "risk": "stockout" if current <= reorder else "normal",
                "next_action": "Plan reorder" if current <= reorder else "No action needed",
            }
        )
    return {"invoices": invoices, "orders": orders, "stock_records": stock}


def _humanize_report_name(name: str) -> str:
    stem = Path(name).stem
    parts = stem.split("-", 1)
    label = parts[1] if len(parts) == 2 and parts[0][:8].isdigit() else stem
    return label.replace("-", " ").replace("_", " ").title()


def _infer_action_from_report_name(name: str) -> str | None:
    stem = Path(name).stem
    known = [
        "validate-inputs",
        "morning-run",
        "daily-brief",
        "payment-radar",
        "stock-radar",
        "order-capture",
        "mobile-approvals",
        "approval-center",
        "prepare-gstr1",
        "autonomous-cycle",
    ]
    for action in known:
        if action in stem:
            return action
    return None


def _normalize_action(action: str) -> str:
    normalized = action.strip().lower().replace("_", "-")
    aliases = {
        "today": "morning-run",
        "payment": "payment-radar",
        "stock": "stock-radar",
        "orders": "order-capture",
        "approvals": "approval-center",
        "mobile": "mobile-approvals",
    }
    return aliases.get(normalized, normalized)


def _run_local_action(
    profile: ClientProfile,
    action: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    params = params or {}
    if action == "morning-run":
        payload = run_morning_run(profile.client_slug)
        return {"payload": payload, "message": f"Morning run complete for {profile.business_name}."}
    if action == "validate-inputs":
        payload = validate_local_inputs(client_id=profile.client_slug)
        if payload["blocking_errors"]:
            message = f"Input check found {len(payload['blocking_errors'])} blocker(s)."
        else:
            message = "Input check passed. No blocking issues found."
        return {"payload": payload, "message": message}
    if action == "mobile-approvals":
        repository = create_repository_for_profile(profile)
        approvals = ApprovalService(
            repository,
            required_actions=set(profile.approval_preferences.required_actions) or None,
        )
        prompt = MobileApprovalAdapter(repository, approvals).render_pending_prompt()
        return {"payload": {"prompt": prompt}, "message": prompt}
    if action == "mobile-reply":
        repository = create_repository_for_profile(profile)
        approvals = ApprovalService(
            repository,
            required_actions=set(profile.approval_preferences.required_actions) or None,
        )
        reply = params.get("reply", "")
        if not reply:
            raise ValueError("Missing 'reply' parameter for mobile-reply action.")
        decided_by = params.get("decided_by", "operator")
        result = MobileApprovalAdapter(repository, approvals).handle_reply(reply, decided_by=decided_by)
        from apps.ares.ares.cli import _owner_reply_message
        return {"payload": result, "message": _owner_reply_message(result)}
    if action == "prepare-gstr1":
        repository = create_repository_for_profile(profile)
        approvals = ApprovalService(
            repository,
            required_actions=set(profile.approval_preferences.required_actions) or None,
        )
        period = params.get("period", "")
        seller_gstin = params.get("seller_gstin", "")
        if not period or not seller_gstin:
            raise ValueError("Missing 'period' or 'seller_gstin' parameter for prepare-gstr1 action.")
        from apps.ares.ares.workflows.gstr1 import prepare_gstr1_return
        result = prepare_gstr1_return(
            repository=repository,
            approvals=approvals,
            client_id=profile.client_slug,
            period=period,
            seller_gstin=seller_gstin,
            requested_by=params.get("requested_by", "operator"),
        )
        from apps.ares.ares.cli import _render_gstr1_summary
        return {"payload": result, "message": _render_gstr1_summary(result)}
    if action == "operator-shell":
        repository = create_repository_for_profile(profile)
        approvals = ApprovalService(
            repository,
            required_actions=set(profile.approval_preferences.required_actions) or None,
        )
        shell = build_operator_shell(profile=profile, repository=repository, approvals=approvals)
        return {"payload": shell, "message": render_operator_shell(shell)}
    if action == "autonomous-cycle":
        payload = run_autonomous_cycle(profile.client_slug)
        return {"payload": payload, "message": payload.get("owner_message", "Ares autonomous cycle complete.")}
    if action in {
        "daily-brief",
        "payment-radar",
        "stock-radar",
        "order-capture",
        "weekly-war-room",
        "approval-center",
    }:
        repository = create_repository_for_profile(profile)
        approvals = ApprovalService(
            repository,
            required_actions=set(profile.approval_preferences.required_actions) or None,
        )
        router_instance = AresRouter(
            repository,
            approvals,
            client_id=profile.client_slug,
            language=profile.language_preference,
        )
        result = router_instance.run_workflow(action)
        _record_workflow_run(repository, profile.client_slug, action, result["payload"])
        return {"payload": result["payload"], "message": result["message"]}
    raise ValueError(f"Unsupported Ares dashboard action: {action}")


def _record_workflow_run(repository: Any, client_id: str, workflow_name: str, outputs: dict[str, Any]) -> None:
    try:
        repository.log_workflow_run(
            WorkflowRun(
                id=f"wf_{uuid4().hex[:12]}",
                workflow_name=workflow_name,
                client_id=client_id,
                status="completed",
                ended_at=datetime.now(timezone.utc),
                outputs=outputs,
            )
        )
    except Exception:
        pass


def _save_run_report(profile: ClientProfile, action: str, message: str, payload: dict[str, Any]) -> dict[str, Any]:
    reports_dir = client_root(profile.client_slug) / "reports"
    ensure_private_directory(reports_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_action = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in action)
    json_path = reports_dir / f"{timestamp}-{safe_action}.json"
    md_path = reports_dir / f"{timestamp}-{safe_action}.md"
    report = {
        "client_id": profile.client_slug,
        "business_name": profile.business_name,
        "action": action,
        "message": message,
        "payload": redact_mapping(payload),
        "audit": LOCAL_AUDIT,
        "created_at": timestamp,
    }
    write_private_json(json_path, jsonable_encoder(report))
    write_private_text(
        md_path,
        "\n".join(
            [
                f"# Ares {action}",
                "",
                f"Client: {profile.business_name} ({profile.client_slug})",
                "",
                "## Result",
                "",
                message,
                "",
                "## Audit",
                "",
                "- local_only: true",
                "- approval_first: true",
                "- live_external_api_called: false",
            ]
        ),
    )
    return {"json_path": str(json_path), "markdown_path": str(md_path)}
