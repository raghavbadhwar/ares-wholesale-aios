"""Local bank statement parsers for Ares reconciliation."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

UTR_PATTERNS = (
    re.compile(r"UPI/([A-Z0-9]{6,20})", re.IGNORECASE),
    re.compile(r"REF:([A-Z0-9]{6,20})", re.IGNORECASE),
    re.compile(r"\b(\d{12})\b"),
)


def extract_upi_utr(narration: str) -> str | None:
    for pattern in UTR_PATTERNS:
        match = pattern.search(narration or "")
        if match:
            return match.group(1)
    return None


def _parse_amount(value: str | int | float | None) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "")
    amount = float(text or 0)
    return -amount if negative else amount


def _parse_date_flexible(value: str) -> str:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text


def _rows(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text.strip())))


def _entry(*, bank: str, date: str, narration: str, debit: str, credit: str, reference: str, balance: str) -> dict:
    debit_amount = _parse_amount(debit)
    credit_amount = _parse_amount(credit)
    direction = "credit" if credit_amount > 0 else "debit"
    amount = credit_amount if direction == "credit" else debit_amount
    return {
        "bank": bank,
        "date": _parse_date_flexible(date),
        "narration": narration,
        "direction": direction,
        "amount": amount,
        "reference": extract_upi_utr(narration) or reference,
        "balance": _parse_amount(balance),
    }


def parse_hdfc_bank_csv(csv_text: str) -> list[dict]:
    return [
        _entry(
            bank="hdfc",
            date=row.get("Date", ""),
            narration=row.get("Narration", ""),
            debit=row.get("Debit Amount", ""),
            credit=row.get("Credit Amount", ""),
            reference=row.get("Chq/Ref Number", ""),
            balance=row.get("Closing Balance", ""),
        )
        for row in _rows(csv_text)
    ]


def parse_icici_bank_csv(csv_text: str) -> list[dict]:
    return [
        _entry(
            bank="icici",
            date=row.get("Transaction Date", ""),
            narration=row.get("Description", ""),
            debit=row.get("Debit", ""),
            credit=row.get("Credit", ""),
            reference=row.get("Ref No./Cheque No.", ""),
            balance=row.get("Balance", ""),
        )
        for row in _rows(csv_text)
    ]


def parse_sbi_bank_csv(csv_text: str) -> list[dict]:
    return [
        _entry(
            bank="sbi",
            date=row.get("Txn Date", ""),
            narration=row.get("Description", ""),
            debit=row.get("Debit", ""),
            credit=row.get("Credit", ""),
            reference=row.get("Ref No./Cheque No.", ""),
            balance=row.get("Balance", ""),
        )
        for row in _rows(csv_text)
    ]


def parse_axis_bank_csv(csv_text: str) -> list[dict]:
    return [
        _entry(
            bank="axis",
            date=row.get("Tran Date", ""),
            narration=row.get("Particulars", ""),
            debit=row.get("DR", ""),
            credit=row.get("CR", ""),
            reference=row.get("CHQNO", ""),
            balance=row.get("BAL", ""),
        )
        for row in _rows(csv_text)
    ]


def parse_bank_statement_csv(csv_text: str, bank: str | None = None) -> dict:
    header = (csv_text.splitlines()[0] if csv_text.strip() else "").lower()
    selected = (bank or "").lower()
    if not selected:
        if "narration" in header:
            selected = "hdfc"
        elif "transaction date" in header:
            selected = "icici"
        elif "txn date" in header:
            selected = "sbi"
        elif "tran date" in header:
            selected = "axis"
    parsers = {
        "hdfc": parse_hdfc_bank_csv,
        "icici": parse_icici_bank_csv,
        "sbi": parse_sbi_bank_csv,
        "axis": parse_axis_bank_csv,
    }
    parser = parsers.get(selected)
    if parser is None:
        return {"bank": selected or "unknown", "rows_parsed": 0, "entries": [], "error": "unsupported_bank", "limitation": "Local parser only; no bank API called."}
    entries = parser(csv_text)
    return {"bank": selected, "rows_parsed": len(entries), "entries": entries, "limitation": "Local parser only; no bank API called."}
