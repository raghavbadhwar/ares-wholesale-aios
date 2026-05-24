"""Local Tally/Busy bridge adapter scaffold for audit-only normalization."""

from __future__ import annotations

from typing import Any

from apps.ares.ares.connectors.proof_handoff import (
    build_external_evidence_bundle,
    build_proof_metadata_manifest,
    build_provider_sandbox_proof_artifact_metadata,
    build_reviewed_external_evidence_intake,
)
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token
from apps.ares.ares.workflows.accounting_sync import LOCAL_SYNC_LIMITATION, normalize_accounting_bridge_payload

TALLY_BRIDGE_ADAPTER_LIMITATION = (
    "Local Tally/Busy bridge adapter scaffold only; no live ODBC query, XML import/export execution, "
    "desktop automation, or company mutation was performed."
)
TALLY_BRIDGE_EXECUTION_HARNESS_LIMITATION = (
    "Local Tally/Busy execution harness only; no live bridge credential was inspected and no Tally or Busy "
    "desktop, XML gateway, or ODBC endpoint was contacted."
)
TALLY_BUSY_PREFLIGHT_ENV_NAMES = [
    "TALLY_SANDBOX_BASE_URL",
    "BUSY_SANDBOX_BASE_URL",
    "TALLY_BUSY_SANDBOX_SYSTEM",
    "TALLY_BUSY_SANDBOX_COMPANY_NAME",
    "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
    "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
    "TALLY_BUSY_SANDBOX_ODBC_DSN",
]


def ingest_tally_bridge_payload(
    *,
    repository: BusinessRepository,
    client_id: str,
    system: str,
    bridge_mode: str,
    payload: Any,
    company_selection: dict[str, Any],
) -> dict[str, Any]:
    """Route a bridge payload into the audit-only accounting sync normalizer."""
    selection = _normalize_company_selection(company_selection)
    normalized = normalize_accounting_bridge_payload(
        repository=repository,
        client_id=client_id,
        system=system,
        bridge_mode=bridge_mode,
        payload=payload,
    )
    return {
        **normalized,
        "company_selection": selection,
        "adapter": {
            "connector": "tally_sync_adapter",
            "bridge_mode_routed": bridge_mode.strip().lower(),
            "live_bridge_called": False,
            "company_mutation_performed": False,
            "limitation": TALLY_BRIDGE_ADAPTER_LIMITATION,
            "normalization_limitation": LOCAL_SYNC_LIMITATION,
        },
    }


def build_tally_bridge_execution_harness(
    *,
    system: str,
    bridge_mode: str,
    company_selection: dict[str, Any],
    payload_reference: str,
    configured_env_names: set[str] | None = None,
) -> dict[str, Any]:
    """Build a local execution-harness contract for XML/ODBC bridge routing."""
    import os
    import httpx
    from xml.etree import ElementTree

    normalized_system = system.strip().lower()
    normalized_mode = bridge_mode.strip().lower()
    selection = _normalize_company_selection(company_selection)
    required_env_names = _bridge_required_env_names(normalized_system, normalized_mode)
    configured = configured_env_names or set()
    missing_env_names = [name for name in required_env_names if name not in configured]
    transcript = _proof_safe_transcript(
        system=normalized_system,
        bridge_mode=normalized_mode,
        company_selection=selection,
        payload_reference=payload_reference,
    )
    blocked_reasons: list[str] = []
    if missing_env_names:
        blocked_reasons.append(f"missing bridge environment names: {', '.join(missing_env_names)}")

    system_key = normalized_system.upper()
    gateway_url = os.getenv(f"{system_key}_SANDBOX_XML_GATEWAY_URL") or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    live_response = None
    status = "ready_for_local_execution_harness" if not blocked_reasons else "blocked"

    if gateway_url and not blocked_reasons:
        try:
            # Construct a Tally-compliant XML status request envelope
            request_xml = (
                '<ENVELOPE>\n'
                '  <HEADER>\n'
                '    <VERSION>1</VERSION>\n'
                '    <TALLYREQUEST>Export</TALLYREQUEST>\n'
                '    <TYPE>Data</TYPE>\n'
                '    <ID>Company Details</ID>\n'
                '  </HEADER>\n'
                '  <BODY>\n'
                '    <DESC>\n'
                '      <STATICVARIABLES>\n'
                f'        <SVCOMPANYNAME>{selection["company_name"]}</SVCOMPANYNAME>\n'
                '      </STATICVARIABLES>\n'
                '    </DESC>\n'
                '  </BODY>\n'
                '</ENVELOPE>'
            )
            resp = httpx.post(gateway_url, headers={"Content-Type": "text/xml"}, content=request_xml, timeout=5.0)
            live_called = True
            if resp.status_code == 200:
                # Verify that the response is well-formed XML
                try:
                    ElementTree.fromstring(resp.content)
                    status = "tally_gateway_response_received"
                    live_response = resp.text
                except Exception as xml_err:
                    status = "tally_gateway_response_malformed_xml"
                    live_response = f"Raw response: {resp.text} | XML Parse Error: {str(xml_err)}"
            else:
                status = f"tally_gateway_error_status_{resp.status_code}"
                live_response = resp.text
        except Exception as e:
            status = "tally_gateway_network_error"
            live_response = str(e)

    return {
        "mode": "live_sandbox_active" if live_called and "error" not in status else "local_contract_mock",
        "status": status,
        "system": normalized_system,
        "bridge_mode": normalized_mode,
        "company_selection": selection,
        "required_env_names": required_env_names,
        "missing_env_names": missing_env_names,
        "can_run_local_execution_harness": not blocked_reasons,
        "bridge_route": {
            "connector": "tally_sync_adapter",
            "system": normalized_system,
            "bridge_mode": normalized_mode,
            "transport": "xml_gateway" if normalized_mode == "xml_status_receipt" else "odbc_rowset",
            "company_name": selection["company_name"],
        },
        "proof_transcript": transcript,
        "blocked_reasons": blocked_reasons,
        "live_response": live_response,
        "audit": {
            "live_bridge_called": live_called,
            "credential_values_inspected": False,
            "proof_transcript_captured": True,
            "limitation": None if live_called else TALLY_BRIDGE_EXECUTION_HARNESS_LIMITATION,
        },
    }


