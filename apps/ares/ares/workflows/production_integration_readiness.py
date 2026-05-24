"""Production integration readiness mapping for Ares.

This is a separate production-integration spike artifact. It does not claim
benchmark parity and it does not perform any live or sandbox API traffic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.ares.ares.workflows.integration_preflight import (
    PROVIDER_REQUIREMENTS,
    REQUIRED_EXTERNAL_ARTIFACTS,
    build_integration_prerequisite_preflight,
)

REPORT_LIMITATION = (
    "Repo-grounded production integration readiness report only; no live API call, "
    "sandbox submission, credential inspection, or benchmark parity claim was performed."
)

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class IntegrationArea:
    key: str
    label: str
    current_code_status: str
    provider_scope: tuple[str, ...]
    existing_files: tuple[str, ...]
    existing_tests: tuple[str, ...]
    missing_files: tuple[str, ...]
    required_env_names_in_repo: tuple[str, ...]
    missing_env_contracts: tuple[str, ...]
    approval_boundaries: tuple[str, ...]
    adapter_contracts: tuple[str, ...]
    blockers: tuple[str, ...]
    recommended_next_step: str
    recommended_order: int
    benchmark_rows: tuple[str, ...]
    sandbox_ready_allowed: bool = True


INTEGRATION_AREAS = (
    IntegrationArea(
        key="whatsapp_business",
        label="WhatsApp Business sandbox / Meta Cloud API",
        current_code_status="local",
        provider_scope=("whatsapp_business",),
        existing_files=(
            "apps/ares/ares/workflows/whatsapp_business.py",
            "apps/ares/ares/connectors/message_ingest.py",
            "apps/ares/ares/connectors/whatsapp_sandbox.py",
            "apps/ares/ares/execution/actions.py",
        ),
        existing_tests=(
            "tests/ares/test_whatsapp_business_contract.py",
            "tests/ares/test_whatsapp_sandbox_adapter.py",
            "tests/ares/test_whatsapp_sandbox_ingest.py",
        ),
        missing_files=(),
        required_env_names_in_repo=tuple(PROVIDER_REQUIREMENTS["whatsapp_business"]),
        missing_env_contracts=(
            "META_WABA_SANDBOX_APP_SECRET",
            "META_WABA_SANDBOX_BUSINESS_ACCOUNT_ID",
        ),
        approval_boundaries=(
            "ApprovalService action `send_whatsapp_business_message` must stay owner-approved before outbound dispatch.",
            "Webhook verification must be enforced before any inbound status or message mutation is trusted.",
            "Template registration and first live send require operator confirmation that the tenant is non-production.",
        ),
        adapter_contracts=(
            "Replace forwarded-text ingestion with Meta webhook payload ingestion while preserving approval-first owner messaging.",
            "Preserve `record_whatsapp_delivery_receipt(...)` as the audit sink for provider delivery states.",
        ),
        blockers=(
            "Current WhatsApp sandbox adapter is local-only and does not register or receive a live Meta webhook.",
            "Repo env contract still omits sandbox app-secret and business-account wiring from the primary provider contract.",
            "No template registration transcript or provider-authenticated message evidence is stored in repo for a WhatsApp sandbox path.",
        ),
        recommended_next_step=(
            "Pair the local WhatsApp sandbox metadata bundle path with template-registration or provider-authenticated message evidence before claiming any wider readiness."
        ),
        recommended_order=1,
        benchmark_rows=(
            "WhatsApp Business Integration",
            "Automated Communication Workflows",
            "WhatsApp Order Parsing",
        ),
    ),
    IntegrationArea(
        key="payment_gateway",
        label="UPI / payment gateway webhook integration",
        current_code_status="local",
        provider_scope=("razorpay", "cashfree", "phonepe"),
        existing_files=(
            "apps/ares/ares/connectors/payment_gateway_sandbox.py",
            "apps/ares/ares/workflows/payment_gateway.py",
            "apps/ares/ares/workflows/payment_reconciliation.py",
            "apps/ares/ares/workflows/payment_match.py",
        ),
        existing_tests=(
            "tests/ares/test_payment_gateway_contract.py",
            "tests/ares/test_payment_gateway_sandbox.py",
            "tests/ares/test_payment_reconciliation.py",
            "tests/ares/test_integration_preflight.py",
        ),
        missing_files=(),
        required_env_names_in_repo=tuple(
            PROVIDER_REQUIREMENTS["razorpay"]
            + PROVIDER_REQUIREMENTS["cashfree"]
            + PROVIDER_REQUIREMENTS["phonepe"]
        ),
        missing_env_contracts=(),
        approval_boundaries=(
            "ApprovalService action `create_payment_gateway_link` must remain owner-approved for customer-facing payment requests.",
            "Ambiguous receipt matching must continue through approval-gated reconciliation review before invoice settlement is final.",
            "Webhook signature validation must pass before payment receipts are ingested into books.",
        ),
        adapter_contracts=(
            "Map provider webhooks into `ingest_payment_gateway_webhook_contract(...)` shape without bypassing reconciliation audit fields.",
            "Keep payment-provider selection explicit; one provider should be chosen first instead of wiring all three in parallel.",
        ),
        blockers=(
            "Current payment gateway sandbox adapter is local-only and currently normalizes Razorpay, Cashfree, and PhonePe webhook payloads only.",
            "No provider-authenticated payment sandbox proof artifact is stored in repo.",
        ),
        recommended_next_step=(
            "Pair the local payment sandbox metadata bundle path with provider-authenticated payment evidence before claiming any wider readiness."
        ),
        recommended_order=2,
        benchmark_rows=(
            "UPI Payment Reconciliation",
            "UPI & Payment Gateway",
        ),
    ),
    IntegrationArea(
        key="tally_busy",
        label="Tally / Busy sync bridge",
        current_code_status="local",
        provider_scope=("tally_busy",),
        existing_files=(
            "apps/ares/ares/workflows/accounting_sync.py",
            "apps/ares/ares/connectors/tally_sync_adapter.py",
        ),
        existing_tests=(
            "tests/ares/test_accounting_sync_contract.py",
            "tests/ares/test_tally_sync_adapter.py",
        ),
        missing_files=(),
        required_env_names_in_repo=(
            "TALLY_SANDBOX_BASE_URL",
            "BUSY_SANDBOX_BASE_URL",
            "TALLY_BUSY_SANDBOX_SYSTEM",
            "TALLY_BUSY_SANDBOX_COMPANY_NAME",
            "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
            "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
            "TALLY_BUSY_SANDBOX_ODBC_DSN",
        ),
        missing_env_contracts=(),
        approval_boundaries=(
            "ApprovalService action `export_accounting_sync` must stay accountant- or owner-approved before any ledger push/import run.",
            "Import receipts should remain audit-only until one-way export and reconciliation proof is stable.",
        ),
        adapter_contracts=(
            "Map local accounting export payloads into Tally XML or Busy import requests without mutating workflow-level payload contracts.",
            "Keep status receipt import audit-only until a real desktop or sandbox bridge is validated.",
        ),
        blockers=(
            "Current Tally/Busy bridge adapter and execution harness are local-only and do not execute live ODBC/XML sessions.",
            "No provider-authenticated sync proof artifact or CA-reviewed close proof is stored in repo for a Tally/Busy path.",
        ),
        recommended_next_step=(
            "Pair the local Tally/Busy metadata bundle path with provider-authenticated sync evidence or CA-reviewed close evidence before any readiness claim."
        ),
        recommended_order=3,
        benchmark_rows=("Tally / Busy Sync",),
        sandbox_ready_allowed=False,
    ),
    IntegrationArea(
        key="gstn_gsp",
        label="GSTN or GSP sandbox integration",
        current_code_status="local",
        provider_scope=("gstn_nic", "gsp_sandbox"),
        existing_files=(
            "apps/ares/ares/connectors/gstn_sandbox.py",
            "apps/ares/ares/connectors/gsp_sandbox.py",
            "apps/ares/ares/workflows/gstn_api.py",
            "apps/ares/ares/workflows/gst_invoice.py",
            "apps/ares/ares/workflows/gstr1.py",
            "apps/ares/ares/workflows/itc_reconciliation.py",
            "apps/ares/ares/workflows/eway_bill.py",
            "apps/ares/ares/connectors/gstn_sandbox.py",
            "apps/ares/ares/connectors/gsp_sandbox.py",
        ),
        existing_tests=(
            "tests/ares/test_gstn_api_integration_contract.py",
            "tests/ares/test_gst_sandbox_adapter.py",
            "tests/ares/test_gst_invoice.py",
            "tests/ares/test_gstr1_preparation.py",
            "tests/ares/test_itc_reconciliation.py",
            "tests/ares/test_eway_bill_contract.py",
            "tests/ares/test_integration_preflight.py",
        ),
        missing_files=(),
        required_env_names_in_repo=tuple(PROVIDER_REQUIREMENTS["gstn_nic"] + PROVIDER_REQUIREMENTS["gsp_sandbox"]),
        missing_env_contracts=(
            "No repo-defined filing-identity contract exists beyond client-id/client-secret/session-token placeholders.",
        ),
        approval_boundaries=(
            "ApprovalService action `submit_gstn_api_request` must stay accountant-approved before any statutory submission path is enabled.",
            "Invoice, GSTR-1, ITC, and e-way bill workflows must preserve manual accountant fallback on every sandbox failure.",
            "No GSTN/GSP credentials should enter logs, prompts, or client folders unredacted.",
        ),
        adapter_contracts=(
            "Preserve request shaping from `prepare_gstn_api_exchange_contract(...)` and add provider adapters behind that contract.",
            "Do not let sandbox adapters bypass invoice, GSTR-1, ITC, or e-way validation already implemented locally.",
        ),
        blockers=(
            "Current GST sandbox adapters are local-only request/response shapers and do not execute live GSTN, NIC, or GSP traffic.",
            "No provider-authenticated statutory proof artifact is stored in repo for a GST sandbox path.",
            "No filing-identity or operator-login contract exists beyond local credential placeholders.",
        ),
        recommended_next_step=(
            "Pair the local GST sandbox metadata bundle path with explicit filing-identity contracts and provider-authenticated statutory evidence before claiming any wider readiness."
        ),
        recommended_order=4,
        benchmark_rows=(
            "Smart GST Invoicing",
            "GSTR-1 Auto-Preparation",
            "ITC Reconciliation (2A/2B)",
            "E-Way Bill Automation",
            "GSTN API Integration",
        ),
    ),
)


def build_production_integration_readiness_report(
    *,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmations: set[str] | None = None,
) -> dict[str, Any]:
    """Build a repo-grounded production integration readiness report."""
    integrations = {
        area.key: _integration_report_row(
            area=area,
            configured_env_names=configured_env_names,
            safe_test_environment_confirmations=safe_test_environment_confirmations,
        )
        for area in INTEGRATION_AREAS
    }
    return {
        "mode": "local_production_integration_readiness_report",
        "status": _overall_status(integrations),
        "scope": "separate_production_integration_spike",
        "benchmark_parity_claimed": False,
        "integrations": integrations,
        "recommended_implementation_order": [
            {
                "order": area.recommended_order,
                "integration": area.label,
                "key": area.key,
                "reason": _order_reason(area.key),
            }
            for area in sorted(INTEGRATION_AREAS, key=lambda item: item.recommended_order)
        ],
        "audit": {
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "secret_values_inspected": False,
            "limitation": REPORT_LIMITATION,
        },
    }


def _integration_report_row(
    *,
    area: IntegrationArea,
    configured_env_names: set[str] | None,
    safe_test_environment_confirmations: set[str] | None,
) -> dict[str, Any]:
    selected_confirmations = set(safe_test_environment_confirmations or set()).intersection(area.provider_scope)
    preflight = build_integration_prerequisite_preflight(
        configured_env_names=configured_env_names,
        safe_test_environment_confirmations=selected_confirmations,
        selected_providers=set(area.provider_scope),
    )
    existing_files = [_path_presence(path) for path in area.existing_files]
    existing_tests = [_path_presence(path) for path in area.existing_tests]
    missing_files = [_path_presence(path) for path in area.missing_files]
    return {
        "label": area.label,
        "current_code_status": area.current_code_status,
        "production_readiness_status": _production_status(
            preflight=preflight,
            missing_files=missing_files,
            missing_env_contracts=area.missing_env_contracts,
            sandbox_ready_allowed=area.sandbox_ready_allowed,
        ),
        "provider_scope": list(area.provider_scope),
        "benchmark_rows": list(area.benchmark_rows),
        "existing_files": existing_files,
        "existing_tests": existing_tests,
        "missing_files": missing_files,
        "required_env_names_in_repo": list(area.required_env_names_in_repo),
        "missing_env_contracts": list(area.missing_env_contracts),
        "approval_boundaries": list(area.approval_boundaries),
        "adapter_contracts": list(area.adapter_contracts),
        "required_external_artifacts": list(REQUIRED_EXTERNAL_ARTIFACTS),
        "provider_preflight": preflight,
        "blockers": list(area.blockers) + _missing_path_blockers(missing_files),
        "recommended_next_step": area.recommended_next_step,
    }


def _path_presence(path: str) -> dict[str, Any]:
    absolute = REPO_ROOT / path
    return {
        "path": path,
        "exists": absolute.exists(),
    }


def _missing_path_blockers(path_rows: list[dict[str, Any]]) -> list[str]:
    blockers = []
    for row in path_rows:
        if not row["exists"]:
            blockers.append(f"missing adapter module or scaffold: {row['path']}")
    return blockers


def _production_status(
    *,
    preflight: dict[str, Any],
    missing_files: list[dict[str, Any]],
    missing_env_contracts: tuple[str, ...],
    sandbox_ready_allowed: bool,
) -> str:
    if any(not row["exists"] for row in missing_files):
        return "live_blocked"
    if missing_env_contracts:
        return "live_blocked"
    if preflight["status"] == "ready" and sandbox_ready_allowed:
        return "sandbox_ready"
    return "live_blocked"


def _overall_status(integrations: dict[str, dict[str, Any]]) -> str:
    statuses = {payload["production_readiness_status"] for payload in integrations.values()}
    if statuses == {"sandbox_ready"}:
        return "sandbox_ready"
    return "live_blocked"


def _order_reason(key: str) -> str:
    reasons = {
        "whatsapp_business": (
            "Ares is WhatsApp-first, and the current repo still depends on forwarded text plus dry-run dispatch."
        ),
        "payment_gateway": (
            "Webhook-backed payment receipt mapping is narrow, non-destructive, and reuses existing local reconciliation surfaces."
        ),
        "tally_busy": (
            "Accounting sync should follow stabilized message and payment events, starting with one-way export plus audit receipts."
        ),
        "gstn_gsp": (
            "GSTN/GSP has the highest compliance blast radius and should follow accounting-truth hardening plus provider selection."
        ),
    }
    return reasons[key]
