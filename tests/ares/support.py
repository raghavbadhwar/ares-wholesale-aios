from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
FORBIDDEN_KEY_FRAGMENTS = ("secret", "password", "private_key", "authorization")
FORBIDDEN_VALUE_FRAGMENTS = ("sk_live_", "rzp_live_", "bearer ", "-----begin ")


def load_json_fixture(*relative_path: str) -> Any:
    fixture_path = FIXTURE_ROOT.joinpath(*relative_path)
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def load_text_fixture(*relative_path: str) -> str:
    fixture_path = FIXTURE_ROOT.joinpath(*relative_path)
    return fixture_path.read_text(encoding="utf-8")


def load_xml_fixture(*relative_path: str) -> ElementTree.Element:
    fixture_path = FIXTURE_ROOT.joinpath(*relative_path)
    return ElementTree.fromstring(fixture_path.read_text(encoding="utf-8"))


def whatsapp_delivery_receipt_event() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("whatsapp", "sandbox_delivery_receipt.json"))


def whatsapp_failed_delivery_receipt_event() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("whatsapp", "sandbox_failed_delivery_receipt.json"))


def whatsapp_inbound_message_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("whatsapp", "sandbox_inbound_message.json"))


def whatsapp_status_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("whatsapp", "sandbox_status_webhook.json"))


def gstn_gstr1_upload_response() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("gst", "gstn_gstr1_upload_response.json"))


def gsp_gstr2b_pull_response() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("gst", "gsp_gstr2b_pull_response.json"))


def gstn_validation_failed_response() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("gst", "gstn_validation_failed_response.json"))


def gsp_manual_review_response() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("gst", "gsp_manual_review_response.json"))


def payment_webhook_event() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "razorpay_payment_captured.json"))


def payment_failed_webhook_event() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "razorpay_payment_failed.json"))


def razorpay_captured_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "razorpay_webhook_payment_captured.json"))


def razorpay_failed_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "razorpay_webhook_payment_failed.json"))


def razorpay_refunded_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "razorpay_webhook_payment_refunded.json"))


def cashfree_success_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "cashfree_webhook_payment_success.json"))


def cashfree_failed_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "cashfree_webhook_payment_failed.json"))


def phonepe_success_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "phonepe_webhook_payment_success.json"))


def phonepe_failed_webhook_payload() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("payments", "phonepe_webhook_payment_failed.json"))


def tally_odbc_rows() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("tally", "odbc_invoice_rows.json"))


def tally_odbc_manual_review_rows() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("tally", "odbc_manual_review_rows.json"))


def tally_status_xml_text() -> str:
    return load_text_fixture("tally", "status_receipt.xml")


def proof_artifact_manifest() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "proof_artifact_manifest.json"))


def benchmark_proof_collection_snapshot() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "benchmark_proof_collection_snapshot.json"))


def benchmark_specialist_handoff_snapshot() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "benchmark_specialist_handoff_snapshot.json"))


def benchmark_closure_dispatch_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "benchmark_closure_dispatch_packet_snapshot.json")
    )


def benchmark_validation_report_snapshot() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "benchmark_validation_report_snapshot.json"))


def benchmark_validation_action_queue_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "benchmark_validation_action_queue_snapshot.json")
    )


def benchmark_validation_dispatch_result_intake_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "benchmark_validation_dispatch_result_intake_snapshot.json")
    )


def benchmark_result_validation_report_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "benchmark_result_validation_report_snapshot.json")
    )


def benchmark_result_intake_validation_report_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "benchmark_result_intake_validation_report_snapshot.json")
    )


def benchmark_result_intake_validation_report_action_queue_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "benchmark_result_intake_validation_report_action_queue_snapshot.json"
        )
    )


def proof_collection_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "proof_collection_packet_snapshot.json"))


def external_evidence_bundle_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "external_evidence_bundle_packet_snapshot.json")
    )


def external_evidence_bundle_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "external_evidence_bundle_blocked_packet_snapshot.json")
    )


def rejected_proof_collection_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "rejected_proof_collection_packet_snapshot.json")
    )


def external_evidence_bundle_rejected_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "external_evidence_bundle_rejected_packet_snapshot.json")
    )


def proof_review_handoff_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "proof_review_handoff_packet_snapshot.json")
    )


def proof_review_decision_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "proof_review_decision_packet_snapshot.json")
    )


def proof_reviewer_assignment_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "proof_reviewer_assignment_packet_snapshot.json")
    )


def proof_review_decision_ledger_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "proof_review_decision_ledger_packet_snapshot.json")
    )


def proof_review_signed_envelope_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "proof_review_signed_envelope_packet_snapshot.json")
    )


def proof_review_signed_envelope_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_blocked_packet_snapshot.json"
        )
    )


def proof_review_signed_envelope_key_rejections_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_key_rejections_snapshot.json"
        )
    )


def proof_review_signed_envelope_invalid_decision_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_invalid_decision_snapshot.json"
        )
    )


def proof_review_signed_envelope_multi_snapshot_chain_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_multi_snapshot_chain_snapshot.json"
        )
    )