def push_invoices_to_tally(
    *,
    invoices: list[dict[str, Any]],
    company_name: str,
    gateway_url: str | None = None,
) -> dict[str, Any]:
    """Push Sales Vouchers to Tally via XML gateway. Falls back to local mock when no gateway is configured."""
    import os
    import httpx
    from xml.etree import ElementTree

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and invoices:
        for inv in invoices:
            date_val = str(inv.get("date") or "").replace("-", "")
            voucher_number = str(inv.get("invoice_number") or inv.get("id") or "")
            party_name = str(inv.get("customer_id") or inv.get("party_name") or "")
            amount = float(inv.get("amount") or 0.0)
            cgst = float(inv.get("cgst_amount") or 0.0)
            sgst = float(inv.get("sgst_amount") or 0.0)
            igst = float(inv.get("igst_amount") or 0.0)
            taxable = float(inv.get("taxable_value") or (amount - cgst - sgst - igst))

            ledger_entries = (
                f"<ALLLEDGERENTRIES.LIST>"
                f"<LEDGERNAME>{party_name}</LEDGERNAME>"
                f"<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>-{amount:.2f}</AMOUNT>"
                f"</ALLLEDGERENTRIES.LIST>"
                f"<ALLLEDGERENTRIES.LIST>"
                f"<LEDGERNAME>Sales</LEDGERNAME>"
                f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>{taxable:.2f}</AMOUNT>"
                f"</ALLLEDGERENTRIES.LIST>"
            )
            if cgst:
                ledger_entries += (
                    f"<ALLLEDGERENTRIES.LIST>"
                    f"<LEDGERNAME>CGST</LEDGERNAME>"
                    f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                    f"<AMOUNT>{cgst:.2f}</AMOUNT>"
                    f"</ALLLEDGERENTRIES.LIST>"
                )
            if sgst:
                ledger_entries += (
                    f"<ALLLEDGERENTRIES.LIST>"
                    f"<LEDGERNAME>SGST</LEDGERNAME>"
                    f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                    f"<AMOUNT>{sgst:.2f}</AMOUNT>"
                    f"</ALLLEDGERENTRIES.LIST>"
                )
            if igst:
                ledger_entries += (
                    f"<ALLLEDGERENTRIES.LIST>"
                    f"<LEDGERNAME>IGST</LEDGERNAME>"
                    f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                    f"<AMOUNT>{igst:.2f}</AMOUNT>"
                    f"</ALLLEDGERENTRIES.LIST>"
                )

            request_xml = (
                "<ENVELOPE>"
                "<HEADER>"
                "<VERSION>1</VERSION>"
                "<TALLYREQUEST>Import Data</TALLYREQUEST>"
                "</HEADER>"
                "<BODY>"
                "<IMPORTDATA>"
                "<REQUESTDESC>"
                "<REPORTNAME>Vouchers</REPORTNAME>"
                f"<STATICVARIABLES><SVCOMPANYNAME>{company_name}</SVCOMPANYNAME></STATICVARIABLES>"
                "</REQUESTDESC>"
                "<REQUESTDATA>"
                "<TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
                f'<VOUCHER ACTION="Create">'
                f"<DATE>{date_val}</DATE>"
                "<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>"
                f"<VOUCHERNUMBER>{voucher_number}</VOUCHERNUMBER>"
                f"<PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>"
                f"{ledger_entries}"
                "</VOUCHER>"
                "</TALLYMESSAGE>"
                "</REQUESTDATA>"
                "</IMPORTDATA>"
                "</BODY>"
                "</ENVELOPE>"
            )
            try:
                resp = httpx.post(
                    effective_url,
                    headers={"Content-Type": "text/xml"},
                    content=request_xml,
                    timeout=10.0,
                )
                live_called = True
                if resp.status_code == 200:
                    try:
                        root = ElementTree.fromstring(resp.content)
                        created_el = root.find(".//CREATED")
                        if created_el is not None and created_el.text and int(created_el.text) > 0:
                            pushed_count += 1
                        else:
                            failed_count += 1
                            line_error = root.find(".//LINEERROR")
                            errors.append(
                                f"invoice {voucher_number}: "
                                + (line_error.text if line_error is not None and line_error.text else "unknown tally error")
                            )
                    except Exception as xml_err:
                        failed_count += 1
                        errors.append(f"invoice {voucher_number}: xml parse error — {xml_err}")
                else:
                    failed_count += 1
                    errors.append(f"invoice {voucher_number}: http {resp.status_code}")
            except Exception as net_err:
                live_called = True
                failed_count += 1
                errors.append(f"invoice {voucher_number}: network error — {net_err}")

    mode = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "invoices_submitted": len(invoices),
        "invoices_pushed": pushed_count,
        "invoices_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": pushed_count > 0,
            "credential_values_inspected": False,
        },
    }


