"""Google Drive folder watcher abstraction for Ares."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apps.ares.ares.connectors.events import new_event
from apps.ares.ares.data.models import IngestedEvent


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str = ""
    modified_time: str = ""
    web_url: str | None = None


class DriveClient(Protocol):
    def list_files(self, folder_id: str) -> list[DriveFile]: ...


class GoogleDriveWatcher:
    def __init__(self, client: DriveClient) -> None:
        self.client = client

    def list_new_files(
        self,
        *,
        client_id: str,
        folder_id: str,
        seen_file_ids: set[str],
    ) -> list[IngestedEvent]:
        events: list[IngestedEvent] = []
        for item in self.client.list_files(folder_id):
            if item.id in seen_file_ids:
                continue
            events.append(
                new_event(
                    source="google_drive",
                    client_id=client_id,
                    file_id=item.id,
                    raw_text=item.name,
                    metadata={
                        "name": item.name,
                        "mime_type": item.mime_type,
                        "modified_time": item.modified_time,
                        "web_url": item.web_url,
                    },
                )
            )
        return events

