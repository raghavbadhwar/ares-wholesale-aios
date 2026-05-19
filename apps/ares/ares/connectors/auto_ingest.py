"""Automatic local inbox ingestion for Ares."""

from __future__ import annotations

import json
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.file_ingest import ingest_export_file, ingest_message_file
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.paths import client_root
from apps.ares.ares.workflows.order_capture import capture_order


def _state_path(client_id: str) -> Path:
    return client_root(client_id) / "data" / "ingestion_state.json"


def _load_seen(client_id: str) -> set[str]:
    path = _state_path(client_id)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    return set(data.get("seen_paths", []))


def _save_seen(client_id: str, seen: set[str]) -> None:
    path = _state_path(client_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seen_paths": sorted(seen)}, indent=2), encoding="utf-8")


def process_local_inbox(*, client_id: str, repository: BusinessRepository) -> dict:
    """Scan client exports/inbox folders and ingest new files once.

    Eyes for the MVP:
    - exports/*.csv -> outstanding/stock import based on filename
    - inbox/*.txt -> forwarded message order capture
    """
    root = client_root(client_id)
    seen = _load_seen(client_id)
    approvals = ApprovalService(repository)
    exports_imported = 0
    orders_captured = 0
    errors: list[str] = []

    for path in sorted((root / "exports").glob("*.csv")):
        key = str(path.resolve())
        if key in seen:
            continue
        try:
            ingest_export_file(path, repository)
            exports_imported += 1
            seen.add(key)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    for path in sorted((root / "inbox").glob("*.txt")):
        key = str(path.resolve())
        if key in seen:
            continue
        try:
            event = ingest_message_file(path, client_id=client_id)
            capture_order(event, repository, approvals)
            orders_captured += 1
            seen.add(key)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")

    _save_seen(client_id, seen)
    return {"exports_imported": exports_imported, "orders_captured": orders_captured, "errors": errors}