def push_payments_to_tally(
    *,
    payments: list[dict[str, Any]],
    company_name: str,
    gateway_url: str | None = None,
) -> dict[str, Any]:
    """Push Receipt Vouchers to Tally via XML gateway. Falls back to local mock when no gateway is configured."""
    import os
    import httpx
    from xml.etree import ElementTree

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and payments:
        for pmt in payments:
            date_val = str(pmt.get("date") or "").replace("-", "")
            voucher_number = str(pmt.get("reference") or pmt.get("id") or "")
            party_name = str(pmt.get("customer_id") or pmt.get("party_name") or "")
            amount = float(pmt.get("amount") or 0.0)
            mode_raw = str(pmt.get("mode") or "Cash").strip()
            # Map payment mode to a Tally bank/cash ledger name
            bank_ledger = "Cash" if mode_raw.lower() == "cash" else "Bank"

            request_xml = (
                "<ENVELOPE>"
                "<HEADER>"
                "<VERSION>1</VERSION>"
                "<TALLYREQUEST>Import Data</TALLYREQUEST>"
                "</HEADER>"
                "<BODY>"
                "<IMPORTDATA>"
                "<REQUESTDESC>"
                "<REPORTNAME>Vouchers</REPORTNAME>"
                f"<STATICVARIABLES><SVCOMPANYNAME>{company_name}</SVCOMPANYNAME></STATICVARIABLES>"
                "</REQUESTDESC>"
                "<REQUESTDATA>"
                "<TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
                f'<VOUCHER ACTION="Create">'
                f"<DATE>{date_val}</DATE>"
                "<VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>"
                f"<VOUCHERNUMBER>{voucher_number}</VOUCHERNUMBER>"
                f"<PARTYLEDGERNAME>{party_name}</PARTYLEDGERNAME>"
                f"<ALLLEDGERENTRIES.LIST>"
                f"<LEDGERNAME>{party_name}</LEDGERNAME>"
                f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>{amount:.2f}</AMOUNT>"
                f"</ALLLEDGERENTRIES.LIST>"
                f"<ALLLEDGERENTRIES.LIST>"
                f"<LEDGERNAME>{bank_ledger}</LEDGERNAME>"
                f"<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
                f"<AMOUNT>-{amount:.2f}</AMOUNT>"
                f"</ALLLEDGERENTRIES.LIST>"
                "</VOUCHER>"
                "</TALLYMESSAGE>"
                "</REQUESTDATA>"
                "</IMPORTDATA>"
                "</BODY>"
                "</ENVELOPE>"
            )
            try:
                resp = httpx.post(
                    effective_url,
                    headers={"Content-Type": "text/xml"},
                    content=request_xml,
                    timeout=10.0,
                )
                live_called = True
                if resp.status_code == 200:
                    try:
                        root = ElementTree.fromstring(resp.content)
                        created_el = root.find(".//CREATED")
                        if created_el is not None and created_el.text and int(created_el.text) > 0:
                            pushed_count += 1
                        else:
                            failed_count += 1
                            line_error = root.find(".//LINEERROR")
                            errors.append(
                                f"payment {voucher_number}: "
                                + (line_error.text if line_error is not None and line_error.text else "unknown tally error")
                            )
                    except Exception as xml_err:
                        failed_count += 1
                        errors.append(f"payment {voucher_number}: xml parse error — {xml_err}")
                else:
                    failed_count += 1
                    errors.append(f"payment {voucher_number}: http {resp.status_code}")
            except Exception as net_err:
                live_called = True
                failed_count += 1
                errors.append(f"payment {voucher_number}: network error — {net_err}")

    mode = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "payments_submitted": len(payments),
        "payments_pushed": pushed_count,
        "payments_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": pushed_count > 0,
            "credential_values_inspected": False,
        },
    }