def proof_review_signed_envelope_mixed_snapshot_chain_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_mixed_snapshot_chain_snapshot.json"
        )
    )


def proof_review_signed_envelope_combined_failure_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "proof_review_signed_envelope_combined_failure_snapshot.json"
        )
    )


def external_evidence_bundle_mixed_snapshot_chain_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "external_evidence_bundle_mixed_snapshot_chain_snapshot.json"
        )
    )


def external_evidence_bundle_unverified_snapshot_chain_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "external_evidence_bundle_unverified_snapshot_chain_snapshot.json"
        )
    )


def external_evidence_bundle_combined_rejection_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "external_evidence_bundle_combined_rejection_snapshot.json"
        )
    )


def reviewed_evidence_intake_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "reviewed_evidence_intake_packet_snapshot.json")
    )


def reviewed_evidence_intake_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "reviewed_evidence_intake_blocked_packet_snapshot.json")
    )


def payment_reviewed_evidence_intake_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "payment_reviewed_evidence_intake_blocked_packet_snapshot.json"
        )
    )


def whatsapp_reviewed_evidence_intake_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "whatsapp_reviewed_evidence_intake_blocked_packet_snapshot.json"
        )
    )


def tally_reviewed_evidence_intake_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "tally_reviewed_evidence_intake_blocked_packet_snapshot.json"
        )
    )


def gst_reviewed_evidence_intake_blocked_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "gst_reviewed_evidence_intake_blocked_packet_snapshot.json"
        )
    )


def reviewed_evidence_intake_rejected_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "reviewed_evidence_intake_rejected_packet_snapshot.json")
    )


def reviewed_evidence_intake_reopened_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "reviewed_evidence_intake_reopened_packet_snapshot.json")
    )


def reviewed_evidence_intake_invalid_resubmission_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "reviewed_evidence_intake_invalid_resubmission_packet_snapshot.json"
        )
    )


def reviewed_evidence_intake_repeated_rejection_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "reviewed_evidence_intake_repeated_rejection_packet_snapshot.json"
        )
    )


def reviewed_evidence_intake_mixed_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture("proof", "reviewed_evidence_intake_mixed_packet_snapshot.json")
    )


def reviewed_evidence_intake_mixed_reopened_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "reviewed_evidence_intake_mixed_reopened_packet_snapshot.json"
        )
    )


def reviewed_evidence_intake_mixed_rejection_cycle_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof", "reviewed_evidence_intake_mixed_rejection_cycle_packet_snapshot.json"
        )
    )


def reviewed_evidence_intake_multi_attempt_resubmission_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_multi_attempt_resubmission_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_multi_attempt_rejection_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_multi_attempt_rejection_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_long_chain_resubmission_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_long_chain_resubmission_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_long_chain_rejection_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_long_chain_rejection_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_mixed_history_invalid_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_mixed_history_invalid_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_multi_invalid_history_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_multi_invalid_history_packet_snapshot.json",
        )
    )


def reviewed_evidence_intake_mixed_type_history_packet_snapshot() -> dict[str, Any]:
    return copy.deepcopy(
        load_json_fixture(
            "proof",
            "reviewed_evidence_intake_mixed_type_history_packet_snapshot.json",
        )
    )


def payment_gateway_sandbox_proof_artifact() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "payment_gateway_sandbox_evidence.json"))


def payment_gateway_sandbox_proof_manifest() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "payment_gateway_sandbox_manifest.json"))


def payment_gateway_sandbox_external_evidence_bundle() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "payment_gateway_external_evidence_bundle.json"))


def payment_gateway_sandbox_reviewed_evidence_intake() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "payment_gateway_reviewed_evidence_intake.json"))


def whatsapp_sandbox_proof_artifact() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "whatsapp_sandbox_evidence.json"))


def whatsapp_sandbox_proof_manifest() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "whatsapp_sandbox_manifest.json"))


def whatsapp_sandbox_external_evidence_bundle() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "whatsapp_external_evidence_bundle.json"))


def whatsapp_sandbox_reviewed_evidence_intake() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "whatsapp_reviewed_evidence_intake.json"))


def gst_sandbox_proof_artifact() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "gst_sandbox_evidence.json"))


def gst_sandbox_proof_manifest() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "gst_sandbox_manifest.json"))


def gst_sandbox_external_evidence_bundle() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "gst_external_evidence_bundle.json"))


def gst_sandbox_reviewed_evidence_intake() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "gst_reviewed_evidence_intake.json"))


def tally_sandbox_proof_artifact() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "tally_sandbox_evidence.json"))


def tally_sandbox_proof_manifest() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "tally_sandbox_manifest.json"))


def tally_sandbox_external_evidence_bundle() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "tally_external_evidence_bundle.json"))


def tally_sandbox_reviewed_evidence_intake() -> dict[str, Any]:
    return copy.deepcopy(load_json_fixture("proof", "tally_reviewed_evidence_intake.json"))


