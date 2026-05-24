from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.gstn_sandbox import (
    GST_SANDBOX_ADAPTER_LIMITATION,
    GST_SANDBOX_HEALTHCHECK_LIMITATION,
    GST_SANDBOX_PROOF_LIMITATION,
    build_gst_sandbox_auth_headers,
    build_gst_sandbox_external_evidence_bundle,
    build_gst_sandbox_healthcheck,
    build_gst_sandbox_proof_artifact_metadata,
    build_gst_sandbox_proof_metadata_manifest,
    build_gst_sandbox_reviewed_evidence_intake,
    ingest_gst_sandbox_tax_adjustments,
    ingest_gst_sandbox_response,
    prepare_gst_sandbox_exchange,
)
from apps.ares.ares.data.models import Invoice, PurchaseInvoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
    build_benchmark_reviewed_evidence_intake_packet,
)
from tests.ares.support import (
    assert_last_action_log,
    assert_local_contract_audit,
    build_gst_sandbox_signature_headers,
    gst_sandbox_external_evidence_bundle,
    gst_sandbox_proof_artifact,
    gst_sandbox_proof_manifest,
    gst_sandbox_reviewed_evidence_intake,
    gsp_gstr2b_pull_response,
    gsp_manual_review_response,
    gstn_gstr1_upload_response,
    gstn_validation_failed_response,
)


def test_should_prepare_signed_gstn_sandbox_request_from_local_contract() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()

    result = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )

    assert result["status"] == "approval_required"
    assert result["request"]["endpoint_key"] == "gstn.gstr1.upload"
    assert result["provider_request"]["path"] == "/sandbox/gstn/gstr1/upload"
    assert result["provider_request"]["headers"] == build_gst_sandbox_signature_headers(
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        request_payload=fixture["request_payload"],
        client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    assert result["adapter"]["request_prepared"] is True
    assert result["adapter"]["session_token_attached"] is False
    assert result["adapter"]["limitation"] == GST_SANDBOX_ADAPTER_LIMITATION


def test_should_prepare_session_aware_gsp_sandbox_request_shape() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gsp_gstr2b_pull_response()

    result = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gsp_sandbox",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gsp-sandbox.example.test",
        sandbox_client_id="gsp_client_id",
        signing_secret="gsp_signing_secret",
        session_token="gsp_session_token",
    )

    assert result["status"] == "approval_required"
    assert result["request"]["endpoint_key"] == "gstn.gstr2b.pull"
    assert result["provider_request"]["headers"] == build_gst_sandbox_signature_headers(
        provider="gsp_sandbox",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        request_payload=fixture["request_payload"],
        client_id="gsp_client_id",
        signing_secret="gsp_signing_secret",
        session_token="gsp_session_token",
    )
    assert result["provider_request"]["session_token_attached"] is True
    assert result["adapter"]["session_token_attached"] is True


def test_should_ingest_structured_gst_sandbox_tax_adjustments_without_csv() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_adj",
                business_gstin_id="gst_mh",
                supplier_id="sup_soap",
                supplier_gstin="27PRINC1234F1Z5",
                invoice_number="PUR-ADJ",
                date=None,
                taxable_value=10000,
                tax_amount=1800,
                gst_rate_percent=18,
                status="booked",
            )
        ]
    )

    result = ingest_gst_sandbox_tax_adjustments(
        repository=repo,
        client_id="demo",
        provider="gsp_sandbox",
        adjustment_payloads=[
            {
                "id": "tax_adj_gsp_1",
                "document_type": "purchase_invoice",
                "document_id": "pinv_adj",
                "action": "amend",
                "status": "booked",
                "taxable_value": 12500,
                "tax_amount": 2250,
                "gst_rate_percent": 18,
                "business_gstin_id": "gst_mh",
                "note": "GSP adjustment payload",
            }
        ],
    )

    assert result["provider"] == "gsp_sandbox"
    assert result["path"] == "sandbox://gsp_sandbox/tax-adjustments"
    assert result["adjustment_ids"] == ["tax_adj_gsp_1"]
    assert len(result["artifact_ids"]) == 1
    assert len(result["statutory_document_ids"]) == 1
    assert result["tax_event_ids"] == ["tax_purchase_pinv_adj"]
    assert result["adapter"]["structured_adjustments_ingested"] is True
    assert repo.get_purchase_invoices()[0].taxable_value == 12500
    assert repo.get_tax_events()[0].business_gstin_id == "gst_mh"
    assert repo.get_tax_adjustments()[0].source_file == "sandbox://gsp_sandbox/tax-adjustments"
    assert repo.get_statutory_adjustment_artifacts()[0].provider == "gsp_sandbox"
    assert repo.get_statutory_adjustment_documents()[0].document_role == "amendment_note"