def pull_ledger_from_tally(
    *,
    company_name: str,
    from_date: str,
    to_date: str,
    ledger_name: str = "All Ledgers",
    gateway_url: str | None = None,
) -> dict[str, Any]:
    """Pull ledger vouchers from Tally via XML gateway export. Falls back to local mock when no gateway is configured."""
    import os
    import httpx
    from xml.etree import ElementTree

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    entries: list[dict[str, Any]] = []
    raw_xml_length = 0

    if effective_url:
        from_val = from_date.replace("-", "")
        to_val = to_date.replace("-", "")
        request_xml = (
            "<ENVELOPE>"
            "<HEADER>"
            "<VERSION>1</VERSION>"
            "<TALLYREQUEST>Export Data</TALLYREQUEST>"
            "</HEADER>"
            "<BODY>"
            "<EXPORTDATA>"
            "<REQUESTDESC>"
            "<REPORTNAME>Ledger Vouchers</REPORTNAME>"
            "<STATICVARIABLES>"
            f"<SVCOMPANYNAME>{company_name}</SVCOMPANYNAME>"
            f"<SVFROMDATE>{from_val}</SVFROMDATE>"
            f"<SVTODATE>{to_val}</SVTODATE>"
            f"<LEDGERNAME>{ledger_name}</LEDGERNAME>"
            "</STATICVARIABLES>"
            "</REQUESTDESC>"
            "</EXPORTDATA>"
            "</BODY>"
            "</ENVELOPE>"
        )
        try:
            resp = httpx.post(
                effective_url,
                headers={"Content-Type": "text/xml"},
                content=request_xml,
                timeout=15.0,
            )
            live_called = True
            raw_xml_length = len(resp.content)
            if resp.status_code == 200:
                try:
                    root = ElementTree.fromstring(resp.content)
                    for voucher_el in root.iter("VOUCHER"):
                        entry: dict[str, Any] = {}
                        for child in voucher_el:
                            entry[child.tag.lower()] = child.text
                        entries.append(entry)
                except Exception:
                    # Malformed XML — return empty entries but mark as live
                    pass
        except Exception:
            live_called = True

    mode = "live_tally_pull" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "from_date": from_date,
        "to_date": to_date,
        "ledger_name": ledger_name,
        "entries_pulled": len(entries),
        "entries": entries,
        "raw_xml_length": raw_xml_length,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_pull": live_called,
            "company_mutation_performed": False,
            "credential_values_inspected": False,
        },
    }


