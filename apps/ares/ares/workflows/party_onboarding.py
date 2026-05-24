"""Local-only GSTIN and PAN validation helpers."""

from __future__ import annotations

import re

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_CHECK_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VALID_GST_STATE_CODES = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
    97,
}
PAN_TYPES = {
    "P": "Individual",
    "F": "Firm",
    "C": "Company",
    "H": "HUF",
    "A": "AOP",
    "T": "Trust",
    "B": "BOI",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
}


def _gstin_checksum_valid(gstin: str) -> bool:
    value = gstin.strip().upper()
    if len(value) != 15:
        return False
    total = 0
    factor = 2
    modulus = 36
    for char in reversed(value[:-1]):
        code_point = GSTIN_CHECK_CHARS.find(char)
        if code_point < 0:
            return False
        product = code_point * factor
        total += (product // modulus) + (product % modulus)
        factor = 1 if factor == 2 else 2
    check_code_point = (modulus - (total % modulus)) % modulus
    return GSTIN_CHECK_CHARS[check_code_point] == value[-1]


def verify_gstin_online(gstin: str) -> dict:
    value = gstin.strip().upper()
    state_code = int(value[:2]) if len(value) >= 2 and value[:2].isdigit() else None
    state_code_valid = state_code in VALID_GST_STATE_CODES if state_code is not None else False
    format_valid = bool(GSTIN_RE.match(value)) and state_code_valid and _gstin_checksum_valid(value)
    return {
        "mode": "local_format_validation",
        "gstin": value,
        "format_valid": format_valid,
        "state_code": state_code,
        "state_code_valid": state_code_valid,
        "api_verified": False,
        "audit": {"gstn_sandbox_called": False},
    }


def verify_party_pan(pan: str) -> dict:
    value = pan.strip().upper()
    format_valid = bool(PAN_RE.match(value))
    taxpayer_type = PAN_TYPES.get(value[3], "Unknown") if format_valid else None
    return {
        "mode": "local_format_validation",
        "pan": value,
        "format_valid": format_valid,
        "taxpayer_type": taxpayer_type,
        "api_verified": False,
        "audit": {"it_sandbox_called": False},
    }
