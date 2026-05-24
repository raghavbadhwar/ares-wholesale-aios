from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.ares.ares.cli import build_chat_context, build_dashboard_launch, main
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import ActionExecutionLog, WorkflowRun
from apps.ares.ares import hardening
from apps.ares.ares.profiles import ClientProfile, write_client_profile
from plugins.ares.dashboard import plugin_api
from plugins.ares.dashboard.plugin_api import _save_run_report, router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_json_repository_redacts_sensitive_action_logs_on_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    repo = JsonClientRepository(tmp_path / "data")
    repo.save_action_log(
        ActionExecutionLog(
            id="act_1",
            client_id="demo",
            action_type="send_whatsapp_business_message",
            status="executed",
            result={
                "recipient_phone": "+919999999999",
                "body": "Please pay INR 1200 today",
                "api_token": "super-secret-token",
            },
            error="Authorization failed for +919999999999",
        )
    )

    raw = (tmp_path / "data" / "action_logs.json").read_text(encoding="utf-8")
    stored = json.loads(raw)[0]

    assert "Please pay INR 1200 today" not in raw
    assert "super-secret-token" not in raw
    assert stored["result"]["recipient_phone"] == "[redacted-phone:9999]"
    assert stored["result"]["body"].startswith("[redacted-text len=")
    assert stored["result"]["api_token"].startswith("[redacted-secret len=")
    assert stored["error"] == "Authorization failed for [redacted-phone:9999]"