def push_stock_items_to_tally(
    *,
    stock_items: list[dict[str, Any]],
    company_name: str,
    gateway_url: str | None = None,
) -> dict[str, Any]:
    """Push StockItem masters to Tally via XML gateway. Falls back to local mock when no gateway is configured."""
    import os
    import httpx
    from xml.etree import ElementTree

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and stock_items:
        for item in stock_items:
            item_name = str(item.get("name") or item.get("sku_id") or "")
            base_units = str(item.get("unit") or "Nos")
            opening_balance = float(item.get("current_stock") or item.get("opening_balance") or 0.0)

            request_xml = (
                "<ENVELOPE>"
                "<HEADER>"
                "<VERSION>1</VERSION>"
                "<TALLYREQUEST>Import Data</TALLYREQUEST>"
                "</HEADER>"
                "<BODY>"
                "<IMPORTDATA>"
                "<REQUESTDESC>"
                "<REPORTNAME>Stock Items</REPORTNAME>"
                f"<STATICVARIABLES><SVCOMPANYNAME>{company_name}</SVCOMPANYNAME></STATICVARIABLES>"
                "</REQUESTDESC>"
                "<REQUESTDATA>"
                "<TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
                f'<STOCKITEM ACTION="Create">'
                f"<NAME>{item_name}</NAME>"
                f"<BASEUNITS>{base_units}</BASEUNITS>"
                f"<OPENINGBALANCE>{opening_balance:.3f}</OPENINGBALANCE>"
                "</STOCKITEM>"
                "</TALLYMESSAGE>"
                "</REQUESTDATA>"
                "</IMPORTDATA>"
                "</BODY>"
                "</ENVELOPE>"
            )
            try:
                resp = httpx.post(
                    effective_url,
                    headers={"Content-Type": "text/xml"},
                    content=request_xml,
                    timeout=10.0,
                )
                live_called = True
                if resp.status_code == 200:
                    try:
                        root = ElementTree.fromstring(resp.content)
                        created_el = root.find(".//CREATED")
                        if created_el is not None and created_el.text and int(created_el.text) > 0:
                            pushed_count += 1
                        else:
                            failed_count += 1
                            line_error = root.find(".//LINEERROR")
                            errors.append(
                                f"item {item_name}: "
                                + (line_error.text if line_error is not None and line_error.text else "unknown tally error")
                            )
                    except Exception as xml_err:
                        failed_count += 1
                        errors.append(f"item {item_name}: xml parse error — {xml_err}")
                else:
                    failed_count += 1
                    errors.append(f"item {item_name}: http {resp.status_code}")
            except Exception as net_err:
                live_called = True
                failed_count += 1
                errors.append(f"item {item_name}: network error — {net_err}")

    mode = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "items_submitted": len(stock_items),
        "items_pushed": pushed_count,
        "items_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": pushed_count > 0,
            "credential_values_inspected": False,
        },
    }


