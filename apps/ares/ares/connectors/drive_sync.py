"""Google Drive-style sync adapter for Ares pilot ingestion.

The production path can feed this from gws/Drive API. For tests and concierge pilots,
a manifest keeps it deterministic and avoids storing Google credentials in code.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from apps.ares.ares.connectors.auto_ingest import process_local_inbox
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.paths import client_root


def _state_path(client_id: str) -> Path:
    return client_root(client_id) / "data" / "drive_sync_state.json"


def _load_seen(client_id: str) -> set[str]:
    path = _state_path(client_id)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    return set(data.get("seen_file_ids", []))


def _save_seen(client_id: str, seen: set[str]) -> None:
    path = _state_path(client_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seen_file_ids": sorted(seen)}, indent=2), encoding="utf-8")


def sync_drive_manifest(*, client_id: str, manifest_path: Path, repository: BusinessRepository) -> dict:
    """Sync new files from a Drive manifest into local Ares folders and ingest them.

    Manifest format:
    [
      {"id": "drive_file_id", "name": "outstanding.csv", "path": "/downloaded/or/local/path.csv", "kind": "export"},
      {"id": "msg_file_id", "name": "order.txt", "path": "/path/order.txt", "kind": "message"}
    ]
    """
    manifest_path = Path(manifest_path)
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("Drive manifest must be a list")

    root = client_root(client_id)
    exports = root / "exports"
    inbox = root / "inbox"
    exports.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    seen = _load_seen(client_id)
    files_synced = 0
    errors: list[str] = []

    for entry in entries:
        file_id = str(entry.get("id") or entry.get("path") or "")
        if not file_id or file_id in seen:
            continue
        try:
            source = Path(str(entry["path"]))
            name = str(entry.get("name") or source.name)
            kind = str(entry.get("kind") or "export")
            target_dir = inbox if kind == "message" or name.lower().endswith(".txt") else exports
            target = target_dir / name
            shutil.copyfile(source, target)
            seen.add(file_id)
            files_synced += 1
        except Exception as exc:
            errors.append(f"{file_id}: {exc}")

    _save_seen(client_id, seen)
    ingestion = process_local_inbox(client_id=client_id, repository=repository)
    return {"files_synced": files_synced, "ingestion": ingestion, "errors": errors}
