from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.payment_gateway_sandbox import (
    PAYMENT_GATEWAY_SANDBOX_ADAPTER_LIMITATION,
    PAYMENT_GATEWAY_SANDBOX_HEALTHCHECK_LIMITATION,
    PAYMENT_GATEWAY_SANDBOX_PROOF_LIMITATION,
    build_payment_gateway_sandbox_external_evidence_bundle,
    build_payment_gateway_sandbox_healthcheck,
    build_payment_gateway_sandbox_proof_artifact_metadata,
    build_payment_gateway_sandbox_proof_metadata_manifest,
    build_payment_gateway_sandbox_reviewed_evidence_intake,
    ingest_payment_gateway_sandbox_payload,
)
from apps.ares.ares.data.models import Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
    build_benchmark_reviewed_evidence_intake_packet,
)
from apps.ares.ares.workflows.payment_gateway import LOCAL_PAYMENT_GATEWAY_LIMITATION
from tests.ares.support import (
    assert_last_action_log,
    assert_local_contract_audit,
    build_cashfree_signature_header,
    build_phonepe_signature_header,
    build_razorpay_signature_header,
    payment_gateway_sandbox_external_evidence_bundle,
    payment_gateway_sandbox_reviewed_evidence_intake,
    cashfree_failed_webhook_payload,
    cashfree_success_webhook_payload,
    payment_gateway_sandbox_proof_artifact,
    payment_gateway_sandbox_proof_manifest,
    phonepe_failed_webhook_payload,
    phonepe_success_webhook_payload,
    razorpay_captured_webhook_payload,
    razorpay_failed_webhook_payload,
    razorpay_refunded_webhook_payload,
)


def test_should_verify_and_route_razorpay_captured_webhook_fixture_through_local_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["payment"]["signature_verification_status"] == "verified_contract_fixture"
    assert result["provider_payload"]["payment_id"] == "pay_sbox_adapter_0001"
    assert result["adapter"]["connector"] == "payment_gateway_sandbox"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["signature_scheme"] == "hmac_sha256"
    assert result["adapter"]["workflow_limitation"] == LOCAL_PAYMENT_GATEWAY_LIMITATION
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="razorpay",
        live_webhook_received=False,
        webhook_signature_verified=True,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=False,
        payment_record_created=True,
    )
    assert repo.effective_invoice_projection(repo.get_invoices()[0])["status"] == "paid"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="reconciled")
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["signature_verified"] is True
    assert result["proof_transcript"]["limitation"] == PAYMENT_GATEWAY_SANDBOX_PROOF_LIMITATION


def test_should_block_signature_mismatch_without_mutating_invoice() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers={"X-Razorpay-Signature": "mismatch"},
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "blocked_unverified_signature"
    assert result["payment"]["matched_invoice_id"] is None
    assert result["payment"]["signature_verification_status"] == "not_verified_contract_mock"
    assert result["adapter"]["signature_verified"] is False
    assert result["adapter"]["limitation"] == PAYMENT_GATEWAY_SANDBOX_ADAPTER_LIMITATION
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments()[0].status == "blocked_unverified_signature"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="blocked_unverified_signature")


def test_should_ignore_refunded_webhook_even_when_signature_verifies() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_refunded_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["payment"] is None
    assert result["provider_payload"]["event_type"] == "payment.refunded"
    assert result["adapter"]["signature_verified"] is True
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments() == []
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="ignored_non_success_event")


def test_should_ignore_failed_webhook_even_when_signature_verifies() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_failed_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["payment"] is None
    assert result["provider_payload"]["event_type"] == "payment.failed"
    assert result["adapter"]["signature_verified"] is True
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments() == []
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="ignored_non_success_event")


def test_should_ignore_duplicate_captured_replay_after_first_verified_ingest() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    headers = build_razorpay_signature_header(payload)

    first = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=headers,
        webhook_signing_secret="sandbox_signature_key",
    )
    duplicate = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=headers,
        webhook_signing_secret="sandbox_signature_key",
    )

    assert first["status"] == "reconciled"
    assert duplicate["status"] == "duplicate_ignored"
    assert duplicate["adapter"]["signature_verified"] is True
    assert len(repo.get_payments()) == 1
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="duplicate_ignored")