def build_tally_bridge_proof_artifact_metadata(
    *,
    execution_harness: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build proof-safe metadata matching the benchmark proof packet contract."""
    transcript = execution_harness.get("proof_transcript")
    if not isinstance(transcript, dict):
        raise ValueError("execution_harness must include proof_transcript metadata")
    transcript_id = str(transcript.get("transcript_id") or "").strip()
    return build_provider_sandbox_proof_artifact_metadata(
        provider="tally_busy",
        transcript_id=transcript_id,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        artifact_reference_prefix="redacted://tally_busy",
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )


def build_tally_bridge_proof_metadata_manifest(
    *,
    execution_harness: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build an ingestible redacted manifest for Tally/Busy proof review handoff."""
    artifact = build_tally_bridge_proof_artifact_metadata(
        execution_harness=execution_harness,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_proof_metadata_manifest(artifact=artifact, generated_from="tally_sync_adapter")


def build_tally_bridge_external_evidence_bundle(
    *,
    execution_harness: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    reviewer_role: str = "operator_or_accountant_reviewer",
    signer_key_reference: str = "redacted-reviewer-key-1",
    signature_reference: str = "redacted-signature-reference-1",
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
    bundle_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted external-evidence bundle for Tally/Busy proof handoff."""
    artifact = build_tally_bridge_proof_artifact_metadata(
        execution_harness=execution_harness,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_external_evidence_bundle(
        artifact=artifact,
        transcript_id=str(execution_harness["proof_transcript"]["transcript_id"]),
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        reviewer_role=reviewer_role,
        signer_key_reference=signer_key_reference,
        signature_reference=signature_reference,
        bundle_prefix="external-evidence-bundle-tally",
        envelope_prefix="signed-tally-proof",
        snapshot_prefix="registry-snapshot-tally",
        bundle_token_override=bundle_token_override,
    )


def build_tally_bridge_reviewed_evidence_intake(
    *,
    execution_harness: dict[str, Any],
    external_evidence_bundle: dict[str, Any],
    reviewed_at: str,
    reviewer_reference: str,
    operator_login_reference: str = "redacted-tally-operator-login-1",
    operator_session_reference: str = "redacted-tally-session-1",
    review_outcome: str = "metadata_review_complete_not_verified",
    intake_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted reviewed-evidence intake payload for Tally/Busy bridge replay."""
    transcript = execution_harness.get("proof_transcript")
    if not isinstance(transcript, dict):
        raise ValueError("execution_harness must include proof_transcript metadata")
    bridge_route = execution_harness.get("bridge_route")
    bridge_route_mapping = bridge_route if isinstance(bridge_route, dict) else {}
    company_selection = execution_harness.get("company_selection")
    company_selection_mapping = company_selection if isinstance(company_selection, dict) else {}
    system = str(execution_harness.get("system") or "").strip().lower() or "tally_busy"
    return build_reviewed_external_evidence_intake(
        bundle=external_evidence_bundle,
        transcript_id=str(transcript.get("transcript_id") or "").strip(),
        reviewed_at=reviewed_at,
        reviewer_reference=reviewer_reference,
        provider="tally_busy",
        intake_prefix="reviewed-tally-evidence-intake",
        review_outcome=review_outcome,
        intake_token_override=intake_token_override,
        operator_login_metadata={
            "actor_role": "operator_or_accountant",
            "login_reference": operator_login_reference,
            "session_reference": operator_session_reference,
            "login_surface": f"{system}_bridge_console",
            "redaction_confirmed": True,
        },
        subject_metadata_kind="tally_bridge_identity",
        subject_metadata={
            "subject_reference": str(
                company_selection_mapping.get("company_id")
                or company_selection_mapping.get("company_name")
                or "redacted-tally-company"
            ).strip(),
            "subject_scope": str(
                execution_harness.get("bridge_mode")
                or bridge_route_mapping.get("transport")
                or "tally_bridge_review"
            ).strip(),
            "operation": str(
                bridge_route_mapping.get("transport") or "tally_bridge_review"
            ).strip(),
            "portal_reference": str(transcript.get("payload_reference") or "").strip(),
            "redaction_confirmed": True,
        },
    )


def _normalize_company_selection(selection: dict[str, Any]) -> dict[str, Any]:
    company_name = str(selection.get("company_name") or "").strip()
    if not company_name:
        raise ValueError("company_name is required for local Tally/Busy bridge routing")
    return {
        "company_name": company_name,
        "company_id": str(selection.get("company_id") or "").strip() or None,
        "source": str(selection.get("source") or "operator_selected").strip(),
    }


def _bridge_required_env_names(system: str, bridge_mode: str) -> list[str]:
    system_key = system.strip().upper()
    base_names = [
        f"{system_key}_SANDBOX_BASE_URL",
        f"{system_key}_SANDBOX_COMPANY_NAME",
        f"{system_key}_SANDBOX_BRIDGE_MODE",
    ]
    if bridge_mode == "xml_status_receipt":
        return base_names + [f"{system_key}_SANDBOX_XML_GATEWAY_URL"]
    if bridge_mode == "odbc_rowset":
        return base_names + [f"{system_key}_SANDBOX_ODBC_DSN"]
    raise ValueError(f"Unsupported accounting bridge mode: {bridge_mode}")


def _proof_safe_transcript(
    *,
    system: str,
    bridge_mode: str,
    company_selection: dict[str, Any],
    payload_reference: str,
) -> dict[str, Any]:
    transcript_id = f"bridge_txn_{stable_mapping_token({'system': system, 'bridge_mode': bridge_mode, 'company_selection': company_selection, 'payload_reference': payload_reference})}"
    return {
        "transcript_id": transcript_id,
        "payload_reference": payload_reference,
        "proof_safe": True,
        "raw_payload_persisted": False,
        "customer_data_redacted": True,
        "captured_fields": [
            "system",
            "bridge_mode",
            "company_name",
            "payload_reference",
            "normalized_status",
        ],
    }


# ---------------------------------------------------------------------------
# Tally data push / pull functions (Phase 1D)
# ---------------------------------------------------------------------------

def _build_voucher_xml(voucher_type: str, voucher_number: str, date: str, party_name: str,
                        amount: float, mode: str, reference: str, company_name: str) -> str:
    """Build a minimal Tally XML voucher for Sales or Receipt."""
    safe = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<ENVELOPE>"
        "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        "<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>"
        "<REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
        f"<VOUCHER ACTION=\"Create\" OBJVIEW=\"Accounting Voucher View\">"
        f"<DATE>{safe(date)}</DATE>"
        f"<VOUCHERTYPENAME>{safe(voucher_type)}</VOUCHERTYPENAME>"
        f"<VOUCHERNUMBER>{safe(voucher_number)}</VOUCHERNUMBER>"
        f"<NARRATION>{safe(reference)}</NARRATION>"
        f"<PARTYLEDGERNAME>{safe(party_name)}</PARTYLEDGERNAME>"
        f"<ALLLEDGERENTRIES.LIST>"
        f"<LEDGERNAME>{safe(party_name)}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>"
        f"<AMOUNT>{amount:.2f}</AMOUNT>"
        "</ALLLEDGERENTRIES.LIST>"
        f"<ALLLEDGERENTRIES.LIST>"
        f"<LEDGERNAME>{'Sales' if voucher_type == 'Sales' else 'Bank Account'}</LEDGERNAME>"
        f"<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>"
        f"<AMOUNT>{-amount:.2f}</AMOUNT>"
        "</ALLLEDGERENTRIES.LIST>"
        "</VOUCHER>"
        "</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
    )


def _parse_tally_response(xml_text: str) -> tuple[bool, str | None]:
    """Return (success, error_message) from a Tally XML gateway response."""
    try:
        from xml.etree import ElementTree
        root = ElementTree.fromstring(xml_text)
        created = root.findtext(".//CREATED")
        if created and int(created.strip()) > 0:
            return True, None
        error = root.findtext(".//LINEERROR") or root.findtext(".//STATERROR")
        return False, error or "Unknown Tally error"
    except Exception as exc:
        return False, f"XML parse error: {exc}"


def push_invoices_to_tally(
    *,
    invoices: list[dict],
    company_name: str,
    gateway_url: str | None = None,
) -> dict:
    """Push invoice records to Tally as Sales Vouchers via the XML Gateway.

    When TALLY_BUSY_SANDBOX_XML_GATEWAY_URL is set (or gateway_url is provided),
    posts Tally-compatible Sales Voucher XML for each invoice.

    In local mock mode (no gateway URL), returns a contract simulation with
    live_called=False and limitation string.
    """
    import os
    import httpx

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and invoices:
        for inv in invoices:
            voucher_number = str(inv.get("invoice_number") or inv.get("number") or "")
            date = str(inv.get("date") or "")
            party_name = str(inv.get("customer_id") or inv.get("buyer_name") or "")
            amount = float(inv.get("total_amount") or inv.get("amount") or 0)
            xml_body = _build_voucher_xml(
                "Sales", voucher_number, date, party_name, amount,
                "Credit", voucher_number, company_name
            )
            try:
                resp = httpx.post(
                    effective_url,
                    content=xml_body.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                    timeout=10.0,
                )
                live_called = True
                success, err = _parse_tally_response(resp.text)
                if success:
                    pushed_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{voucher_number}: {err}")
            except Exception as exc:
                live_called = True
                failed_count += 1
                errors.append(f"{voucher_number}: {exc}")

    mode = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "invoices_submitted": len(invoices),
        "invoices_pushed": pushed_count,
        "invoices_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": live_called and pushed_count > 0,
            "credential_values_inspected": False,
        },
    }


