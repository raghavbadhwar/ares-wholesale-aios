"""External integration prerequisite preflight for Ares."""

from __future__ import annotations

import os
from typing import Any

INTEGRATION_PREFLIGHT_LIMITATION = (
    "Local integration prerequisite preflight only; no secret values are inspected and no live API or sandbox submission is performed."
)

ALLOWED_SANDBOX_TEST_SCOPE = [
    "instantiate_provider_sandbox_client",
    "validate_local_request_signing_or_payload_shape",
    "run_mock_or_provider_sandbox_health_checks_after_operator_confirmation",
]

FORBIDDEN_TEST_SCOPE = [
    "production submissions",
    "live filings",
    "real payment collection",
    "customer or supplier messaging",
    "secret value printing or persistence",
]

REQUIRED_EXTERNAL_ARTIFACTS = [
    "provider sandbox account or tenant identifier",
    "provider sandbox base URL and API documentation",
    "allowed sandbox test payloads and webhook samples",
    "written confirmation that no production submissions, filings, payments, or messages will be triggered",
]

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

PROVIDER_BENCHMARK_IMPACT = {
    "gstn_nic": {
        "benchmark_feature_rows": [
            "Smart GST Invoicing",
            "GSTR-1 Auto-Preparation",
            "ITC Reconciliation (2A/2B)",
            "E-Way Bill Automation",
            "GSTN API Integration",
        ],
        "production_blockers_addressed": ["live_gstn_nic_integration"],
    },
    "razorpay": {
        "benchmark_feature_rows": ["UPI Payment Reconciliation", "UPI & Payment Gateway"],
        "production_blockers_addressed": ["live_payment_gateway_webhooks"],
    },
    "cashfree": {
        "benchmark_feature_rows": ["UPI Payment Reconciliation", "UPI & Payment Gateway"],
        "production_blockers_addressed": ["live_payment_gateway_webhooks"],
    },
    "phonepe": {
        "benchmark_feature_rows": ["UPI Payment Reconciliation", "UPI & Payment Gateway"],
        "production_blockers_addressed": ["live_payment_gateway_webhooks"],
    },
    "whatsapp_business": {
        "benchmark_feature_rows": ["WhatsApp Business Integration", "Automated Communication Workflows"],
        "production_blockers_addressed": ["live_whatsapp_business_api"],
    },
    "tally_busy": {
        "benchmark_feature_rows": ["Tally / Busy Sync"],
        "production_blockers_addressed": ["live_tally_busy_bidirectional_sync"],
    },
    "logistics": {
        "benchmark_feature_rows": ["Logistics Integration"],
        "production_blockers_addressed": [],
    },
    "account_aggregator": {
        "benchmark_feature_rows": ["Account Aggregator / AA", "Credit Scoring per Party"],
        "production_blockers_addressed": ["live_bank_account_aggregator_data"],
    },
    "ondc": {
        "benchmark_feature_rows": ["ONDC Seller Node"],
        "production_blockers_addressed": [],
    },
    "agmarknet": {
        "benchmark_feature_rows": ["Mandi Price Integration"],
        "production_blockers_addressed": [],
    },
}


def build_integration_env_template(*, selected_providers: set[str] | None = None) -> dict[str, Any]:
    """Build a dotenv-style sandbox env template without reading or including values."""
    provider_scope = _provider_scope(selected_providers)
    providers = {
        provider: {
            "provider": provider,
            "env_names": list(required_env_names),
            "env_template_lines": [f"# {provider} sandbox integration"]
            + [f"{env_name}=" for env_name in required_env_names],
            "values_included": False,
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
        }
        for provider, required_env_names in provider_scope.items()
    }
    return {
        "mode": "local_preflight_env_template",
        "provider_scope": list(provider_scope),
        "format": "dotenv",
        "provider_count": len(providers),
        "providers": providers,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": INTEGRATION_PREFLIGHT_LIMITATION,
        },
    }