def tally_status_payload_from_xml() -> dict[str, Any]:
    root = load_xml_fixture("tally", "status_receipt.xml")
    import_result = root.find("./BODY/IMPORTRESULT")
    if import_result is None:
        raise AssertionError("Missing ./BODY/IMPORTRESULT in tally status fixture")

    items: list[dict[str, str]] = []
    for item in import_result.findall("./ITEMS/ITEM"):
        items.append(
            {
                "record_type": item.findtext("RECORDTYPE", default="").strip().lower(),
                "record_id": item.findtext("RECORDID", default="").strip(),
                "status": item.findtext("STATUS", default="").strip().lower(),
            }
        )

    return {
        "batch_id": import_result.findtext("BATCHID", default="").strip(),
        "status": import_result.findtext("STATUS", default="").strip().lower(),
        "external_reference": import_result.findtext("EXTERNALREFERENCE", default="").strip(),
        "items": items,
    }


def assert_local_contract_audit(audit: dict[str, Any], *, limitation: str, **expected_fields: Any) -> None:
    assert audit["limitation"] == limitation
    for field, expected_value in expected_fields.items():
        assert audit[field] == expected_value


def assert_pending_approval(repo: Any, action_type: str, *, expected_data: dict[str, Any] | None = None) -> Any:
    matches = [approval for approval in repo.list_pending_approvals() if approval.type == action_type]
    assert len(matches) == 1
    approval = matches[0]
    if expected_data:
        for key, expected_value in expected_data.items():
            assert approval.data[key] == expected_value
    return approval


def assert_last_action_log(repo: Any, *, action_type: str, status: str | None = None) -> Any:
    log = repo.list_action_logs()[-1]
    assert log.action_type == action_type
    if status is not None:
        assert log.status == status
    return log


def assert_redaction_safe_payload(payload: Any, *, allowed_key_paths: set[str] | None = None) -> None:
    issues = _collect_redaction_issues(payload, allowed_key_paths=allowed_key_paths or set())
    assert issues == [], f"Fixture payload is not redaction-safe: {issues}"


def build_razorpay_signature_header(
    payload: dict[str, Any],
    *,
    webhook_signing_secret: str = "sandbox_signature_key",
) -> dict[str, str]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = hmac.new(
        webhook_signing_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Razorpay-Signature": signature}


def build_cashfree_signature_header(
    payload: dict[str, Any],
    *,
    webhook_signing_secret: str = "sandbox_signature_key",
) -> dict[str, str]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    signature = hmac.new(
        webhook_signing_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Cashfree-Signature": signature}


def build_phonepe_signature_header(
    payload: dict[str, Any],
    *,
    salt_key: str = "sandbox_signature_key",
    salt_index: str = "1",
    webhook_path: str = "/v1/notifications/payment",
) -> dict[str, str]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    body_b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    digest = hashlib.sha256(f"{body_b64}{webhook_path}{salt_key}".encode("utf-8")).hexdigest()
    return {"X-VERIFY": f"{digest}###{salt_index}"}


def build_whatsapp_signature_header(
    payload: dict[str, Any],
    *,
    webhook_app_secret: str = "sandbox_app_secret",
) -> dict[str, str]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hmac.new(
        webhook_app_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


def build_gst_sandbox_signature_headers(
    *,
    provider: str,
    operation: str,
    gstin: str,
    request_payload: dict[str, Any],
    client_id: str = "sandbox_client_id",
    signing_secret: str = "sandbox_signing_secret",
    session_token: str | None = None,
) -> dict[str, str]:
    canonical = json.dumps(
        {
            "provider": provider.strip().lower(),
            "operation": operation.strip().lower(),
            "gstin": gstin.strip(),
            "request_payload": request_payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "X-Ares-Sandbox-Provider": provider.strip().lower(),
        "X-Ares-Sandbox-Client-Id": client_id,
        "X-Ares-Sandbox-Signature": signature,
    }
    if session_token:
        headers["X-Ares-Sandbox-Session"] = f"present:{len(session_token)}"
    return headers


def _collect_redaction_issues(
    payload: Any,
    *,
    path: str = "root",
    allowed_key_paths: set[str],
) -> list[str]:
    if isinstance(payload, dict):
        issues: list[str] = []
        for key, value in payload.items():
            key_path = f"{path}.{key}"
            normalized_key = key.lower()
            if key_path not in allowed_key_paths and any(
                fragment in normalized_key for fragment in FORBIDDEN_KEY_FRAGMENTS
            ):
                issues.append(f"{key_path}: forbidden key fragment")
            issues.extend(
                _collect_redaction_issues(
                    value,
                    path=key_path,
                    allowed_key_paths=allowed_key_paths,
                )
            )
        return issues

    if isinstance(payload, list):
        issues: list[str] = []
        for index, item in enumerate(payload):
            issues.extend(
                _collect_redaction_issues(
                    item,
                    path=f"{path}[{index}]",
                    allowed_key_paths=allowed_key_paths,
                )
            )
        return issues

    if isinstance(payload, str):
        normalized_value = payload.lower()
        if any(fragment in normalized_value for fragment in FORBIDDEN_VALUE_FRAGMENTS):
            return [f"{path}: forbidden value fragment"]

    return []