def test_json_repository_appends_redacted_jsonl_audit_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    repo = JsonClientRepository(tmp_path / "data")
    repo.save_action_log(
        ActionExecutionLog(
            id="act_1",
            client_id="demo",
            action_type="send_customer_message",
            status="executed",
            result={"body": "Namaste Raj ji", "recipient_phone": "+919999999999"},
        )
    )
    repo.log_workflow_run(
        WorkflowRun(
            id="wf_1",
            workflow_name="daily-brief",
            client_id="demo",
            status="completed",
            outputs={"response_text": "Raj ko call karo"},
        )
    )

    audit_log = (
        tmp_path / ".ares" / "clients" / "demo" / "logs" / "audit_events.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    action_event = json.loads(audit_log[0])
    workflow_event = json.loads(audit_log[1])

    assert action_event["event_type"] == "action_log"
    assert action_event["payload"]["result"]["body"].startswith("[redacted-text len=")
    assert action_event["payload"]["result"]["recipient_phone"] == "[redacted-phone:9999]"
    assert workflow_event["event_type"] == "workflow_run"
    assert workflow_event["payload"]["outputs"]["response_text"].startswith("[redacted-text len=")


def test_dashboard_launch_blocks_remote_bind_without_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile = ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner")
    context_path = build_chat_context(profile)

    with pytest.raises(ValueError, match="without --insecure"):
        build_dashboard_launch(profile, context_path, host="0.0.0.0", insecure=False)

    with pytest.raises(ValueError, match="ARES_ALLOW_INSECURE_DASHBOARD_BIND"):
        build_dashboard_launch(profile, context_path, host="0.0.0.0", insecure=True)

    monkeypatch.setenv("ARES_ALLOW_INSECURE_DASHBOARD_BIND", "1")
    launch = build_dashboard_launch(profile, context_path, host="0.0.0.0", insecure=True)
    assert "--insecure" in launch.command


def test_cli_health_check_emits_runtime_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    monkeypatch.setattr("sys.argv", ["ares", "health-check", "--client", "demo", "--json"])

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "local_runtime_health"
    assert payload["client_id"] == "demo"
    assert payload["status"] in {"ready", "warning"}
    assert any(check["id"] == "client_profile" for check in payload["checks"])


def test_dashboard_overview_redacts_recent_action_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo Wholesale", owner_name="Owner"))
    repo = JsonClientRepository(tmp_path / ".ares" / "clients" / "demo" / "data")
    repo.save_action_log(
        ActionExecutionLog(
            id="act_1",
            client_id="demo",
            action_type="voice_query_transcript",
            status="answered",
            result={
                "transcript": "Raj bhai ko bolo payment bheje",
                "recipient_phone": "+919999999999",
            },
        )
    )

    response = _client().get("/overview?client=demo")

    assert response.status_code == 200
    payload = response.json()
    action_log = payload["recent_records"]["action_logs"][0]
    assert action_log["result"]["transcript"].startswith("[redacted-text len=")
    assert action_log["result"]["recipient_phone"] == "[redacted-phone:9999]"


def test_dashboard_run_report_persists_redacted_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile = ClientProfile(client_slug="demo", business_name="Demo Wholesale", owner_name="Owner")
    write_client_profile(profile)

    report = _save_run_report(
        profile,
        "send-message",
        "Queued customer follow-up.",
        {"recipient_phone": "+919999999999", "body": "Please clear overdue amount today."},
    )

    stored = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
    assert stored["payload"]["recipient_phone"] == "[redacted-phone:9999]"
    assert stored["payload"]["body"].startswith("[redacted-text len=")
    assert "Please clear overdue amount today." not in Path(report["json_path"]).read_text(encoding="utf-8")


def test_dashboard_health_route_returns_runtime_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo Wholesale", owner_name="Owner"))

    response = _client().get("/health?client=demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local_runtime_health"
    assert payload["client_id"] == "demo"


def test_dashboard_run_failure_is_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo Wholesale", owner_name="Owner"))

    def explode(*args, **kwargs):
        raise RuntimeError("boom for +919999999999")

    monkeypatch.setattr(plugin_api, "_run_local_action", explode)
    response = _client().post("/run", json={"client": "demo", "action": "today"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Ares dashboard action failed"
    runtime_errors = (tmp_path / ".ares" / "clients" / "demo" / "logs" / "runtime_errors.jsonl").read_text(
        encoding="utf-8"
    )
    assert "boom for +919999999999" not in runtime_errors
    assert "[redacted-phone:9999]" in runtime_errors


def test_runtime_error_event_posts_redacted_monitoring_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    monkeypatch.setenv("ARES_MONITORING_WEBHOOK_URL", "https://monitor.example.com/ares")
    monkeypatch.setenv("ARES_MONITORING_TIMEOUT_SECONDS", "1.25")
    monkeypatch.setenv("ARES_MONITORING_MAX_ATTEMPTS", "2")
    calls: list[dict[str, object]] = []

    class Response:
        status_code = 200

    def fake_post(url, *, json, headers, timeout, follow_redirects):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
                "follow_redirects": follow_redirects,
            }
        )
        return Response()

    monkeypatch.setattr(hardening.httpx, "post", fake_post)

    hardening.append_runtime_error_event(
        "demo",
        event_type="ares_cli_error",
        error="boom for +919999999999",
        context={"body": "Please pay today"},
    )

    assert len(calls) == 1
    payload = calls[0]["json"]
    assert calls[0]["url"] == "https://monitor.example.com/ares"
    assert calls[0]["timeout"] == 1.25
    assert payload["message"] == "boom for [redacted-phone:9999]"
    assert payload["extra"]["context"]["body"].startswith("[redacted-text len=")
    assert "Please pay today" not in json.dumps(payload)
    audit_lines = (
        tmp_path / ".ares" / "clients" / "demo" / "logs" / "audit_events.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    delivery_event = json.loads(audit_lines[-1])
    assert delivery_event["event_type"] == "monitoring_delivery"
    assert delivery_event["status"] == "delivered"


def test_runtime_error_event_retries_monitoring_before_recording_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    monkeypatch.setenv("ARES_MONITORING_WEBHOOK_URL", "https://monitor.example.com/ares")
    monkeypatch.setenv("ARES_MONITORING_MAX_ATTEMPTS", "2")
    attempts = {"count": 0}

    def fake_post(*args, **kwargs):
        attempts["count"] += 1
        raise hardening.httpx.ConnectError("network down")

    monkeypatch.setattr(hardening.httpx, "post", fake_post)
    monkeypatch.setattr(hardening.time, "sleep", lambda *args, **kwargs: None)

    hardening.append_runtime_error_event(
        "demo",
        event_type="ares_dashboard_run_error",
        error="failed for +919999999999",
        context={},
    )

    assert attempts["count"] == 2
    audit_lines = (
        tmp_path / ".ares" / "clients" / "demo" / "logs" / "audit_events.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    delivery_event = json.loads(audit_lines[-1])
    assert delivery_event["event_type"] == "monitoring_delivery"
    assert delivery_event["status"] == "failed"
    assert delivery_event["attempts"] == 2
