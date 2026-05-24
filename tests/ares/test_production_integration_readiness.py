from __future__ import annotations

from apps.ares.ares.workflows.production_integration_readiness import (
    REPORT_LIMITATION,
    build_production_integration_readiness_report,
)


def test_should_map_current_repo_integration_surfaces_without_claiming_sandbox_or_benchmark_readiness() -> None:
    report = build_production_integration_readiness_report(configured_env_names=set())

    assert report["mode"] == "local_production_integration_readiness_report"
    assert report["status"] == "live_blocked"
    assert report["scope"] == "separate_production_integration_spike"
    assert report["benchmark_parity_claimed"] is False
    assert report["audit"] == {
        "live_api_called": False,
        "sandbox_submission_performed": False,
        "secret_values_inspected": False,
        "limitation": REPORT_LIMITATION,
    }

    whatsapp = report["integrations"]["whatsapp_business"]
    assert whatsapp["current_code_status"] == "local"
    assert whatsapp["production_readiness_status"] == "live_blocked"
    assert whatsapp["provider_scope"] == ["whatsapp_business"]
    assert whatsapp["required_env_names_in_repo"] == [
        "META_WABA_SANDBOX_PHONE_NUMBER_ID",
        "META_WABA_SANDBOX_ACCESS_TOKEN",
        "META_WABA_SANDBOX_VERIFY_TOKEN",
    ]
    assert whatsapp["missing_env_contracts"] == [
        "META_WABA_SANDBOX_APP_SECRET",
        "META_WABA_SANDBOX_BUSINESS_ACCOUNT_ID",
    ]
    assert any(
        row["path"] == "apps/ares/ares/connectors/whatsapp_sandbox.py" and row["exists"]
        for row in whatsapp["existing_files"]
    )
    assert all(
        blocker != "missing adapter module or scaffold: apps/ares/ares/connectors/whatsapp_sandbox.py"
        for blocker in whatsapp["blockers"]
    )
    assert "Current WhatsApp sandbox adapter is local-only and does not register or receive a live Meta webhook." in whatsapp["blockers"]
    assert "No template registration transcript or provider-authenticated message evidence is stored in repo for a WhatsApp sandbox path." in whatsapp["blockers"]
    assert whatsapp["provider_preflight"]["status"] == "blocked"

    payment = report["integrations"]["payment_gateway"]
    assert payment["current_code_status"] == "local"
    assert payment["production_readiness_status"] == "live_blocked"
    assert payment["provider_scope"] == ["razorpay", "cashfree", "phonepe"]
    assert "RAZORPAY_SANDBOX_KEY_ID" in payment["required_env_names_in_repo"]
    assert "CASHFREE_SANDBOX_CLIENT_SECRET" in payment["required_env_names_in_repo"]
    assert "PHONEPE_SANDBOX_SALT_KEY" in payment["required_env_names_in_repo"]
    assert payment["missing_env_contracts"] == []
    assert any(
        row["path"] == "apps/ares/ares/connectors/payment_gateway_sandbox.py" and row["exists"]
        for row in payment["existing_files"]
    )
    assert all(
        blocker != "missing adapter module or scaffold: apps/ares/ares/connectors/payment_gateway_sandbox.py"
        for blocker in payment["blockers"]
    )
    assert "Current payment gateway sandbox adapter is local-only and currently normalizes Razorpay, Cashfree, and PhonePe webhook payloads only." in payment["blockers"]
    assert "No provider-authenticated payment sandbox proof artifact is stored in repo." in payment["blockers"]

    tally = report["integrations"]["tally_busy"]
    assert tally["current_code_status"] == "local"
    assert tally["production_readiness_status"] == "live_blocked"
    assert tally["required_env_names_in_repo"] == [
        "TALLY_SANDBOX_BASE_URL",
        "BUSY_SANDBOX_BASE_URL",
        "TALLY_BUSY_SANDBOX_SYSTEM",
        "TALLY_BUSY_SANDBOX_COMPANY_NAME",
        "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
        "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
        "TALLY_BUSY_SANDBOX_ODBC_DSN",
    ]
    assert tally["missing_env_contracts"] == []
    assert any(row["path"] == "apps/ares/ares/connectors/tally_sync_adapter.py" and row["exists"] for row in tally["existing_files"])
    assert all(
        blocker != "missing adapter module or scaffold: apps/ares/ares/connectors/tally_sync_adapter.py"
        for blocker in tally["blockers"]
    )
    assert "Current Tally/Busy bridge adapter and execution harness are local-only and do not execute live ODBC/XML sessions." in tally["blockers"]
    assert (
        "No provider-authenticated sync proof artifact or CA-reviewed close proof is stored in repo for a Tally/Busy path."
        in tally["blockers"]
    )

    gstn = report["integrations"]["gstn_gsp"]
    assert gstn["current_code_status"] == "local"
    assert gstn["production_readiness_status"] == "live_blocked"
    assert gstn["provider_scope"] == ["gstn_nic", "gsp_sandbox"]
    assert gstn["required_env_names_in_repo"] == [
        "GSTN_SANDBOX_BASE_URL",
        "GSTN_SANDBOX_CLIENT_ID",
        "GSTN_SANDBOX_CLIENT_SECRET",
        "NIC_SANDBOX_BASE_URL",
        "NIC_SANDBOX_CLIENT_ID",
        "NIC_SANDBOX_CLIENT_SECRET",
        "GSP_SANDBOX_BASE_URL",
        "GSP_SANDBOX_CLIENT_ID",
        "GSP_SANDBOX_CLIENT_SECRET",
        "GSP_SANDBOX_SESSION_TOKEN",
    ]
    assert gstn["missing_env_contracts"] == [
        "No repo-defined filing-identity contract exists beyond client-id/client-secret/session-token placeholders.",
    ]
    assert any(
        row["path"] == "apps/ares/ares/connectors/gstn_sandbox.py" and row["exists"]
        for row in gstn["existing_files"]
    )
    assert any(
        row["path"] == "apps/ares/ares/connectors/gsp_sandbox.py" and row["exists"]
        for row in gstn["existing_files"]
    )
    assert all(
        blocker != "missing adapter module or scaffold: apps/ares/ares/connectors/gstn_sandbox.py"
        for blocker in gstn["blockers"]
    )
    assert all(
        blocker != "missing adapter module or scaffold: apps/ares/ares/connectors/gsp_sandbox.py"
        for blocker in gstn["blockers"]
    )
    assert "Current GST sandbox adapters are local-only request/response shapers and do not execute live GSTN, NIC, or GSP traffic." in gstn["blockers"]
    assert "No provider-authenticated statutory proof artifact is stored in repo for a GST sandbox path." in gstn["blockers"]