def test_should_verify_and_route_cashfree_success_webhook_fixture_through_local_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = cashfree_success_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="cashfree",
        payload=payload,
        headers=build_cashfree_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["payment"]["signature_verification_status"] == "verified_contract_fixture"
    assert result["provider_payload"]["payment_id"] == "cfpay_sbox_0001"
    assert result["adapter"]["provider"] == "cashfree"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["signature_scheme"] == "hmac_sha256"
    assert result["adapter"]["normalized_event_type"] == "payment.captured"
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="cashfree",
        live_webhook_received=False,
        webhook_signature_verified=True,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=False,
        payment_record_created=True,
    )
    assert repo.effective_invoice_projection(repo.get_invoices()[0])["status"] == "paid"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="reconciled")


def test_should_ignore_cashfree_failed_webhook_even_when_signature_verifies() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = cashfree_failed_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="cashfree",
        payload=payload,
        headers=build_cashfree_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["payment"] is None
    assert result["provider_payload"]["event_type"] == "PAYMENT_FAILED_WEBHOOK"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["provider"] == "cashfree"
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments() == []
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="ignored_non_success_event")


def test_should_verify_and_route_phonepe_success_webhook_fixture_through_local_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = phonepe_success_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="phonepe",
        payload=payload,
        headers=build_phonepe_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["payment"]["signature_verification_status"] == "verified_contract_fixture"
    assert result["provider_payload"]["payment_id"] == "ppepay_sbox_0001"
    assert result["adapter"]["provider"] == "phonepe"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["signature_scheme"] == "sha256_base64_path_salt_index"
    assert result["adapter"]["normalized_event_type"] == "payment.captured"
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="phonepe",
        live_webhook_received=False,
        webhook_signature_verified=True,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=False,
        payment_record_created=True,
    )
    assert repo.effective_invoice_projection(repo.get_invoices()[0])["status"] == "paid"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="reconciled")


def test_should_ignore_phonepe_failed_webhook_even_when_signature_verifies() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = phonepe_failed_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="phonepe",
        payload=payload,
        headers=build_phonepe_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["payment"] is None
    assert result["provider_payload"]["event_type"] == "checkout.order.failed"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["provider"] == "phonepe"
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments() == []
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="ignored_non_success_event")


def test_should_expose_local_payment_gateway_sandbox_healthcheck_gate() -> None:
    blocked = build_payment_gateway_sandbox_healthcheck(provider="razorpay")
    ready = build_payment_gateway_sandbox_healthcheck(
        provider="razorpay",
        configured_env_names={
            "RAZORPAY_SANDBOX_KEY_ID",
            "RAZORPAY_SANDBOX_KEY_SECRET",
            "RAZORPAY_SANDBOX_WEBHOOK_SECRET",
        },
        safe_test_environment_confirmed=True,
    )

    assert blocked["status"] == "blocked"
    assert blocked["can_run_local_adapter_tests"] is False
    assert "missing sandbox environment names" in blocked["blocked_reasons"][0]
    assert blocked["audit"]["limitation"] == PAYMENT_GATEWAY_SANDBOX_HEALTHCHECK_LIMITATION

    assert ready["status"] == "ready_for_local_adapter_tests"
    assert ready["can_run_local_adapter_tests"] is True
    assert ready["fixture_families"] == [
        "payment.captured webhook payload",
        "payment.failed webhook payload",
        "payment.refunded webhook payload",
    ]
    assert ready["webhook_signature_scheme"] == "hmac_sha256"
    assert ready["missing_env_names"] == []


def test_should_expose_cashfree_local_payment_gateway_sandbox_healthcheck_gate() -> None:
    ready = build_payment_gateway_sandbox_healthcheck(
        provider="cashfree",
        configured_env_names={
            "CASHFREE_SANDBOX_CLIENT_ID",
            "CASHFREE_SANDBOX_CLIENT_SECRET",
            "CASHFREE_SANDBOX_WEBHOOK_SECRET",
        },
        safe_test_environment_confirmed=True,
    )

    assert ready["status"] == "ready_for_local_adapter_tests"
    assert ready["can_run_local_adapter_tests"] is True
    assert ready["fixture_families"] == [
        "payment.success webhook payload",
        "payment.failed webhook payload",
    ]
    assert ready["webhook_signature_scheme"] == "hmac_sha256"
    assert ready["missing_env_names"] == []


