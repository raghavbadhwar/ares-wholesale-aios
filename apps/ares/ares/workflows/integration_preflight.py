"""External integration prerequisite preflight for Ares."""

from __future__ import annotations

import os
from typing import Any

INTEGRATION_PREFLIGHT_LIMITATION = (
    "Local integration prerequisite preflight only; no secret values are inspected and no live API or sandbox submission is performed."
)

PROVIDER_REQUIREMENTS = {
    "gstn_nic": [
        "GSTN_SANDBOX_BASE_URL",
        "GSTN_SANDBOX_CLIENT_ID",
        "GSTN_SANDBOX_CLIENT_SECRET",
        "NIC_SANDBOX_BASE_URL",
        "NIC_SANDBOX_CLIENT_ID",
        "NIC_SANDBOX_CLIENT_SECRET",
    ],
    "razorpay": [
        "RAZORPAY_SANDBOX_KEY_ID",
        "RAZORPAY_SANDBOX_KEY_SECRET",
        "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
    ],
    "cashfree": [
        "CASHFREE_SANDBOX_CLIENT_ID",
        "CASHFREE_SANDBOX_CLIENT_SECRET",
        "CASHFREE_SANDBOX_WEBHOOK_SECRET",
    ],
    "phonepe": ["PHONEPE_SANDBOX_MERCHANT_ID", "PHONEPE_SANDBOX_SALT_KEY", "PHONEPE_SANDBOX_SALT_INDEX"],
    "whatsapp_business": [
        "META_WABA_SANDBOX_PHONE_NUMBER_ID",
        "META_WABA_SANDBOX_ACCESS_TOKEN",
        "META_WABA_SANDBOX_VERIFY_TOKEN",
    ],
    "tally_busy": ["TALLY_SANDBOX_BASE_URL", "BUSY_SANDBOX_BASE_URL"],
    "logistics": ["LOGISTICS_SANDBOX_BASE_URL", "LOGISTICS_SANDBOX_API_KEY"],
    "account_aggregator": ["AA_SANDBOX_BASE_URL", "AA_SANDBOX_CLIENT_ID", "AA_SANDBOX_CLIENT_SECRET"],
    "ondc": ["ONDC_SANDBOX_BASE_URL", "ONDC_SANDBOX_SUBSCRIBER_ID", "ONDC_SANDBOX_SIGNING_PRIVATE_KEY"],
    "agmarknet": ["AGMARKNET_SANDBOX_BASE_URL"],
}


def configured_integration_env_names() -> set[str]:
    """Return configured integration env var names without reading values."""
    prefixes = (
        "GSTN",
        "NIC",
        "RAZORPAY",
        "CASHFREE",
        "PHONEPE",
        "META_WABA",
        "TALLY",
        "BUSY",
        "LOGISTICS",
        "AA_",
        "ACCOUNT_AGGREGATOR",
        "ONDC",
        "AGMARKNET",
    )
    return {name for name in os.environ if name.startswith(prefixes)}


def build_integration_prerequisite_preflight(
    *,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmations: set[str] | None = None,
) -> dict[str, Any]:
    """Build a preflight report for live/sandbox adapter hardening prerequisites."""
    env_names = set(configured_env_names if configured_env_names is not None else configured_integration_env_names())
    confirmations = set(safe_test_environment_confirmations or set())
    providers = {
        provider: _provider_status(
            provider=provider,
            required_env_names=required_env_names,
            configured_env_names=env_names,
            safe_test_environment_confirmed=provider in confirmations,
        )
        for provider, required_env_names in PROVIDER_REQUIREMENTS.items()
    }
    ready_count = sum(1 for provider in providers.values() if provider["status"] == "ready_for_sandbox_adapter_tests")
    blocked_count = len(providers) - ready_count
    if blocked_count == 0:
        status = "ready"
    elif ready_count:
        status = "partial_ready"
    else:
        status = "blocked"
    return {
        "mode": "local_preflight",
        "status": status,
        "ready_provider_count": ready_count,
        "blocked_provider_count": blocked_count,
        "providers": providers,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": INTEGRATION_PREFLIGHT_LIMITATION,
        },
    }


def _provider_status(
    *,
    provider: str,
    required_env_names: list[str],
    configured_env_names: set[str],
    safe_test_environment_confirmed: bool,
) -> dict[str, Any]:
    missing = [name for name in required_env_names if name not in configured_env_names]
    if missing:
        status = "missing_credentials"
    elif not safe_test_environment_confirmed:
        status = "needs_safety_confirmation"
    else:
        status = "ready_for_sandbox_adapter_tests"
    return {
        "provider": provider,
        "status": status,
        "required_env_names": list(required_env_names),
        "missing_env_names": missing,
        "safe_test_environment_confirmed": safe_test_environment_confirmed,
        "secret_values_inspected": False,
        "live_api_called": False,
    }
