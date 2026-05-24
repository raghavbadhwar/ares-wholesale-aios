"""Local provider-readiness gates for Ares integrations."""

from __future__ import annotations

import os

PROVIDER_REQUIREMENTS = {
    "whatsapp_business": (
        "META_WABA_SANDBOX_PHONE_NUMBER_ID",
        "META_WABA_SANDBOX_ACCESS_TOKEN",
        "META_WABA_SANDBOX_VERIFY_TOKEN",
    ),
    "payment_gateway": ("PAYMENT_GATEWAY_SANDBOX_BASE_URL", "PAYMENT_GATEWAY_SANDBOX_SECRET"),
    "razorpay": ("RAZORPAY_SANDBOX_KEY_ID", "RAZORPAY_SANDBOX_KEY_SECRET", "RAZORPAY_SANDBOX_WEBHOOK_SECRET"),
    "cashfree": ("CASHFREE_SANDBOX_CLIENT_ID", "CASHFREE_SANDBOX_CLIENT_SECRET", "CASHFREE_SANDBOX_WEBHOOK_SECRET"),
    "phonepe": ("PHONEPE_SANDBOX_MERCHANT_ID", "PHONEPE_SANDBOX_SALT_KEY", "PHONEPE_SANDBOX_SALT_INDEX"),
    "gstn": ("GSTN_SANDBOX_BASE_URL", "GSTN_SANDBOX_CLIENT_ID", "GSTN_SANDBOX_CLIENT_SECRET"),
    "gstn_nic": (
        "GSTN_SANDBOX_BASE_URL",
        "GSTN_SANDBOX_CLIENT_ID",
        "GSTN_SANDBOX_CLIENT_SECRET",
        "NIC_SANDBOX_BASE_URL",
        "NIC_SANDBOX_CLIENT_ID",
        "NIC_SANDBOX_CLIENT_SECRET",
    ),
    "gsp_sandbox": ("GSP_SANDBOX_BASE_URL", "GSP_SANDBOX_CLIENT_ID", "GSP_SANDBOX_CLIENT_SECRET", "GSP_SANDBOX_SESSION_TOKEN"),
    "tally_busy": (
        "TALLY_SANDBOX_BASE_URL",
        "BUSY_SANDBOX_BASE_URL",
        "TALLY_BUSY_SANDBOX_SYSTEM",
        "TALLY_BUSY_SANDBOX_COMPANY_NAME",
        "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
        "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
        "TALLY_BUSY_SANDBOX_ODBC_DSN",
    ),
    "supplier_payment": ("SUPPLIER_PAYMENT_SANDBOX_BASE_URL", "SUPPLIER_PAYMENT_SANDBOX_SECRET"),
}

REQUIRED_EXTERNAL_ARTIFACTS = (
    "provider-authenticated sandbox transcript",
    "redacted request and response evidence bundle",
    "operator or accountant review receipt",
    "sandbox tenant confirmation",
)


def configured_integration_env_names() -> list[str]:
    names = sorted({name for values in PROVIDER_REQUIREMENTS.values() for name in values})
    return [name for name in names if os.getenv(name, "").strip()]


def build_integration_preflight(*, configured_env_names: set[str] | None = None) -> dict:
    configured = configured_env_names if configured_env_names is not None else set(configured_integration_env_names())
    providers = []
    for provider, required in PROVIDER_REQUIREMENTS.items():
        missing = [name for name in required if name not in configured]
        providers.append(
            {
                "provider": provider,
                "status": "ready" if not missing else "blocked",
                "required_env_names": list(required),
                "missing_env_names": missing,
                "readiness": "sandbox_ready" if not missing else "live_blocked",
            }
        )
    return {
        "mode": "local_integration_preflight",
        "providers": providers,
        "ready_provider_count": len([item for item in providers if item["status"] == "ready"]),
        "blocked_provider_count": len([item for item in providers if item["status"] == "blocked"]),
        "audit": {"live_provider_called": False},
    }


def build_integration_prerequisite_preflight(
    *,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmations: set[str] | None = None,
    selected_providers: set[str] | None = None,
) -> dict:
    """Check local prerequisite names for a selected provider set without reading secret values."""
    configured = configured_env_names if configured_env_names is not None else set(configured_integration_env_names())
    confirmations = safe_test_environment_confirmations or set()
    providers = sorted(selected_providers or set(PROVIDER_REQUIREMENTS))
    provider_rows = []
    for provider in providers:
        required = PROVIDER_REQUIREMENTS[provider]
        missing = [name for name in required if name not in configured]
        sandbox_confirmed = provider in confirmations
        provider_rows.append(
            {
                "provider": provider,
                "status": "ready" if not missing and sandbox_confirmed else "blocked",
                "required_env_names": list(required),
                "missing_env_names": missing,
                "safe_test_environment_confirmed": sandbox_confirmed,
                "blocked_reasons": _blocked_reasons(provider, missing, sandbox_confirmed),
            }
        )
    blocked_rows = [row for row in provider_rows if row["status"] == "blocked"]
    required_env_names = []
    for provider in providers:
        required_env_names.extend(PROVIDER_REQUIREMENTS[provider])
    return {
        "mode": "local_integration_prerequisite_preflight",
        "status": "ready" if not blocked_rows else "blocked",
        "providers": provider_rows,
        "required_env_names": required_env_names,
        "missing_env_names": sorted({name for row in provider_rows for name in row["missing_env_names"]}),
        "required_external_artifacts": list(REQUIRED_EXTERNAL_ARTIFACTS),
        "audit": {
            "secret_values_inspected": False,
            "live_provider_called": False,
            "sandbox_submission_performed": False,
        },
    }


def _blocked_reasons(provider: str, missing_env_names: list[str], sandbox_confirmed: bool) -> list[str]:
    reasons = []
    if missing_env_names:
        reasons.append(f"missing sandbox environment names for {provider}: {', '.join(missing_env_names)}")
    if not sandbox_confirmed:
        reasons.append(f"safe non-production sandbox tenant not confirmed for {provider}")
    return reasons
