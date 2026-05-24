"""Stable identifiers for replay-safe contract workflows."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_contract_token(*parts: Any, length: int = 12) -> str:
    normalized = "::".join(_normalize_part(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]


def stable_mapping_token(payload: Any, *, length: int = 12) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:length]


def _normalize_part(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return str(value)