def test_should_normalize_accepted_gstn_sandbox_response_through_adapter() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )

    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )

    assert result["status"] == "accepted"
    assert result["provider"] == "gstn_nic"
    assert result["response"]["portal_reference"] == "GSTN-SANDBOX-REF-0001"
    assert result["adapter"]["response_processed"] is True
    assert result["adapter"]["session_contract_required"] is False
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["statutory_submission_performed"] is False
    assert result["proof_transcript"]["limitation"] == GST_SANDBOX_PROOF_LIMITATION
    assert_last_action_log(repo, action_type="gstn_api_response_normalized", status="accepted")


def test_should_normalize_validation_failed_and_manual_review_responses_through_adapter() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    failed_fixture = gstn_validation_failed_response()
    failed_request = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=failed_fixture["operation"],
        gstin=failed_fixture["gstin"],
        requested_by="accountant",
        payload=failed_fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    failed_result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=failed_request,
        response_payload=failed_fixture,
    )

    manual_fixture = gsp_manual_review_response()
    manual_request = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gsp_sandbox",
        operation=manual_fixture["operation"],
        gstin=manual_fixture["gstin"],
        requested_by="accountant",
        payload=manual_fixture["request_payload"],
        base_url="https://gsp-sandbox.example.test",
        sandbox_client_id="gsp_client_id",
        signing_secret="gsp_signing_secret",
        session_token="gsp_session_token",
    )
    manual_result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gsp_sandbox",
        request_contract=manual_request,
        response_payload=manual_fixture,
    )

    assert failed_result["status"] == "validation_failed"
    assert failed_result["audit"]["manual_fallback_required"] is True
    assert failed_result["response"]["validation_errors"][0]["code"] == "invalid_period"

    assert manual_result["status"] == "needs_manual_review"
    assert manual_result["provider"] == "gsp_sandbox"
    assert manual_result["adapter"]["session_contract_required"] is True
    assert manual_result["audit"]["manual_fallback_required"] is True


def test_should_ingest_adjustments_from_gst_sandbox_response_payload() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_resp",
                business_gstin_id="gst_mh",
                supplier_id="sup_soap",
                supplier_gstin="27PRINC1234F1Z5",
                invoice_number="PUR-RESP",
                date=None,
                taxable_value=10000,
                tax_amount=1800,
                gst_rate_percent=18,
                status="booked",
            )
        ]
    )
    request_contract = {
        "request": {
            "request_id": "gstn_req_resp_1",
            "operation": "gstr2b_pull",
            "endpoint_key": "gstn.gstr2b.pull",
            "gstin": "27ABCDE1234F1Z5",
            "payload_digest": {"period": "2026-05"},
        }
    }

    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gsp_sandbox",
        request_contract=request_contract,
        response_payload={
            "response": {
                "status": "needs_manual_review",
                "portal_reference": "GSP-SANDBOX-2B-MANUAL-ADJ-0001",
                "errors": [{"code": "supplier_adjustment", "field": "adjustments", "message": "Supplier amended invoice."}],
            },
            "payload_reference": "redacted://gsp/sandbox/gstr2b-adjustment-review-1",
            "adjustments": [
                {
                    "id": "tax_adj_resp_1",
                    "document_type": "purchase_invoice",
                    "document_id": "pinv_resp",
                    "action": "amend",
                    "status": "booked",
                    "taxable_value": 13000,
                    "tax_amount": 2340,
                    "gst_rate_percent": 18,
                    "business_gstin_id": "gst_mh",
                    "note": "Supplier amendment from sandbox response",
                }
            ],
        },
    )

    assert result["status"] == "needs_manual_review"
    assert result["adapter"]["structured_adjustments_ingested"] is True
    assert result["structured_adjustments"]["adjustment_ids"] == ["tax_adj_resp_1"]
    assert len(result["structured_adjustments"]["artifact_ids"]) == 1
    assert len(result["structured_adjustments"]["statutory_document_ids"]) == 1
    assert repo.get_purchase_invoices()[0].tax_amount == 2340
    artifact = repo.get_statutory_adjustment_artifacts()[0]
    assert artifact.adjustment_record_id == "tax_adj_resp_1"
    assert artifact.source_kind == "gst_sandbox_response"
    assert artifact.operation == "gstr2b_pull"
    assert artifact.metadata["adjustment_source"] == "normalized_payload"
    assert repo.get_statutory_adjustment_documents()[0].document_role == "amendment_note"


