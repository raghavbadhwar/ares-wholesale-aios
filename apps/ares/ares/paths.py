"""Filesystem paths for Ares client-isolated state."""

from __future__ import annotations

import os
from pathlib import Path


def get_ares_home() -> Path:
    """Return the base Ares state directory.

    Ares intentionally does not reuse Hermes memory directories. Each client
    gets an isolated subtree under this home so data, reports, approvals, and
    memories cannot bleed between pilots.
    """
    override = os.getenv("ARES_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".ares").resolve()


def client_root(client_slug: str, *, ares_home: Path | None = None) -> Path:
    clean = normalize_client_slug(client_slug)
    return (ares_home or get_ares_home()) / "clients" / clean


def normalize_client_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.lower())
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        raise ValueError("client slug cannot be empty")
    return slug