def build_integration_readiness_packet(
    *,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmations: set[str] | None = None,
    selected_providers: set[str] | None = None,
) -> dict[str, Any]:
    """Build a provider handoff packet for sandbox adapter hardening readiness."""
    preflight = build_integration_prerequisite_preflight(
        configured_env_names=configured_env_names,
        safe_test_environment_confirmations=safe_test_environment_confirmations,
        selected_providers=selected_providers,
    )
    catalog = build_integration_provider_catalog(selected_providers=selected_providers)
    providers = {
        provider: _readiness_packet_provider(
            provider=provider,
            status=preflight["providers"][provider],
            catalog=catalog["providers"][provider],
        )
        for provider in preflight["providers"]
    }
    return {
        "mode": "local_preflight_readiness_packet",
        "status": preflight["status"],
        "provider_scope": preflight["provider_scope"],
        "ready_provider_count": preflight["ready_provider_count"],
        "blocked_provider_count": preflight["blocked_provider_count"],
        "providers": providers,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": INTEGRATION_PREFLIGHT_LIMITATION,
        },
    }


def build_integration_provider_catalog(*, selected_providers: set[str] | None = None) -> dict[str, Any]:
    """Build operator-facing provider setup metadata without reading environment values."""
    provider_scope = _provider_scope(selected_providers)
    providers = {
        provider: {
            "provider": provider,
            "required_env_names": list(required_env_names),
            "scope_flag": f"--provider {provider}",
            "confirmation_flag": f"--confirm-safe-sandbox {provider}",
            "requires_sandbox_named_env": True,
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "allowed_sandbox_test_scope": list(ALLOWED_SANDBOX_TEST_SCOPE),
            "forbidden_test_scope": list(FORBIDDEN_TEST_SCOPE),
            **_provider_benchmark_impact(provider),
            "next_required_actions": _next_required_actions(
                provider=provider,
                missing_env_names=list(required_env_names),
                safe_test_environment_confirmed=False,
            ),
        }
        for provider, required_env_names in provider_scope.items()
    }
    return {
        "mode": "local_preflight_provider_catalog",
        "provider_scope": list(provider_scope),
        "provider_count": len(providers),
        "providers": providers,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": INTEGRATION_PREFLIGHT_LIMITATION,
        },
    }