def test_should_extract_raw_purchase_adjustments_from_nested_sandbox_response_shape() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_nested",
                business_gstin_id="gst_mh",
                supplier_id="sup_nested",
                supplier_gstin="27PRINC1234F1Z5",
                invoice_number="PUR-NESTED",
                date=None,
                taxable_value=10000,
                tax_amount=1800,
                gst_rate_percent=18,
                status="booked",
            )
        ]
    )
    request_contract = {
        "request": {
            "request_id": "gstn_req_resp_nested_1",
            "operation": "gstr2b_pull",
            "endpoint_key": "gstn.gstr2b.pull",
            "gstin": "27ABCDE1234F1Z5",
            "payload_digest": {"period": "2026-05"},
        }
    }

    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gsp_sandbox",
        request_contract=request_contract,
        response_payload={
            "response": {
                "status": "needs_manual_review",
                "portal_reference": "GSP-SANDBOX-2B-MANUAL-RAW-0001",
                "data": {
                    "supplier_adjustments": [
                        {
                            "invoice_number": "PUR-NESTED",
                            "adjustment_type": "amend",
                            "taxable_amount": 14000,
                            "total_tax": 2520,
                            "gst_rate": 18,
                            "reason": "Supplier amended invoice in raw response.",
                        }
                    ]
                },
            },
            "payload_reference": "redacted://gsp/sandbox/gstr2b-raw-adjustment-review-1",
        },
    )

    assert result["status"] == "needs_manual_review"
    assert result["adapter"]["structured_adjustments_ingested"] is True
    assert result["adapter"]["structured_adjustment_source"] == "raw_provider_shape"
    assert len(result["structured_adjustments"]["artifact_ids"]) == 1
    assert len(result["structured_adjustments"]["statutory_document_ids"]) == 1
    assert repo.get_purchase_invoices()[0].tax_amount == 2520
    adjustment = repo.get_tax_adjustments()[0]
    assert adjustment.document_id == "pinv_nested"
    assert adjustment.document_number == "PUR-NESTED"
    artifact = repo.get_statutory_adjustment_artifacts()[0]
    assert artifact.source_kind == "gst_sandbox_raw_response"
    assert artifact.metadata["source_key"] == "response.data.supplier_adjustments"
    assert repo.get_statutory_adjustment_documents()[0].document_role == "amendment_note"


def test_should_extract_raw_sales_credit_note_shape_from_sandbox_response() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(
                id="inv_sales_raw",
                invoice_number="INV-RAW-1",
                customer_id="cust_1",
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                gst_rate_percent=18,
                status="open",
            )
        ]
    )
    request_contract = {
        "request": {
            "request_id": "gstn_req_resp_sales_1",
            "operation": "gstr1_return_upload",
            "endpoint_key": "gstn.gstr1.upload",
            "gstin": "27ABCDE1234F1Z5",
            "payload_digest": {"period": "2026-05"},
        }
    }

    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload={
            "response": {
                "status": "accepted",
                "portal_reference": "GSTN-SANDBOX-GSTR1-RAW-CN-0001",
                "credit_notes": [
                    {
                        "invoice_number": "INV-RAW-1",
                        "taxable_amount": 0,
                        "total_tax": 0,
                        "reason": "Credit note posted in raw response.",
                    }
                ],
            },
            "payload_reference": "redacted://gstn/sandbox/gstr1-raw-credit-note-1",
        },
    )

    assert result["status"] == "accepted"
    assert result["adapter"]["structured_adjustments_ingested"] is True
    assert result["adapter"]["structured_adjustment_source"] == "raw_provider_shape"
    adjustment = repo.get_tax_adjustments()[0]
    assert adjustment.document_type == "sales_invoice"
    assert adjustment.action == "cancel"
    assert adjustment.document_id == "inv_sales_raw"
    assert repo.get_invoices()[0].status == "cancelled"
    artifact = repo.get_statutory_adjustment_artifacts()[0]
    assert artifact.source_kind == "gst_sandbox_raw_response"
    assert artifact.metadata["source_key"] == "response.credit_notes"
    assert repo.get_statutory_adjustment_documents()[0].document_role == "credit_note"


def test_should_expose_gst_sandbox_healthcheck_for_gstn_and_gsp() -> None:
    blocked_gstn = build_gst_sandbox_healthcheck(provider="gstn_nic")
    ready_gsp = build_gst_sandbox_healthcheck(
        provider="gsp_sandbox",
        configured_env_names={
            "GSP_SANDBOX_BASE_URL",
            "GSP_SANDBOX_CLIENT_ID",
            "GSP_SANDBOX_CLIENT_SECRET",
            "GSP_SANDBOX_SESSION_TOKEN",
        },
        safe_test_environment_confirmed=True,
    )

    assert blocked_gstn["status"] == "blocked"
    assert "GSTN_SANDBOX_BASE_URL" in blocked_gstn["missing_env_names"]
    assert blocked_gstn["audit"]["limitation"] == GST_SANDBOX_HEALTHCHECK_LIMITATION

    assert ready_gsp["status"] == "ready_for_local_adapter_tests"
    assert ready_gsp["required_env_names"] == [
        "GSP_SANDBOX_BASE_URL",
        "GSP_SANDBOX_CLIENT_ID",
        "GSP_SANDBOX_CLIENT_SECRET",
        "GSP_SANDBOX_SESSION_TOKEN",
    ]
    assert ready_gsp["request_signature_scheme"] == "hmac_sha256"
    assert ready_gsp["missing_env_names"] == []