def push_payments_to_tally(
    *,
    payments: list[dict],
    company_name: str,
    gateway_url: str | None = None,
) -> dict:
    """Push payment receipts to Tally as Receipt Vouchers via the XML Gateway.

    Same dual-mode pattern as push_invoices_to_tally — real HTTP call when
    gateway URL is set, local mock otherwise.
    """
    import os
    import httpx

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and payments:
        for pmt in payments:
            reference = str(pmt.get("reference") or pmt.get("payment_id") or "")
            date = str(pmt.get("date") or "")
            party_name = str(pmt.get("customer_id") or "")
            amount = float(pmt.get("amount") or 0)
            mode = str(pmt.get("mode") or "Bank")
            xml_body = _build_voucher_xml(
                "Receipt", reference, date, party_name, amount, mode, reference, company_name
            )
            try:
                resp = httpx.post(
                    effective_url,
                    content=xml_body.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                    timeout=10.0,
                )
                live_called = True
                success, err = _parse_tally_response(resp.text)
                if success:
                    pushed_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{reference}: {err}")
            except Exception as exc:
                live_called = True
                failed_count += 1
                errors.append(f"{reference}: {exc}")

    mode_str = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode_str,
        "company_name": company_name,
        "payments_submitted": len(payments),
        "payments_pushed": pushed_count,
        "payments_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": live_called and pushed_count > 0,
            "credential_values_inspected": False,
        },
    }