def test_should_keep_all_integrations_live_blocked_until_missing_modules_exist_even_if_env_names_and_confirmations_are_present() -> None:
    report = build_production_integration_readiness_report(
        configured_env_names={
            "META_WABA_SANDBOX_PHONE_NUMBER_ID",
            "META_WABA_SANDBOX_ACCESS_TOKEN",
            "META_WABA_SANDBOX_VERIFY_TOKEN",
            "GSTN_SANDBOX_BASE_URL",
            "GSTN_SANDBOX_CLIENT_ID",
            "GSTN_SANDBOX_CLIENT_SECRET",
            "NIC_SANDBOX_BASE_URL",
            "NIC_SANDBOX_CLIENT_ID",
            "NIC_SANDBOX_CLIENT_SECRET",
            "GSP_SANDBOX_BASE_URL",
            "GSP_SANDBOX_CLIENT_ID",
            "GSP_SANDBOX_CLIENT_SECRET",
            "GSP_SANDBOX_SESSION_TOKEN",
            "RAZORPAY_SANDBOX_KEY_ID",
            "RAZORPAY_SANDBOX_KEY_SECRET",
            "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
            "CASHFREE_SANDBOX_CLIENT_ID",
            "CASHFREE_SANDBOX_CLIENT_SECRET",
            "CASHFREE_SANDBOX_WEBHOOK_SECRET",
            "PHONEPE_SANDBOX_MERCHANT_ID",
            "PHONEPE_SANDBOX_SALT_KEY",
            "PHONEPE_SANDBOX_SALT_INDEX",
            "TALLY_SANDBOX_BASE_URL",
            "BUSY_SANDBOX_BASE_URL",
            "TALLY_BUSY_SANDBOX_SYSTEM",
            "TALLY_BUSY_SANDBOX_COMPANY_NAME",
            "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
            "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
            "TALLY_BUSY_SANDBOX_ODBC_DSN",
        },
        safe_test_environment_confirmations={
            "whatsapp_business",
            "gstn_nic",
            "gsp_sandbox",
            "razorpay",
            "cashfree",
            "phonepe",
            "tally_busy",
        },
    )

    assert report["status"] == "live_blocked"
    assert report["integrations"]["whatsapp_business"]["provider_preflight"]["status"] == "ready"
    assert report["integrations"]["payment_gateway"]["provider_preflight"]["status"] == "ready"
    assert report["integrations"]["tally_busy"]["provider_preflight"]["status"] == "ready"
    assert report["integrations"]["gstn_gsp"]["provider_preflight"]["status"] == "ready"
    assert report["integrations"]["whatsapp_business"]["production_readiness_status"] == "live_blocked"
    assert report["integrations"]["payment_gateway"]["production_readiness_status"] == "sandbox_ready"
    assert report["integrations"]["tally_busy"]["production_readiness_status"] == "live_blocked"
    assert report["integrations"]["gstn_gsp"]["production_readiness_status"] == "live_blocked"


def test_should_recommend_operator_safe_implementation_order() -> None:
    report = build_production_integration_readiness_report(configured_env_names=set())

    assert report["recommended_implementation_order"] == [
        {
            "order": 1,
            "integration": "WhatsApp Business sandbox / Meta Cloud API",
            "key": "whatsapp_business",
            "reason": "Ares is WhatsApp-first, and the current repo still depends on forwarded text plus dry-run dispatch.",
        },
        {
            "order": 2,
            "integration": "UPI / payment gateway webhook integration",
            "key": "payment_gateway",
            "reason": "Webhook-backed payment receipt mapping is narrow, non-destructive, and reuses existing local reconciliation surfaces.",
        },
        {
            "order": 3,
            "integration": "Tally / Busy sync bridge",
            "key": "tally_busy",
            "reason": "Accounting sync should follow stabilized message and payment events, starting with one-way export plus audit receipts.",
        },
        {
            "order": 4,
            "integration": "GSTN or GSP sandbox integration",
            "key": "gstn_gsp",
            "reason": "GSTN/GSP has the highest compliance blast radius and should follow accounting-truth hardening plus provider selection.",
        },
    ]
