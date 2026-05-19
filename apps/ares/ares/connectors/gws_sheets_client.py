"""GWS CLI backed Google Sheets client for Ares."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from io import StringIO


class GwsConnectorError(RuntimeError):
    pass


class GwsSheetsClient:
    """Small adapter around the local gws CLI.

    This intentionally stores no credentials. Auth remains in the user's normal
    gws configuration, and Ares can fall back to CSV exports when gws is absent.
    """

    def __init__(self, gws_path: str | None = None) -> None:
        self.gws_path = gws_path or shutil.which("gws") or "/opt/homebrew/bin/gws"

    def _run(self, args: list[str]) -> str:
        if not self.gws_path:
            raise GwsConnectorError("gws CLI not found. Use CSV fallback or install/configure Google Workspace CLI.")
        try:
            completed = subprocess.run(
                [self.gws_path, *args],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise GwsConnectorError(f"gws Sheets command failed; use CSV fallback for MVP: {exc}") from exc
        return completed.stdout

    def read_rows(self, spreadsheet_id: str, tab: str) -> list[dict]:
        out = self._run(["sheets", "values", "get", spreadsheet_id, f"{tab}!A:Z", "--format", "json"])
        try:
            data = json.loads(out or "{}")
        except json.JSONDecodeError:
            return list(csv.DictReader(StringIO(out)))
        values = data.get("values", data if isinstance(data, list) else [])
        if not values:
            return []
        header, *rows = values
        return [dict(zip(header, row)) for row in rows]

    def append_row(self, spreadsheet_id: str, tab: str, row: dict) -> None:
        payload = json.dumps(list(row.values()))
        self._run(["sheets", "values", "append", spreadsheet_id, f"{tab}!A:Z", "--values", payload])