def _readiness_packet_provider(*, provider: str, status: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    can_run = status["can_run_sandbox_adapter_tests"]
    return {
        "provider": provider,
        "status": status["status"],
        "required_env_names": status["required_env_names"],
        "missing_env_names": status["missing_env_names"],
        "safe_test_environment_confirmed": status["safe_test_environment_confirmed"],
        "can_run_sandbox_adapter_tests": can_run,
        "adapter_hardening_gate": "ready_for_sandbox_adapter_tests" if can_run else "blocked_until_checklist_passes",
        "blocked_reasons": status["blocked_reasons"],
        "next_required_actions": status["next_required_actions"],
        "setup_checklist": [
            {
                "id": "sandbox_environment_names",
                "status": "passed" if not status["missing_env_names"] else "blocked",
                "required_env_names": status["required_env_names"],
                "missing_env_names": status["missing_env_names"],
            },
            {
                "id": "safe_non_production_sandbox_confirmation",
                "status": "passed" if status["safe_test_environment_confirmed"] else "blocked",
                "confirmation_flag": catalog["confirmation_flag"],
            },
        ],
        "operator_commands": [
            f"ares integration-preflight --list-providers --provider {provider} --json",
            f"ares integration-preflight --provider {provider} --json",
            f"ares integration-preflight --provider {provider} --confirm-safe-sandbox {provider} --json",
        ],
        "required_external_artifacts": list(REQUIRED_EXTERNAL_ARTIFACTS),
        "allowed_sandbox_test_scope": status["allowed_sandbox_test_scope"],
        "forbidden_test_scope": status["forbidden_test_scope"],
        "benchmark_feature_rows": status["benchmark_feature_rows"],
        "production_blockers_addressed": status["production_blockers_addressed"],
        "secret_values_inspected": False,
        "live_api_called": False,
        "sandbox_submission_performed": False,
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
    selected_providers: set[str] | None = None,
) -> dict[str, Any]:
    """Build a preflight report for live/sandbox adapter hardening prerequisites."""
    env_names = set(configured_env_names if configured_env_names is not None else configured_integration_env_names())
    provider_scope = _provider_scope(selected_providers)
    confirmations = _provider_key_set(
        safe_test_environment_confirmations,
        label="safe sandbox confirmation provider",
    )
    _validate_confirmation_scope(confirmations=confirmations, provider_scope=set(provider_scope))
    providers = {
        provider: _provider_status(
            provider=provider,
            required_env_names=required_env_names,
            configured_env_names=env_names,
            safe_test_environment_confirmed=provider in confirmations,
        )
        for provider, required_env_names in provider_scope.items()
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
        "provider_scope": list(provider_scope),
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


def _provider_scope(selected_providers: set[str] | None) -> dict[str, list[str]]:
    if not selected_providers:
        return dict(PROVIDER_REQUIREMENTS)
    _provider_key_set(selected_providers, label="integration provider")
    return {provider: PROVIDER_REQUIREMENTS[provider] for provider in PROVIDER_REQUIREMENTS if provider in selected_providers}


def _provider_key_set(provider_keys: set[str] | None, *, label: str) -> set[str]:
    if not provider_keys:
        return set()
    unknown = sorted(provider_keys - set(PROVIDER_REQUIREMENTS))
    if unknown:
        valid = ", ".join(PROVIDER_REQUIREMENTS)
        raise ValueError(f"Unknown {label}: {', '.join(unknown)}. Valid providers: {valid}")
    return set(provider_keys)


def _validate_confirmation_scope(*, confirmations: set[str], provider_scope: set[str]) -> None:
    outside_scope = sorted(confirmations - provider_scope)
    if outside_scope:
        selected = ", ".join(sorted(provider_scope))
        raise ValueError(
            "Safe sandbox confirmation provider outside selected provider scope: "
            f"{', '.join(outside_scope)}. Selected providers: {selected}"
        )


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
    blocked_reasons = _blocked_reasons(
        provider=provider,
        missing_env_names=missing,
        safe_test_environment_confirmed=safe_test_environment_confirmed,
    )
    return {
        "provider": provider,
        "status": status,
        "required_env_names": list(required_env_names),
        "missing_env_names": missing,
        "safe_test_environment_confirmed": safe_test_environment_confirmed,
        "can_run_sandbox_adapter_tests": status == "ready_for_sandbox_adapter_tests",
        "blocked_reasons": blocked_reasons,
        "next_required_actions": _next_required_actions(
            provider=provider,
            missing_env_names=missing,
            safe_test_environment_confirmed=safe_test_environment_confirmed,
        ),
        "allowed_sandbox_test_scope": list(ALLOWED_SANDBOX_TEST_SCOPE),
        "forbidden_test_scope": list(FORBIDDEN_TEST_SCOPE),
        **_provider_benchmark_impact(provider),
        "secret_values_inspected": False,
        "live_api_called": False,
    }


def _provider_benchmark_impact(provider: str) -> dict[str, list[str]]:
    impact = PROVIDER_BENCHMARK_IMPACT[provider]
    return {
        "benchmark_feature_rows": list(impact["benchmark_feature_rows"]),
        "production_blockers_addressed": list(impact["production_blockers_addressed"]),
    }


def _blocked_reasons(
    *,
    provider: str,
    missing_env_names: list[str],
    safe_test_environment_confirmed: bool,
) -> list[str]:
    reasons: list[str] = []
    if missing_env_names:
        reasons.append(f"missing sandbox environment names: {', '.join(missing_env_names)}")
    if not safe_test_environment_confirmed:
        reasons.append(f"safe non-production sandbox tenant not confirmed for {provider}")
    return reasons


def _next_required_actions(
    *,
    provider: str,
    missing_env_names: list[str],
    safe_test_environment_confirmed: bool,
) -> list[str]:
    actions: list[str] = []
    if missing_env_names:
        actions.append(f"configure sandbox-only environment variable names for {provider}")
    if not safe_test_environment_confirmed:
        actions.append(f"confirm {provider} is a safe non-production sandbox tenant before adapter tests")
    return actions
