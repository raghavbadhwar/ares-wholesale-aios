"""Tests for NIC e-invoice IRN, E-Way Bill, and GSTR-1 payload builders."""

from __future__ import annotations

import pytest

from apps.ares.ares.connectors.gstn_sandbox import (
    generate_irn_payload,
    generate_eway_bill_payload,
    generate_gstr1_upload_payload,
    GST_SANDBOX_ADAPTER_LIMITATION,
)

_SELLER_GSTIN = "29ABCDE1234F1ZA"
_BUYER_GSTIN = "27XYZAB9876K1ZP"


def _make_invoice(**overrides):
    base = {
        "invoice_number": "INV-2024-001",
        "date": "01/12/2024",
        "amount": 10000.0,
        "taxable_value": 10000.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "igst_amount": 0.0,
        "cess_amount": 0.0,
        "total_amount": 11800.0,
    }
    base.update(overrides)
    return base


class TestGenerateIrnPayload:
    def test_irn_payload_structure_with_line_items(self):
        invoice = _make_invoice(
            line_items=[
                {"description": "Widget A", "quantity": 10, "unit_price": 500, "taxable_value": 5000, "gst_rate": 18},
                {"description": "Widget B", "quantity": 10, "unit_price": 500, "taxable_value": 5000, "gst_rate": 18},
            ]
        )
        result = generate_irn_payload(invoice, _SELLER_GSTIN, _BUYER_GSTIN)

        assert result["Version"] == "1.1"
        assert "TranDtls" in result
        assert result["DocDtls"]["No"] == "INV-2024-001"
        assert result["DocDtls"]["Dt"] == "01/12/2024"
        assert result["SellerDtls"]["Gstin"] == _SELLER_GSTIN
        assert len(result["ItemList"]) == 2
        assert "AssVal" in result["ValDtls"]

    def test_irn_payload_fallback_single_item_when_no_line_items(self):
        invoice = _make_invoice()  # no line_items key
        result = generate_irn_payload(invoice, _SELLER_GSTIN)

        assert len(result["ItemList"]) == 1
        assert result["ItemList"][0]["SlNo"] == "1"

    def test_irn_seller_state_derived_from_gstin(self):
        result = generate_irn_payload(_make_invoice(), "29ABCDE1234F1ZA")
        assert result["SellerDtls"]["Stcd"] == "29"

    def test_irn_buyer_state_derived_from_gstin(self):
        result = generate_irn_payload(_make_invoice(), _SELLER_GSTIN, _BUYER_GSTIN)
        assert result["BuyerDtls"]["Stcd"] == "27"

    def test_irn_buyer_defaults_to_urp_when_no_gstin(self):
        result = generate_irn_payload(_make_invoice(), _SELLER_GSTIN)
        assert result["BuyerDtls"]["Gstin"] == "URP"

    def test_irn_transaction_type_default(self):
        result = generate_irn_payload(_make_invoice(), _SELLER_GSTIN)
        assert result["TranDtls"]["SupTyp"] == "B2B"

    def test_irn_custom_transaction_type(self):
        result = generate_irn_payload(_make_invoice(), _SELLER_GSTIN, transaction_type="SEZWP")
        assert result["TranDtls"]["SupTyp"] == "SEZWP"


class TestGenerateEwayBillPayload:
    def test_eway_bill_payload_requires_irn(self):
        result = generate_eway_bill_payload(irn="TEST-IRN-12345", invoice=_make_invoice())
        assert result["irn"] == "TEST-IRN-12345"
        assert result["_eway_bill_generated"] is False
        assert result["_nic_api_called"] is False

    def test_eway_bill_includes_distance(self):
        result = generate_eway_bill_payload(irn="IRN-1", invoice=_make_invoice(), distance_km=250)
        assert result["Distance"] == 250

    def test_eway_bill_vehicle_number_from_arg(self):
        result = generate_eway_bill_payload(irn="IRN-1", invoice=_make_invoice(), vehicle_number="KA01AB1234")
        assert result["VehNo"] == "KA01AB1234"

    def test_eway_bill_vehicle_type_is_regular(self):
        result = generate_eway_bill_payload(irn="IRN-1", invoice=_make_invoice())
        assert result["VehType"] == "R"


class TestGenerateGstr1UploadPayload:
    def test_gstr1_upload_payload_splits_b2b_and_b2cs(self):
        invoices = [
            _make_invoice(buyer_gstin="29ABCDE1234F1ZA", invoice_number="B2B-001"),
            _make_invoice(invoice_number="B2CS-001"),  # no buyer_gstin → B2CS
        ]
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=invoices
        )
        assert len(result["b2b"]) == 1
        assert len(result["b2cs"]) == 1

    def test_gstr1_returns_correct_gstin_and_period(self):
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=[]
        )
        assert result["gstin"] == _SELLER_GSTIN
        assert result["fp"] == "032024"
        assert result["b2b"] == []
        assert result["b2cs"] == []

    def test_gstr1_b2b_groups_by_buyer_gstin(self):
        """Multiple invoices for the same buyer should group under one ctin entry."""
        invoices = [
            _make_invoice(buyer_gstin=_BUYER_GSTIN, invoice_number="INV-1"),
            _make_invoice(buyer_gstin=_BUYER_GSTIN, invoice_number="INV-2"),
        ]
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=invoices
        )
        assert len(result["b2b"]) == 1
        assert result["b2b"][0]["ctin"] == _BUYER_GSTIN
        assert len(result["b2b"][0]["inv"]) == 2

    def test_gstr1_b2cs_inter_when_igst_nonzero(self):
        invoices = [_make_invoice(igst_amount=1800.0, cgst_amount=0, sgst_amount=0)]
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=invoices
        )
        assert result["b2cs"][0]["sply_ty"] == "INTER"

    def test_gstr1_b2cs_intra_when_igst_zero(self):
        invoices = [_make_invoice(igst_amount=0, cgst_amount=900, sgst_amount=900)]
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=invoices
        )
        assert result["b2cs"][0]["sply_ty"] == "INTRA"


class TestStatutoryNotPerformedFlags:
    def test_irn_payload_not_filed(self):
        result = generate_irn_payload(_make_invoice(), _SELLER_GSTIN)
        assert result["_statutory_filing_performed"] is False
        assert result["_nic_api_called"] is False
        assert result["_limitation"] == GST_SANDBOX_ADAPTER_LIMITATION

    def test_eway_bill_not_generated(self):
        result = generate_eway_bill_payload(irn="IRN-1", invoice=_make_invoice())
        assert result["_nic_api_called"] is False
        assert result["_eway_bill_generated"] is False
        assert result["_limitation"] == GST_SANDBOX_ADAPTER_LIMITATION

    def test_gstr1_not_filed(self):
        result = generate_gstr1_upload_payload(
            gstin=_SELLER_GSTIN, return_period="032024", invoices=[]
        )
        assert result["_statutory_filing_performed"] is False
        assert result["_gstr1_uploaded"] is False
        assert result["_limitation"] == GST_SANDBOX_ADAPTER_LIMITATION