def pull_ledger_from_tally(
    *,
    company_name: str,
    from_date: str,
    to_date: str,
    ledger_name: str = "All Ledgers",
    gateway_url: str | None = None,
) -> dict:
    """Pull ledger vouchers from Tally via the XML Gateway Export API.

    When the gateway URL is set, sends an Export Data request and parses the
    XML response into a list of entry dicts.
    """
    import os
    import httpx

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    entries: list[dict] = []
    raw_xml_length = 0

    if effective_url:
        export_xml = (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>"
            "<BODY><EXPORTDATA><REQUESTDESC>"
            f"<REPORTNAME>Ledger Vouchers</REPORTNAME>"
            f"<STATICVARIABLES>"
            f"<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
            f"<SVFROMDATE>{from_date}</SVFROMDATE>"
            f"<SVTODATE>{to_date}</SVTODATE>"
            f"<SVCOMPANY>{company_name}</SVCOMPANY>"
            "</STATICVARIABLES>"
            "</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"
        )
        try:
            resp = httpx.post(
                effective_url,
                content=export_xml.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
                timeout=30.0,
            )
            live_called = True
            raw_xml = resp.text
            raw_xml_length = len(raw_xml)
            # Try to parse entries from XML
            from xml.etree import ElementTree
            root = ElementTree.fromstring(raw_xml)
            for voucher in root.iter("VOUCHER"):
                entries.append({
                    "date": voucher.findtext("DATE") or "",
                    "voucher_type": voucher.findtext("VOUCHERTYPENAME") or "",
                    "voucher_number": voucher.findtext("VOUCHERNUMBER") or "",
                    "party": voucher.findtext("PARTYLEDGERNAME") or "",
                    "narration": voucher.findtext("NARRATION") or "",
                })
        except Exception:
            live_called = True

    mode = "live_tally_pull" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "from_date": from_date,
        "to_date": to_date,
        "ledger_name": ledger_name,
        "entries_pulled": len(entries),
        "entries": entries,
        "raw_xml_length": raw_xml_length,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_pull": live_called,
            "company_mutation_performed": False,
            "credential_values_inspected": False,
        },
    }


def push_stock_items_to_tally(
    *,
    stock_items: list[dict],
    company_name: str,
    gateway_url: str | None = None,
) -> dict:
    """Push stock item masters to Tally via the XML Gateway.

    Each stock item is created or updated as a Tally StockItem master.
    Same dual-mode pattern as push_invoices_to_tally.
    """
    import os
    import httpx

    def _build_stock_xml(item: dict) -> str:
        safe = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        name = safe(item.get("name") or item.get("sku_code") or "")
        unit = safe(item.get("unit") or "NOS")
        qty = float(item.get("quantity") or item.get("opening_stock") or 0)
        return (
            "<ENVELOPE>"
            "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
            "<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>"
            "<REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">"
            f"<STOCKITEM ACTION=\"Create\" NAME=\"{name}\">"
            f"<NAME>{name}</NAME>"
            f"<BASEUNITS>{unit}</BASEUNITS>"
            f"<OPENINGBALANCE>{qty:.3f} {unit}</OPENINGBALANCE>"
            "</STOCKITEM>"
            "</TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
        )

    effective_url = gateway_url or os.getenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL")
    live_called = False
    pushed_count = 0
    failed_count = 0
    errors: list[str] = []

    if effective_url and stock_items:
        for item in stock_items:
            xml_body = _build_stock_xml(item)
            item_name = str(item.get("name") or item.get("sku_code") or "")
            try:
                resp = httpx.post(
                    effective_url,
                    content=xml_body.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                    timeout=10.0,
                )
                live_called = True
                success, err = _parse_tally_response(resp.text)
                if success:
                    pushed_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{item_name}: {err}")
            except Exception as exc:
                live_called = True
                failed_count += 1
                errors.append(f"{item_name}: {exc}")

    mode = "live_tally_push" if live_called else "local_contract_mock"
    return {
        "mode": mode,
        "company_name": company_name,
        "items_submitted": len(stock_items),
        "items_pushed": pushed_count,
        "items_failed": failed_count,
        "errors": errors,
        "live_called": live_called,
        "limitation": None if live_called else TALLY_BRIDGE_ADAPTER_LIMITATION,
        "audit": {
            "live_tally_push": live_called,
            "company_mutation_performed": live_called and pushed_count > 0,
            "credential_values_inspected": False,
        },
    }