def test_should_build_proof_safe_gst_artifact_metadata_accepted_by_proof_packet() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )

    artifact = build_gst_sandbox_proof_artifact_metadata(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert artifact["provider"] == "gstn_nic"
    assert artifact["redaction_confirmed"] is True
    assert artifact["artifact_path_or_reference"].startswith("redacted://gst_sandbox/gstn_nic/gst_txn_")
    assert requirement["status"] == "metadata_accepted_for_review"


def test_should_build_gst_proof_metadata_manifest_for_operator_handoff() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )

    manifest = build_gst_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert manifest["generated_from"] == "gstn_sandbox"
    assert manifest["redaction_confirmed"] is True
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["provider"] == "gstn_nic"
    assert requirement["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_gst_proof_artifact_and_manifest_fixtures_are_accepted_by_proof_packet() -> None:
    artifact = gst_sandbox_proof_artifact()
    manifest = gst_sandbox_proof_manifest()
    artifact_packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert {item["artifact_id"]: item for item in artifact_packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]["status"] == "metadata_accepted_for_review"
    assert {item["artifact_id"]: item for item in manifest_packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]["status"] == "metadata_accepted_for_review"
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True


def test_should_build_gst_external_evidence_bundle_for_operator_handoff() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )

    bundle = build_gst_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    bundle_item = packet["external_evidence_bundles"][0]

    assert bundle["bundle_id"].startswith("external-evidence-bundle-gst-")
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


def test_gst_external_evidence_bundle_fixture_is_accepted_for_handoff() -> None:
    bundle = gst_sandbox_external_evidence_bundle()
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


def test_should_build_gst_reviewed_evidence_intake_for_operator_login_and_filing_identity() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )
    bundle = build_gst_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )

    intake = build_gst_sandbox_reviewed_evidence_intake(
        adapter_result=result,
        external_evidence_bundle=bundle,
        reviewed_at="2026-05-23T12:15:00+05:30",
        reviewer_reference="redacted-gst-reviewer-1",
    )
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert intake["bundle_id"] == bundle["bundle_id"]
    assert intake["provider"] == "gstn_nic"
    assert intake["operator_login_metadata"]["actor_role"] == "accountant"
    assert intake["subject_metadata_kind"] == "gst_filing_identity"
    assert intake["subject_metadata"]["gstin"] == fixture["gstin"]
    assert intake["subject_metadata"]["filing_period"] == "2026-05"
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert packet["reviewed_evidence_intake_summary"]["intakes_accepted_for_local_replay"] == 1
    assert packet["audit"]["reviewed_evidence_intake_files_read"] is True


def test_gst_reviewed_evidence_intake_fixture_is_accepted_by_packet() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
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


def test_gst_reviewed_evidence_intake_blocks_on_missing_operator_session_and_gstin() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["session_reference"] = ""
    intake["subject_metadata"]["gstin"] = ""
    intake["filing_identity_metadata"]["gstin"] = ""

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
        "subject_metadata.missing_identifier",
    ]


def test_gst_reviewed_evidence_intake_blocks_after_reviewer_rejection_with_valid_metadata() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-gst-review-rejection-1"
    intake["review_rejection_reasons"] = ["filing_period_mismatch"]

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
        "review_rejection_reason:filing_period_mismatch",
    ]


def test_gst_reviewed_evidence_intake_reopens_after_corrected_resubmission() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-gst-review-rejection-1"
    intake["review_rejection_reasons"] = ["filing_period_mismatch"]
    intake["review_resubmission_reference"] = "redacted-gst-review-resubmission-1"

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
        "review_rejection_reason:filing_period_mismatch",
    ]


def test_gst_reviewed_evidence_intake_accepts_second_corrected_resubmission_after_repeated_review_cycle() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-gst-review-rejection-2"
    intake["review_rejection_reasons"] = ["filing_period_still_misaligned"]
    intake["review_resubmission_reference"] = "redacted-gst-review-resubmission-2"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-gst-review-rejection-1",
            "review_rejection_reasons": ["filing_period_mismatch"],
            "review_resubmission_reference": "redacted-gst-review-resubmission-1",
        }
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
    assert packet["reviewed_evidence_intake_summary"][
        "intakes_resubmitted_after_review_rejection"
    ] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["review_cycle_history_summary"] == {
        "prior_review_cycle_count": 1,
        "total_review_cycle_count": 2,
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
        "review_rejection_reason:filing_period_still_misaligned",
    ]
