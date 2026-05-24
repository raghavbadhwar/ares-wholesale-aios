"""Repository factory for Ares clients."""

from __future__ import annotations

from apps.ares.ares.connectors.google_sheets import GoogleSheetsRepository
from apps.ares.ares.connectors.gws_sheets_client import GwsSheetsClient
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.paths import client_root
from apps.ares.ares.profiles import ClientProfile


def create_repository_for_profile(profile: ClientProfile) -> BusinessRepository:
    """Return the best configured repository for a client.

    Default pilot mode is local JSON under ~/.ares/clients/<slug>/data.
    If a command-center Google Sheet is configured, the same workflow layer can
    run against the Sheets-backed adapter.
    """
    if profile.connector_status.google_sheets == "configured" and profile.google.command_center_sheet_id:
        return GoogleSheetsRepository(
            client=GwsSheetsClient(),
            spreadsheet_id=profile.google.command_center_sheet_id,
            client_slug=profile.client_slug,
        )
    return JsonClientRepository(client_root(profile.client_slug) / "data")
