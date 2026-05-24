"""Runtime hardening helpers for Ares local and pilot surfaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


_SECRET_FIELD_TOKENS = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "signature",
)
_LONG_TEXT_FIELDS = {
    "body",
    "draft",
    "message",
    "raw_text",
    "transcript",
    "response_text",
    "content",
}
_PHONE_FIELDS = {"phone", "recipient_phone", "contact_phone"}
_GSTIN_FIELDS = {"gstin", "supplier_gstin", "customer_gstin", "seller_gstin", "ecommerce_gstin"}
_ALLOWED_REMOTE_BIND_ENV = "ARES_ALLOW_INSECURE_DASHBOARD_BIND"
_MONITORING_WEBHOOK_ENV = "ARES_MONITORING_WEBHOOK_URL"
_MONITORING_TIMEOUT_ENV = "ARES_MONITORING_TIMEOUT_SECONDS"
_MONITORING_ATTEMPTS_ENV = "ARES_MONITORING_MAX_ATTEMPTS"
_DEFAULT_MONITORING_TIMEOUT_SECONDS = 2.5
_DEFAULT_MONITORING_ATTEMPTS = 2
_SENTRY_ENV_KEYS = ("ARES_SENTRY_DSN", "SENTRY_DSN")

_PHONE_RE = re.compile(r"\+?[1-9]\d{7,14}")
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z0-9]{13}\b", re.IGNORECASE)


def ensure_private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(path, 0o700)
    return path


def write_private_text(path: Path, content: str, *, mode: int = 0o600) -> Path:
    ensure_private_directory(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    _chmod_best_effort(tmp, mode)
    tmp.replace(path)
    _chmod_best_effort(path, mode)
    return path


def write_private_json(path: Path, payload: Any, *, mode: int = 0o600, indent: int = 2) -> Path:
    return write_private_text(path, json.dumps(payload, indent=indent, sort_keys=True), mode=mode)


def append_private_jsonl(path: Path, payload: Any, *, mode: int = 0o600) -> Path:
    ensure_private_directory(path.parent)
    line = json.dumps(payload, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.write("\n")
    _chmod_best_effort(path, mode)
    return path


def append_client_audit_event(
    client_slug: str | None,
    *,
    event_type: str,
    payload: Any,
    level: str = "info",
    status: str = "recorded",
) -> Path:
    path = _logs_file_path(client_slug, "audit_events.jsonl")
    event = {
        "timestamp": _utc_now_iso(),
        "event_type": event_type,
        "level": level,
        "status": status,
        "client_id": client_slug,
        "payload": _redact_value(payload, key="payload"),
    }
    return append_private_jsonl(path, event)


def append_runtime_error_event(
    client_slug: str | None,
    *,
    event_type: str,
    error: str,
    context: dict[str, Any] | None = None,
) -> Path:
    path = _logs_file_path(client_slug, "runtime_errors.jsonl")
    event = {
        "timestamp": _utc_now_iso(),
        "event_type": event_type,
        "level": "error",
        "status": "failed",
        "client_id": client_slug,
        "error": _redact_string(error, key="error"),
        "context": _redact_value(context or {}, key="context"),
    }
    append_private_jsonl(path, event)
    _emit_monitoring_event(client_slug, event)
    return path


def redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return _redact_value(value, key=None)


def redact_action_log_record(value: dict[str, Any]) -> dict[str, Any]:
    record = dict(value)
    record["result"] = _redact_value(record.get("result", {}), key="result")
    if record.get("error"):
        record["error"] = _redact_string(str(record["error"]), key="error")
    return record


def redact_workflow_run_record(value: dict[str, Any]) -> dict[str, Any]:
    record = dict(value)
    record["inputs"] = _redact_value(record.get("inputs", {}), key="inputs")
    record["outputs"] = _redact_value(record.get("outputs", {}), key="outputs")
    record["errors"] = _redact_value(record.get("errors", []), key="errors")
    return record


def validate_dashboard_bind(host: str, *, insecure: bool) -> None:
    normalized = host.strip().lower()
    if _is_loopback_host(normalized):
        return
    if not insecure:
        raise ValueError(
            "Refusing non-local dashboard bind without --insecure. Keep Ares on 127.0.0.1/localhost unless you are deliberately fronting it with HTTPS and access controls."
        )
    if os.getenv(_ALLOWED_REMOTE_BIND_ENV, "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise ValueError(
            f"Refusing remote dashboard bind because {_ALLOWED_REMOTE_BIND_ENV}=1 is not set. Remote exposure requires explicit opt-in plus external HTTPS and authentication."
        )


def build_runtime_health_snapshot(*, client_slug: str | None = None) -> dict[str, Any]:
    from apps.ares.ares.connectors.auto_ingest import validate_local_inputs
    from apps.ares.ares.paths import CLIENT_SUBDIRECTORIES, client_root, get_ares_home
    from apps.ares.ares.profiles import load_client_profile
    from apps.ares.ares.workflows.integration_preflight import configured_integration_env_names

    ares_home = get_ares_home()
    checks: list[dict[str, Any]] = []
    warnings = 0
    blocked = 0

    home_exists = ares_home.exists()
    checks.append(
        _check(
            "ares_home",
            "passed" if home_exists else "warning",
            detail=str(ares_home),
        )
    )
    if not home_exists:
        warnings += 1

    monitoring_env_names = sorted(
        name for name in (_MONITORING_WEBHOOK_ENV, *_SENTRY_ENV_KEYS) if os.getenv(name, "").strip()
    )
    monitoring_status = "passed" if monitoring_env_names else "warning"
    monitoring_config = _monitoring_config()
    checks.append(
        _check(
            "monitoring_hook",
            monitoring_status,
            detail=f"configured ({monitoring_config['provider']})" if monitoring_env_names else "not configured",
            configured_env_names=monitoring_env_names,
            timeout_seconds=monitoring_config["timeout_seconds"],
            max_attempts=monitoring_config["max_attempts"],
        )
    )
    if monitoring_status != "passed":
        warnings += 1

    dashboard_opt_in = os.getenv(_ALLOWED_REMOTE_BIND_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    checks.append(
        _check(
            "dashboard_remote_bind_policy",
            "passed",
            detail="remote bind requires explicit opt-in",
            remote_bind_opt_in=dashboard_opt_in,
        )
    )
    audit_log_path = _logs_file_path(client_slug, "audit_events.jsonl")
    runtime_error_path = _logs_file_path(client_slug, "runtime_errors.jsonl")
    logging_findings = []
    for path in (audit_log_path.parent, audit_log_path, runtime_error_path):
        if path.exists() and _mode_too_broad(path, 0o700 if path.is_dir() else 0o600):
            logging_findings.append({"path": str(path), "expected_mode": "0700" if path.is_dir() else "0600"})
    checks.append(
        _check(
            "structured_logging",
            "passed" if not logging_findings else "warning",
            detail="per-client JSONL audit/error logs are available" if client_slug else "global JSONL runtime logs are available",
            audit_log_path=str(audit_log_path),
            runtime_error_log_path=str(runtime_error_path),
            findings=logging_findings,
        )
    )
    if logging_findings:
        warnings += 1

    payload: dict[str, Any] = {
        "mode": "local_runtime_health",
        "status": "ready",
        "client_id": client_slug,
        "ares_home": str(ares_home),
        "checks": checks,
        "env_contract": {
            "ares_home_env_set": bool(os.getenv("ARES_HOME", "").strip()),
            "monitoring_env_names_present": monitoring_env_names,
            "integration_env_name_count": len(configured_integration_env_names()),
            "dashboard_remote_bind_opt_in": dashboard_opt_in,
            "monitoring_provider": monitoring_config["provider"],
            "monitoring_timeout_seconds": monitoring_config["timeout_seconds"],
            "monitoring_max_attempts": monitoring_config["max_attempts"],
        },
        "dashboard": {
            "local_only_default": True,
            "remote_bind_requires_insecure_flag": True,
            "remote_bind_requires_explicit_opt_in": True,
            "https_termination_required_for_remote_bind": True,
        },
        "logging": {
            "audit_log_path": str(audit_log_path),
            "audit_log_exists": audit_log_path.exists(),
            "runtime_error_log_path": str(runtime_error_path),
            "runtime_error_log_exists": runtime_error_path.exists(),
            "monitoring_delivery_enabled": monitoring_config["enabled"],
            "monitoring_destination": monitoring_config["destination_summary"],
        },
        "audit": {
            "secret_values_inspected": False,
            "live_external_api_called": False,
            "limitation": "Local runtime health signal only; no live APIs, secrets, or remote probes are exercised.",
        },
    }

    if client_slug:
        root = client_root(client_slug)
        profile_path = root / "profile.yaml"
        try:
            load_client_profile(client_slug)
            profile_status = "passed"
            profile_detail = str(profile_path)
        except FileNotFoundError:
            profile_status = "blocked"
            profile_detail = f"missing: {profile_path}"
        except Exception as exc:
            profile_status = "blocked"
            profile_detail = str(exc)
        payload["checks"].append(_check("client_profile", profile_status, detail=profile_detail))
        if profile_status == "blocked":
            blocked += 1

        missing_dirs = [name for name in CLIENT_SUBDIRECTORIES if not (root / name).exists()]
        dirs_status = "passed" if not missing_dirs else "warning"
        payload["checks"].append(
            _check(
                "client_scaffold",
                dirs_status,
                detail="all required directories present" if not missing_dirs else "missing required directories",
                missing=missing_dirs,
            )
        )
        if missing_dirs:
            warnings += 1

        privacy_issues = _privacy_issues(root)
        privacy_status = "passed" if not privacy_issues else "warning"
        payload["checks"].append(
            _check(
                "private_permissions",
                privacy_status,
                detail="private file modes look safe" if not privacy_issues else "some runtime files are broader than recommended",
                findings=privacy_issues,
            )
        )
        if privacy_issues:
            warnings += 1

        validation = validate_local_inputs(client_id=client_slug)
        payload["client_runtime"] = {
            "root": str(root),
            "reports_dir": str(root / "reports"),
            "logs_dir": str(root / "logs"),
            "blocking_input_errors": len(validation["blocking_errors"]),
            "parseable_exports": validation["parseable_exports"],
            "inbox_messages": validation["inbox_messages"],
        }
        payload["checks"].append(
            _check(
                "input_readiness",
                "passed" if not validation["blocking_errors"] else "warning",
                detail="inputs parse cleanly" if not validation["blocking_errors"] else "input blockers present",
                blocking_errors=validation["blocking_errors"],
            )
        )
        if validation["blocking_errors"]:
            warnings += 1

    payload["status"] = "blocked" if blocked else ("warning" if warnings else "ready")
    return payload


def _check(check_id: str, status: str, *, detail: str, **extra: Any) -> dict[str, Any]:
    return {"id": check_id, "status": status, "detail": detail, **extra}


def _privacy_issues(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for directory in ("logs", "reports", "data", "approvals", "workflows", "chat"):
        path = root / directory
        if path.exists() and _mode_too_broad(path, 0o700):
            findings.append({"path": str(path), "expected_mode": "0700"})
    for file_name in ("profile.yaml",):
        path = root / file_name
        if path.exists() and _mode_too_broad(path, 0o600):
            findings.append({"path": str(path), "expected_mode": "0600"})
    for path in list((root / "data").glob("*.json")) + list((root / "reports").glob("*.json")) + list((root / "reports").glob("*.md")):
        if path.exists() and _mode_too_broad(path, 0o600):
            findings.append({"path": str(path), "expected_mode": "0600"})
    return findings


def _mode_too_broad(path: Path, recommended_mode: int) -> bool:
    try:
        actual = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    return (actual & ~recommended_mode) != 0


def _redact_value(value: Any, *, key: str | None) -> Any:
    if isinstance(value, dict):
        return {sub_key: _redact_value(sub_value, key=sub_key) for sub_key, sub_value in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, key=key) for item in value]
    if isinstance(value, str):
        return _redact_string(value, key=key)
    return value


def _redact_string(value: str, *, key: str | None) -> str:
    normalized_key = (key or "").strip().lower()
    if any(token in normalized_key for token in _SECRET_FIELD_TOKENS):
        return _secret_summary(value)
    if normalized_key in _PHONE_FIELDS:
        return _mask_phone(value)
    if normalized_key in _GSTIN_FIELDS:
        return _mask_gstin(value)
    if normalized_key in _LONG_TEXT_FIELDS:
        return _text_summary(value)

    redacted = _PHONE_RE.sub(lambda match: _mask_phone(match.group(0)), value)
    redacted = _GSTIN_RE.sub(lambda match: _mask_gstin(match.group(0)), redacted)
    return redacted


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "[redacted-phone]"
    return f"[redacted-phone:{digits[-4:]}]"


def _mask_gstin(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) < 6:
        return "[redacted-gstin]"
    return f"{normalized[:2]}***{normalized[-3:]}"


def _text_summary(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    return f"[redacted-text len={len(cleaned)} sha256={_sha256_prefix(cleaned)}]"


def _secret_summary(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    return f"[redacted-secret len={len(cleaned)} sha256={_sha256_prefix(cleaned)}]"


def _sha256_prefix(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _monitoring_config() -> dict[str, Any]:
    webhook = os.getenv(_MONITORING_WEBHOOK_ENV, "").strip()
    if webhook:
        parsed = urlparse(webhook)
        destination_summary = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return {
            "enabled": True,
            "provider": "webhook",
            "destination": webhook,
            "destination_summary": destination_summary,
            "headers": {},
            "timeout_seconds": _monitoring_timeout_seconds(),
            "max_attempts": _monitoring_max_attempts(),
        }

    dsn = next((os.getenv(name, "").strip() for name in _SENTRY_ENV_KEYS if os.getenv(name, "").strip()), "")
    if dsn:
        parsed = urlparse(dsn)
        public_key = parsed.username or ""
        secret = parsed.password or ""
        project_id = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
        base_path = parsed.path.strip("/").split("/")[:-1]
        prefix = f"/{'/'.join(base_path)}" if base_path else ""
        store_path = f"{prefix}/api/{project_id}/store/"
        destination = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            destination = f"{destination}:{parsed.port}"
        destination += store_path
        auth_parts = [
            "Sentry sentry_version=7",
            "sentry_client=ares-hardening/1.0",
            f"sentry_key={public_key}",
        ]
        if secret:
            auth_parts.append(f"sentry_secret={secret}")
        return {
            "enabled": True,
            "provider": "sentry_dsn",
            "destination": destination,
            "destination_summary": destination,
            "headers": {
                "Content-Type": "application/json",
                "X-Sentry-Auth": ", ".join(auth_parts),
            },
            "timeout_seconds": _monitoring_timeout_seconds(),
            "max_attempts": _monitoring_max_attempts(),
        }

    return {
        "enabled": False,
        "provider": "none",
        "destination": "",
        "destination_summary": "none",
        "headers": {},
        "timeout_seconds": _monitoring_timeout_seconds(),
        "max_attempts": _monitoring_max_attempts(),
    }


def _monitoring_timeout_seconds() -> float:
    raw = os.getenv(_MONITORING_TIMEOUT_ENV, "").strip()
    if not raw:
        return _DEFAULT_MONITORING_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_MONITORING_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_MONITORING_TIMEOUT_SECONDS


def _monitoring_max_attempts() -> int:
    raw = os.getenv(_MONITORING_ATTEMPTS_ENV, "").strip()
    if not raw:
        return _DEFAULT_MONITORING_ATTEMPTS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MONITORING_ATTEMPTS
    return min(max(value, 1), 5)


def _emit_monitoring_event(client_slug: str | None, event: dict[str, Any]) -> None:
    config = _monitoring_config()
    if not config["enabled"]:
        return

    payload = {
        "event_id": hashlib.sha256(
            json.dumps(event, sort_keys=True).encode("utf-8")
        ).hexdigest()[:32],
        "timestamp": event["timestamp"],
        "level": event.get("level", "error"),
        "logger": "ares.runtime",
        "platform": "python",
        "server_name": "ares-local",
        "environment": "ares-local-pilot",
        "tags": {
            "client_id": client_slug or "global",
            "event_type": event["event_type"],
            "provider": config["provider"],
        },
        "extra": event["payload"] if "payload" in event else {
            "status": event.get("status"),
            "context": event.get("context", {}),
        },
        "message": event.get("error") or event["event_type"],
    }

    attempts = config["max_attempts"]
    timeout = config["timeout_seconds"]
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(
                config["destination"],
                json=payload,
                headers=config["headers"],
                timeout=timeout,
                follow_redirects=True,
            )
            if response.status_code < 400:
                _append_monitoring_delivery_event(
                    client_slug,
                    {
                        "timestamp": _utc_now_iso(),
                        "event_type": "monitoring_delivery",
                        "level": "info",
                        "status": "delivered",
                        "provider": config["provider"],
                        "attempt": attempt,
                    },
                )
                return
            last_error = f"http_status_{response.status_code}"
            if response.status_code not in {408, 425, 429, 500, 502, 503, 504}:
                break
        except httpx.HTTPError as exc:
            last_error = exc.__class__.__name__
        if attempt < attempts:
            time.sleep(0.15 * attempt)

    _append_monitoring_delivery_event(
        client_slug,
        {
            "timestamp": _utc_now_iso(),
            "event_type": "monitoring_delivery",
            "level": "warning",
            "status": "failed",
            "provider": config["provider"],
            "attempts": attempts,
            "error": last_error or "unknown_monitoring_error",
        },
    )


def _append_monitoring_delivery_event(client_slug: str | None, event: dict[str, Any]) -> None:
    path = _logs_file_path(client_slug, "audit_events.jsonl")
    append_private_jsonl(path, event)


def _logs_file_path(client_slug: str | None, filename: str) -> Path:
    if client_slug:
        return _ares_home() / "clients" / client_slug / "logs" / filename
    return _ares_home() / "logs" / filename


def _ares_home() -> Path:
    override = os.getenv("ARES_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".ares").resolve()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass
