"""Client profile schema and loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from apps.ares.ares.paths import client_root, ensure_client_scaffold, normalize_client_slug


class StaffContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str
    phone: str | None = None
    telegram_id: str | None = None


class GoogleWorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_center_sheet_id: str | None = None
    drive_folder_id: str | None = None
    exports_folder_id: str | None = None


class ApprovalPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_actions: list[str] = Field(default_factory=list)
    default_decider: str = "owner"
    batch_approval_allowed: bool = True


class CreditRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_payment_terms_days: int = 30
    default_credit_limit: float | None = None
    hard_stop_overdue_days: int | None = 45


class ConnectorStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    google_sheets: Literal["not_configured", "configured", "disabled"] = "not_configured"
    google_drive: Literal["not_configured", "configured", "disabled"] = "not_configured"
    message_forwarding: Literal["not_configured", "configured", "disabled"] = "not_configured"
    exports: Literal["not_configured", "configured", "disabled"] = "not_configured"
    screenshots: Literal["not_configured", "configured", "disabled"] = "not_configured"


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_slug: str
    business_name: str
    owner_name: str
    language_preference: str = "english_hinglish"
    timezone: str = "Asia/Kolkata"
    staff: list[StaffContact] = Field(default_factory=list)
    google: GoogleWorkspaceConfig = Field(default_factory=GoogleWorkspaceConfig)
    approval_preferences: ApprovalPreferences = Field(default_factory=ApprovalPreferences)
    credit_rules: CreditRules = Field(default_factory=CreditRules)
    report_times: dict[str, str] = Field(default_factory=lambda: {"daily_brief": "09:00"})
    connector_status: ConnectorStatus = Field(default_factory=ConnectorStatus)

    @field_validator("client_slug")
    @classmethod
    def _slug_is_normalized(cls, value: str) -> str:
        normalized = normalize_client_slug(value)
        if normalized != value:
            raise ValueError(f"client_slug must be normalized as {normalized!r}")
        return value


def load_client_profile(client_slug: str, *, ares_home: Path | None = None) -> ClientProfile:
    path = client_root(client_slug, ares_home=ares_home) / "profile.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Ares client profile not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return ClientProfile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Invalid Ares client profile at {path}: {exc}") from exc


def write_client_profile(profile: ClientProfile, *, ares_home: Path | None = None) -> Path:
    root = ensure_client_scaffold(profile.client_slug, ares_home=ares_home)
    path = root / "profile.yaml"
    path.write_text(yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def profile_from_mapping(data: dict[str, Any]) -> ClientProfile:
    return ClientProfile.model_validate(data)