def test_should_expose_phonepe_local_payment_gateway_sandbox_healthcheck_gate() -> None:
    ready = build_payment_gateway_sandbox_healthcheck(
        provider="phonepe",
        configured_env_names={
            "PHONEPE_SANDBOX_MERCHANT_ID",
            "PHONEPE_SANDBOX_SALT_KEY",
            "PHONEPE_SANDBOX_SALT_INDEX",
        },
        safe_test_environment_confirmed=True,
    )

    assert ready["status"] == "ready_for_local_adapter_tests"
    assert ready["can_run_local_adapter_tests"] is True
    assert ready["fixture_families"] == [
        "checkout.order.completed webhook payload",
        "checkout.order.failed webhook payload",
    ]
    assert ready["webhook_signature_scheme"] == "sha256_base64_path_salt_index"
    assert ready["missing_env_names"] == []


def test_should_build_proof_safe_payment_gateway_artifact_metadata_accepted_by_proof_packet() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    artifact = build_payment_gateway_sandbox_proof_artifact_metadata(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert artifact["artifact_id"] == "provider_sandbox_adapter_evidence"
    assert artifact["provider"] == "razorpay"
    assert artifact["sandbox_or_production_like_tenant"] == "sandbox"
    assert artifact["operator_or_accountant_reviewer"] == "redacted-ops-reviewer-1"
    assert artifact["redaction_confirmed"] is True
    assert artifact["artifact_path_or_reference"].startswith("redacted://payment_gateway/razorpay/payment_txn_")
    assert requirement["status"] == "metadata_accepted_for_review"


def test_payment_gateway_proof_artifact_fixture_is_redaction_safe_and_accepted_by_proof_packet() -> None:
    artifact = payment_gateway_sandbox_proof_artifact()
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert artifact["provider"] == "razorpay"
    assert artifact["redaction_confirmed"] is True
    assert requirement["status"] == "metadata_accepted_for_review"


def test_should_build_payment_gateway_proof_metadata_manifest_for_operator_handoff() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    manifest = build_payment_gateway_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert manifest["generated_from"] == "payment_gateway_sandbox"
    assert manifest["redaction_confirmed"] is True
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["provider"] == "razorpay"
    assert requirement["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_payment_gateway_proof_manifest_fixture_is_accepted_by_proof_packet() -> None:
    manifest = payment_gateway_sandbox_proof_manifest()
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert manifest["generated_from"] == "payment_gateway_sandbox"
    assert manifest["redaction_confirmed"] is True
    assert requirement["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_should_build_payment_gateway_external_evidence_bundle_for_operator_handoff() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    bundle = build_payment_gateway_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    bundle_item = packet["external_evidence_bundles"][0]

    assert bundle["bundle_id"].startswith("external-evidence-bundle-payment-")
    assert bundle["redaction_confirmed"] is True
    assert len(bundle["artifacts"]) == 1
    assert len(bundle["review_decisions"]) == 1
    assert len(bundle["signed_envelopes"]) == 1
    assert len(bundle["reviewer_key_registry_snapshots"]) == 1
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["proof_collection_summary"]["artifact_requirements_accepted"] == 1
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1
    assert packet["audit"]["external_evidence_bundle_files_read"] is True


def test_payment_gateway_external_evidence_bundle_fixture_is_accepted_for_handoff() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    bundle_item = packet["external_evidence_bundles"][0]

    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1


def test_should_build_payment_gateway_reviewed_evidence_intake_for_local_replay() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )
    bundle = build_payment_gateway_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )

    intake = build_payment_gateway_sandbox_reviewed_evidence_intake(
        adapter_result=result,
        external_evidence_bundle=bundle,
        reviewed_at="2026-05-23T11:10:00+05:30",
        reviewer_reference="redacted-payment-reviewer-1",
    )
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert intake["provider"] == "razorpay"
    assert intake["subject_metadata_kind"] == "payment_settlement_identity"
    assert intake["subject_metadata"]["subject_reference"] == "pay_sbox_adapter_0001"
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["subject_metadata_summary"]["subject_identifier"] == "pay_sbox_adapter_0001"
    assert item["subject_metadata_summary"]["metadata_ready"] is True


def test_payment_gateway_reviewed_evidence_intake_fixture_is_accepted_by_packet() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_accepted_for_local_replay"] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["operator_login_summary"]["session_reference_present"] is True
    assert item["subject_metadata_summary"]["portal_reference_present"] is True


def test_payment_gateway_reviewed_evidence_intake_blocks_on_missing_operator_session_and_portal_reference() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["session_reference"] = ""
    intake["subject_metadata"]["portal_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_blocked"] == 1
    assert item["intake_status"] == "blocked_until_metadata_ready"
    assert item["operator_login_summary"]["metadata_ready"] is False
    assert item["subject_metadata_summary"]["metadata_ready"] is False
    assert item["rejection_reasons"] == [
        "operator_login_metadata.missing_field:session_reference",
        "subject_metadata.missing_field:portal_reference",
    ]


def test_payment_gateway_reviewed_evidence_intake_blocks_after_reviewer_rejection_with_valid_metadata() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    intake["review_rejection_reasons"] = ["settlement_window_mismatch"]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_rejected_after_review"] == 1
    assert item["intake_status"] == "blocked_after_review_rejection"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert item["review_rejection_summary"] == {
        "rejected_after_review": True,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": False,
        "review_resubmission_reference_present": False,
    }
    assert item["rejection_reasons"] == [
        "review_rejection_reason:settlement_window_mismatch",
    ]


def test_payment_gateway_reviewed_evidence_intake_reopens_after_corrected_resubmission() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    intake["review_rejection_reasons"] = ["settlement_window_mismatch"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-1"

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"][
        "intakes_resubmitted_after_review_rejection"
    ] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert item["review_rejection_summary"] == {
        "rejected_after_review": False,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": True,
        "review_resubmission_reference_present": True,
    }
    assert item["rejection_reasons"] == [
        "review_rejection_reason:settlement_window_mismatch",
    ]


def test_payment_gateway_reviewed_evidence_intake_accepts_longer_review_remediation_chain() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-3"
    intake["review_rejection_reasons"] = ["settlement_reference_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-3"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-payment-review-rejection-1",
            "review_rejection_reasons": ["settlement_window_mismatch"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-payment-review-rejection-2",
            "review_rejection_reasons": ["gateway_reference_missing"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-2",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"][
        "intakes_with_multi_attempt_review_history"
    ] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["review_cycle_history_summary"] == {
        "prior_review_cycle_count": 2,
        "total_review_cycle_count": 3,
        "all_prior_cycles_complete": True,
        "multi_attempt_review_replay": True,
    }
    assert item["review_rejection_summary"] == {
        "rejected_after_review": False,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": True,
        "review_resubmission_reference_present": True,
    }
    assert item["rejection_reasons"] == [
        "review_rejection_reason:settlement_reference_still_incomplete",
    ]


def test_payment_gateway_reviewed_evidence_intake_blocks_on_non_dict_cycle_inside_longer_review_history() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-4"
    intake["review_rejection_reasons"] = ["settlement_metadata_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-4"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-payment-review-rejection-1",
            "review_rejection_reasons": ["settlement_window_mismatch"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-1",
        },
        "malformed-history-cycle",
        {
            "review_rejection_reference": "redacted-payment-review-rejection-3",
            "review_rejection_reasons": ["gateway_reference_missing"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-3",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="281 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"][
        "intakes_with_multi_attempt_review_history"
    ] == 1
    assert item["intake_status"] == "blocked_until_metadata_ready"
    assert item["review_cycle_history_summary"] == {
        "prior_review_cycle_count": 3,
        "total_review_cycle_count": 4,
        "all_prior_cycles_complete": False,
        "multi_attempt_review_replay": True,
    }
    assert item["review_rejection_summary"] == {
        "rejected_after_review": False,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": True,
        "review_resubmission_reference_present": True,
    }
    assert item["rejection_reasons"] == [
        "prior_review_cycle:1:invalid_payload",
        "review_rejection_reason:settlement_metadata_still_incomplete",
    ]
