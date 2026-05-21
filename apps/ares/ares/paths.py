"""Filesystem paths for Ares client-isolated state."""

from __future__ import annotations

import os
from pathlib import Path


CLIENT_SUBDIRECTORIES = (
    "memory",
    "data",
    "exports",
    "inbox",
    "reports",
    "approvals",
    "logs",
    "workflows",
    "skills",
)

_SCAFFOLD_FILES = {
    "exports/README.md": "# Ares exports drop\n\nDrop CSV exports here for outstanding/receivables and stock/inventory imports.\nSuggested filenames: `tally_outstanding.csv`, `stock_report.csv`.\n",
    "inbox/README.md": "# Ares inbox drop\n\nDrop forwarded order/customer messages here as `.txt` files. One message per file works best for pilot mode.\n",
    "reports/README.md": "# Ares reports\n\nAres-generated operator summaries and owner-facing report artifacts can be saved here during pilot runs.\n",
}


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


def ensure_client_scaffold(client_slug: str, *, ares_home: Path | None = None) -> Path:
    root = client_root(client_slug, ares_home=ares_home)
    root.mkdir(parents=True, exist_ok=True)
    for subdir in CLIENT_SUBDIRECTORIES:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    for relative_path, content in _SCAFFOLD_FILES.items():
        file_path = root / relative_path
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")
    return root


def normalize_client_slug(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.lower())
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        raise ValueError("client slug cannot be empty")
    return slug

