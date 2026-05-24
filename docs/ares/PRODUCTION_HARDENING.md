# Ares Production Hardening

This document tracks the current production-hardening posture for Ares in the
standalone `/Users/raghav/.ares/ares` checkout. It is grounded in the local
pilot architecture described in:

- `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
- `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`

Ares is still an approval-first, local-first pilot operator loop. This checklist
hardens that posture; it does not claim benchmark parity or hosted SaaS
readiness.

## Implemented Hardening

- Private on-disk writes for Ares runtime state now flow through
  `apps/ares/ares/hardening.py`.
  - Client scaffold directories are created with private permissions.
  - `profile.yaml`, ingestion state, drive-sync state, redacted action logs, and
    redacted workflow runs are written via private-mode helpers.
- Redaction rules now cover the most sensitive Ares pilot artifacts.
  - Long free-text payloads are replaced with length + hash summaries.
  - Secret-like fields are replaced with hashed summaries.
  - Phone numbers and GSTIN-style identifiers are masked in persisted log/report
    surfaces.
  - Dashboard recent-record payloads and saved dashboard run reports are redacted
    before persistence or response emission.
- Local health and readiness signals now exist.
  - `ares health-check [--client <slug>]` reports runtime health, scaffold
    readiness, monitoring env presence, log paths, and input readiness.
  - The dashboard plugin exposes `/api/plugins/ares/health`.
- Remote exposure is now blocked by default.
  - `ares dashboard` refuses non-loopback hosts unless both `--insecure` and
    `ARES_ALLOW_INSECURE_DASHBOARD_BIND=1` are set.
  - This keeps accidental remote bind from being treated as a casual local
    default.
- Structured Ares-native audit/error logs now exist for the local JSON-backed
  runtime.
  - `apps/ares/ares/data/json_repository.py` appends redacted JSONL audit events
    for workflow runs and action logs.
  - CLI top-level failures append `runtime_errors.jsonl`.
  - Dashboard action failures append `runtime_errors.jsonl`.

## Environment And Secret Contract

Required or relevant runtime variables for the current hardening posture:

- `ARES_HOME`
  - Optional override for the local Ares state root.
  - Default remains `~/.ares`.
- `ARES_ALLOW_INSECURE_DASHBOARD_BIND`
  - Required in addition to `--insecure` before binding the dashboard to a
    non-loopback address.
  - Intended only for explicitly fronted deployments with external HTTPS and
    access control.
- `ARES_SENTRY_DSN` or `SENTRY_DSN`
  - When set, runtime error events are exported with a best-effort Sentry
    store-style POST.
- `ARES_MONITORING_WEBHOOK_URL`
  - Optional generic error-monitoring webhook destination.
  - Takes precedence over Sentry DSN variables.
- `ARES_MONITORING_TIMEOUT_SECONDS`
  - Optional per-attempt timeout for monitoring delivery.
  - Default: `2.5`.
- `ARES_MONITORING_MAX_ATTEMPTS`
  - Optional retry budget for monitoring delivery.
  - Default: `2`, max: `5`.
- Sandbox integration env names
  - The integration-preflight surface still requires sandbox-named variables
    only, such as `RAZORPAY_SANDBOX_*`, `GSTN_SANDBOX_*`, `NIC_SANDBOX_*`, and
    related provider-specific names.
  - Secret values remain intentionally unread during preflight.

## Production Hardening Checklist

- `Done`: Private permissions for client scaffold, profile, state files, and
  redacted report/log artifacts.
- `Done`: Redaction of dashboard recent records, saved dashboard run reports,
  persisted local action logs, and persisted local workflow runs.
- `Done`: Local runtime health command and dashboard health route.
- `Done`: Explicit remote-bind guard requiring deliberate opt-in.
- `Done`: Per-client JSONL audit trail for local action/workflow events.
- `Done`: Per-client JSONL runtime error trail for CLI/dashboard failures.
- `Done`: Best-effort monitoring hook export for runtime errors.
  - Runtime error events can now flow to either `ARES_MONITORING_WEBHOOK_URL`
    or Sentry DSN configuration with explicit timeout/retry limits.
- `Partial`: Error handling.
  - CLI and dashboard failures are now logged locally and can be exported, but
    there is still no alert routing, on-call integration, or incident workflow.
- `Partial`: Deploy-readiness signaling.
  - Health surfaces are local and dashboard-plugin scoped; they do not validate
    upstream reverse proxy, HTTPS, auth, or infrastructure rollback posture.
- `Blocked`: End-to-end timeout and retry policy for live integrations.
  - Most Ares integrations remain contract-only or preflight-only, so there is
    no live adapter stack yet to harden with real request timeouts, retry
    budgets, circuit breaking, or webhook replay handling.
- `Blocked`: Hosted production security controls.
  - Ares still depends on Ares/infrastructure for auth, TLS termination,
    security headers, CORS enforcement, deployment rollback, and access control.

## Risk Register

### High

- Sensitive business records still live as local JSON in the client `data/`
  directory.
  - Hardening now protects permissions and redacts log/report copies, but the
    underlying local business dataset remains plaintext on disk.
- No real monitoring/export pipeline exists.
  - Local JSONL error logs and best-effort export now exist, but there is still
    no guaranteed delivery, alerting, or retained incident backend owned by
    Ares.
- Remote hosting assumptions are external to Ares.
  - If operators bypass the local-only default, Ares still relies on upstream
    infrastructure for HTTPS, authentication, and safe rollback.

### Medium

- Health checks are local-runtime only.
  - They verify local scaffolding and hardening posture, not provider liveness
    or production control-plane health.
- Sheets-backed repository mode does not yet have the same local JSONL audit
  sink as the default JSON-backed client runtime.
- Timeout/retry posture is still mostly declarative in contract mocks rather
  than enforced in live adapters.

### Low

- Redaction is intentionally scoped to log/report/audit surfaces and may need
  expansion if new artifact shapes are introduced.
- Some runtime files may predate the private-mode helpers and retain broader
  filesystem permissions until rewritten or manually corrected.

## Missing Monitoring / Health / Security Surfaces

- Structured metrics or counters for workflow failures, ingestion blockers,
  approval backlog, and dashboard action latency.
- Authenticated, deployment-grade health/readiness endpoints outside the local
  dashboard plugin.
- Explicit reverse-proxy deployment contract for HTTPS, host allowlisting, CORS,
  and security headers when Ares is served beyond localhost.
- Rollback playbook and deployment manifest for any hosted Ares dashboard path.
- Live integration adapter timeout, retry, idempotency, and webhook replay
  policy once sandbox or production connectors are introduced.

## Production Assumptions Not Yet Satisfied

- Ares is not yet a hosted multi-tenant product shell.
- Ares is not yet wired to live WhatsApp, GSTN/NIC, payment gateway, or Tally
  integrations.
- Ares does not yet prove production-grade TLS/auth rollout by itself.
- Ares still assumes local operator ownership of runtime state and local disk.
