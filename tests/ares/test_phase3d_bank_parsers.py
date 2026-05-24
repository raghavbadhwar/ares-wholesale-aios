"""Tests for Phase 3D — bank CSV parsers and UPI UTR extraction."""

from __future__ import annotations

import pytest

from apps.ares.ares.workflows.bank_reconciliation import (
    extract_upi_utr,
    parse_hdfc_bank_csv,
    parse_icici_bank_csv,
    parse_sbi_bank_csv,
    parse_axis_bank_csv,
    parse_bank_statement_csv,
    _parse_amount,
    _parse_date_flexible,
)


# ---------------------------------------------------------------------------
# extract_upi_utr
# ---------------------------------------------------------------------------

def test_utr_from_labelled_utr():
    narration = "UPI/123456789012/Payment for invoice"
    result = extract_upi_utr(narration)
    assert result == "123456789012"


def test_utr_from_ref_prefix():
    narration = "REF:ABCDEF123456 Bank transfer"
    result = extract_upi_utr(narration)
    assert result == "ABCDEF123456"


def test_utr_bare_12_digit():
    narration = "NEFT CR 420123456789 SBI"
    result = extract_upi_utr(narration)
    assert result == "420123456789"


def test_utr_none_when_no_match():
    result = extract_upi_utr("Salary credit from company")
    assert result is None


# ---------------------------------------------------------------------------
# _parse_amount
# ---------------------------------------------------------------------------

def test_parse_amount_indian_comma_format():
    assert _parse_amount("1,23,456.78") == 123456.78


def test_parse_amount_simple():
    assert _parse_amount("500.00") == 500.0


def test_parse_amount_negative_brackets():
    assert _parse_amount("(500.00)") == -500.0


def test_parse_amount_zero_string():
    assert _parse_amount("0") == 0.0


def test_parse_amount_empty_returns_zero():
    assert _parse_amount("") == 0.0


# ---------------------------------------------------------------------------
# _parse_date_flexible
# ---------------------------------------------------------------------------

def test_parse_date_dd_mm_yyyy():
    assert _parse_date_flexible("01/01/2024") == "2024-01-01"


def test_parse_date_dd_mon_yyyy():
    assert _parse_date_flexible("15 Jan 2024") == "2024-01-15"


def test_parse_date_iso_passthrough():
    assert _parse_date_flexible("2024-03-20") == "2024-03-20"


# ---------------------------------------------------------------------------
# parse_hdfc_bank_csv
# ---------------------------------------------------------------------------

HDFC_CSV = """Date,Narration,Value Dat,Debit Amount,Credit Amount,Chq/Ref Number,Closing Balance
01/01/2024,UPI-PAYTM-UPI/123456789012/Payment,01/01/2024,,10000.00,123456789012,50000.00
02/01/2024,HDFC BANK ATM WD,02/01/2024,2000.00,,CHQ001,48000.00
"""


def test_parse_hdfc_returns_entries():
    entries = parse_hdfc_bank_csv(HDFC_CSV)
    assert len(entries) == 2


def test_parse_hdfc_credit_entry():
    entries = parse_hdfc_bank_csv(HDFC_CSV)
    credit_entries = [e for e in entries if e["direction"] == "credit"]
    assert len(credit_entries) == 1
    assert credit_entries[0]["amount"] == 10000.0


def test_parse_hdfc_debit_entry():
    entries = parse_hdfc_bank_csv(HDFC_CSV)
    debit_entries = [e for e in entries if e["direction"] == "debit"]
    assert len(debit_entries) == 1
    assert debit_entries[0]["amount"] == 2000.0


def test_parse_hdfc_bank_tag():
    entries = parse_hdfc_bank_csv(HDFC_CSV)
    assert all(e["bank"] == "hdfc" for e in entries)


def test_parse_hdfc_utr_extracted():
    entries = parse_hdfc_bank_csv(HDFC_CSV)
    credit_entry = next(e for e in entries if e["direction"] == "credit")
    assert credit_entry["reference"] == "123456789012"


# ---------------------------------------------------------------------------
# parse_icici_bank_csv
# ---------------------------------------------------------------------------

ICICI_CSV = """Transaction Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance
03/01/2024,03/01/2024,UPI/REF:ABCDEF123456/Customer payment,ABCDEF123456,,25000.00,75000.00
04/01/2024,04/01/2024,NEFT DR Supplier payment,NEFT001,15000.00,,60000.00
"""


def test_parse_icici_returns_entries():
    entries = parse_icici_bank_csv(ICICI_CSV)
    assert len(entries) == 2


def test_parse_icici_amounts():
    entries = parse_icici_bank_csv(ICICI_CSV)
    amounts = {e["direction"]: e["amount"] for e in entries}
    assert amounts["credit"] == 25000.0
    assert amounts["debit"] == 15000.0


# ---------------------------------------------------------------------------
# parse_sbi_bank_csv
# ---------------------------------------------------------------------------

SBI_CSV = """Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance
05/01/2024,05/01/2024,UPI Credit from customer,REF123456789012,,5000.00,55000.00
06/01/2024,06/01/2024,Bill payment debit,BILL001,1500.00,,53500.00
"""


def test_parse_sbi_returns_entries():
    entries = parse_sbi_bank_csv(SBI_CSV)
    assert len(entries) == 2


def test_parse_sbi_bank_tag():
    entries = parse_sbi_bank_csv(SBI_CSV)
    assert all(e["bank"] == "sbi" for e in entries)


# ---------------------------------------------------------------------------
# parse_axis_bank_csv
# ---------------------------------------------------------------------------

AXIS_CSV = """Tran Date,CHQNO,Particulars,DR,CR,BAL
07/01/2024,CHQ001,Cash deposit,, 8000.00,63500.00
08/01/2024,CHQ002,Cheque payment,3000.00,,60500.00
"""


def test_parse_axis_returns_entries():
    entries = parse_axis_bank_csv(AXIS_CSV)
    assert len(entries) == 2


def test_parse_axis_bank_tag():
    entries = parse_axis_bank_csv(AXIS_CSV)
    assert all(e["bank"] == "axis" for e in entries)


# ---------------------------------------------------------------------------
# parse_bank_statement_csv — auto-detection
# ---------------------------------------------------------------------------

def test_auto_detect_hdfc():
    result = parse_bank_statement_csv(HDFC_CSV)
    assert result["bank"] == "hdfc"
    assert result["rows_parsed"] == 2


def test_auto_detect_icici():
    result = parse_bank_statement_csv(ICICI_CSV)
    assert result["bank"] == "icici"
    assert result["rows_parsed"] == 2


def test_auto_detect_sbi():
    result = parse_bank_statement_csv(SBI_CSV)
    assert result["bank"] == "sbi"
    assert result["rows_parsed"] == 2


def test_auto_detect_axis():
    result = parse_bank_statement_csv(AXIS_CSV)
    assert result["bank"] == "axis"
    assert result["rows_parsed"] == 2


def test_unsupported_bank_returns_error():
    result = parse_bank_statement_csv("Col1,Col2,Col3\n1,2,3", bank="unknown")
    assert "error" in result
    assert result["rows_parsed"] == 0


def test_bank_override_works():
    result = parse_bank_statement_csv(HDFC_CSV, bank="hdfc")
    assert result["bank"] == "hdfc"
    assert result["rows_parsed"] > 0


def test_limitation_always_present_local_mode():
    result = parse_bank_statement_csv(HDFC_CSV)
    assert "limitation" in result
