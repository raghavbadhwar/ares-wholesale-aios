"""CLI entrypoint for Ares workflows."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.autonomy.runner import run_autonomous_cycle, run_morning_run
from apps.ares.ares.connectors.auto_ingest import validate_local_inputs
from apps.ares.ares.connectors.drive_sync import sync_drive_manifest
from apps.ares.ares.connectors.export_parser import parse_outstanding_report, parse_stock_report
from apps.ares.ares.data.factory import create_repository_for_profile
from apps.ares.ares.execution.actions import ActionExecutor
from apps.ares.ares.face.mobile_approval import MobileApprovalAdapter
from apps.ares.ares.face.operator_shell import build_operator_shell, render_operator_shell
from apps.ares.ares.face.owner_chat import handle_owner_reply
from apps.ares.ares.orchestrator.router import AresRouter, WORKFLOW_ALIASES
from apps.ares.ares.paths import get_ares_home, normalize_client_slug
from apps.ares.ares.profiles import ClientProfile, load_client_profile, write_client_profile
from apps.ares.ares.scheduling import build_cron_job_specs, build_cron_prompts
from apps.ares.ares.workflows.benchmark_audit import build_benchmark_completion_audit
from apps.ares.ares.workflows.gstr1 import prepare_gstr1_return
from apps.ares.ares.workflows.integration_preflight import build_integration_prerequisite_preflight


def register_cli(subparser: argparse.ArgumentParser) -> None:
    actions = subparser.add_subparsers(dest="ares_action")

    chat_p = actions.add_parser("chat", help="Chat interactively with the Ares company brain")
    chat_p.add_argument("--client", required=True, help="Client slug")
    chat_p.add_argument("-q", "--query", default="", help="Single query, then exit")
    chat_p.add_argument("-m", "--model", default="", help="Optional model override")
    chat_p.add_argument("--provider", default="", help="Optional provider override")
    chat_p.add_argument("-t", "--toolsets", default="", help="Optional comma-separated toolsets")
    chat_p.add_argument("--tui", action="store_true", help="Launch Hermes TUI for Ares chat")
    chat_p.add_argument("--yolo", action="store_true", help="Bypass dangerous command approvals")

    run_p = actions.add_parser("run-workflow", help="Run an Ares workflow")
    run_p.add_argument("--client", required=True, help="Client slug")
    run_p.add_argument("--workflow", required=True, help="daily-brief, payment-radar, stock-radar, weekly-war-room")
    run_p.add_argument("--outstanding-csv", default="", help="Optional outstanding export CSV")
    run_p.add_argument("--stock-csv", default="", help="Optional stock export CSV")
    run_p.add_argument("--json", action="store_true", help="Print JSON payload")

    gstr1_p = actions.add_parser("prepare-gstr1", help="Prepare a local approval-gated GSTR-1 draft")
    gstr1_p.add_argument("--client", required=True)
    gstr1_p.add_argument("--period", required=True, help="Return period in YYYY-MM format")
    gstr1_p.add_argument("--seller-gstin", required=True)
    gstr1_p.add_argument("--requested-by", default="owner")
    gstr1_p.add_argument("--json", action="store_true")

    onboard_p = actions.add_parser("onboard-client", help="Create a real local Ares client profile")
    onboard_p.add_argument("--client", required=True)
    onboard_p.add_argument("--business-name", required=True)
    onboard_p.add_argument("--owner-name", required=True)
    onboard_p.add_argument("--language", default="english_hinglish")
    onboard_p.add_argument("--timezone", default="Asia/Kolkata")

    sample_p = actions.add_parser("create-sample-client", help="Create a local sample client profile")
    sample_p.add_argument("--client", required=True)
    sample_p.add_argument("--business-name", required=True)
    sample_p.add_argument("--owner-name", required=True)

    setup_p = actions.add_parser("setup", help="One-command local setup for an Ares wholesaler pilot")
    setup_p.add_argument("--client", required=True)
    setup_p.add_argument("--business-name", required=True)
    setup_p.add_argument("--owner-name", required=True)
    setup_p.add_argument("--language", default="english_hinglish")
    setup_p.add_argument("--timezone", default="Asia/Kolkata")
    setup_p.add_argument("--ares-home", default="", help="Optional ARES_HOME path to show in generated commands")
    setup_p.add_argument("--sample", action="store_true", help="Create a sample/demo profile instead of a real client profile")

    show_p = actions.add_parser("show-client", help="Show client profile")
    show_p.add_argument("--client", required=True)
    actions.add_parser("list-clients", help="List local Ares clients")
    actions.add_parser("list-workflows", help="List workflows")

    approval_p = actions.add_parser("approval-center", help="Show pending approvals")
    approval_p.add_argument("--client", required=True)

    shell_p = actions.add_parser("operator-shell", help="Show local Ares operator shell")
    shell_p.add_argument("--client", required=True)
    shell_p.add_argument("--json", action="store_true")

    reply_p = actions.add_parser("owner-reply", help="Process owner approval reply and execute approved action")
    reply_p.add_argument("--client", required=True)
    reply_p.add_argument("--approval-id", required=True)
    reply_p.add_argument("--reply", required=True, help="approve, reject, edit <text>, ask later")
    reply_p.add_argument("--decided-by", default="owner")
    reply_p.add_argument("--json", action="store_true")

    auto_p = actions.add_parser("autonomous-cycle", help="Run eyes + memory + draft-actions + owner approval summary")
    auto_p.add_argument("--client", required=True)
    auto_p.add_argument("--json", action="store_true")

    validate_p = actions.add_parser("validate-inputs", help="Validate dropped exports and inbox files before running workflows")
    validate_p.add_argument("--client", required=True)
    validate_p.add_argument("--json", action="store_true")

    morning_p = actions.add_parser("morning-run", help="Run ingestion + daily brief + owner approval output for pilot ops")
    morning_p.add_argument("--client", required=True)
    morning_p.add_argument("--json", action="store_true")

    mobile_p = actions.add_parser("mobile-approvals", help="Print Telegram/WhatsApp-friendly approval prompt")
    mobile_p.add_argument("--client", required=True)

    mobile_reply_p = actions.add_parser("mobile-reply", help="Process Telegram/WhatsApp-style approval reply")
    mobile_reply_p.add_argument("--client", required=True)
    mobile_reply_p.add_argument("--reply", required=True, help="e.g. approve appr_xxx, reject appr_xxx, edit appr_xxx <text>")
    mobile_reply_p.add_argument("--decided-by", default="owner")
    mobile_reply_p.add_argument("--json", action="store_true")

    drive_p = actions.add_parser("sync-drive-manifest", help="Sync Drive manifest files into Ares and ingest them")
    drive_p.add_argument("--client", required=True)
    drive_p.add_argument("--manifest", required=True)
    drive_p.add_argument("--json", action="store_true")

    cron_p = actions.add_parser("print-cron-prompts", help="Print self-contained Hermes cron prompts")
    cron_p.add_argument("--client", required=True)

    cron_specs_p = actions.add_parser("print-cron-specs", help="Print JSON Hermes cron schedule specs")
    cron_specs_p.add_argument("--client", required=True)

    actions.add_parser("schedules", help="Print default workflow schedules")

    preflight_p = actions.add_parser("integration-preflight", help="Check external integration sandbox prerequisites")
    preflight_p.add_argument("--json", action="store_true", help="Print JSON payload")
    preflight_p.add_argument(
        "--confirm-safe-sandbox",
        action="append",
        default=[],
        help="Provider key explicitly confirmed safe for sandbox adapter tests",
    )

    audit_p = actions.add_parser("benchmark-audit", help="Report benchmark coverage and production blockers")
    audit_p.add_argument("--latest-local-test-result", default="not supplied", help="Latest local tests/ares result string")
    audit_p.add_argument("--json", action="store_true", help="Print JSON payload")
    subparser.set_defaults(func=ares_command)


def ares_command(args: argparse.Namespace) -> int:
    action = getattr(args, "ares_action", None)
    try:
        if action == "chat":
            profile = load_client_profile(args.client)
            context_path = build_chat_context(profile)
            launch = build_chat_launch(
                profile,
                context_path,
                query=getattr(args, "query", ""),
                model=getattr(args, "model", ""),
                provider=getattr(args, "provider", ""),
                toolsets=getattr(args, "toolsets", ""),
                tui=getattr(args, "tui", False),
                yolo=getattr(args, "yolo", False),
            )
            return run_chat_launch(launch)
        if action == "run-workflow":
            result = _run_workflow(args)
            print(json.dumps(result["payload"], indent=2, default=str) if getattr(args, "json", False) else result["message"])
            return 0
        if action == "prepare-gstr1":
            result = _prepare_gstr1(args)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _render_gstr1_summary(result))
            return 0
        if action in {"create-sample-client", "onboard-client"}:
            slug = normalize_client_slug(args.client)
            profile = ClientProfile(
                client_slug=slug,
                business_name=args.business_name,
                owner_name=args.owner_name,
                language_preference=getattr(args, "language", "english_hinglish"),
                timezone=getattr(args, "timezone", "Asia/Kolkata"),
            )
            path = write_client_profile(profile)
            print(f"Created Ares client profile: {path}")
            return 0
        if action == "setup":
            slug = normalize_client_slug(args.client)
            profile = ClientProfile(
                client_slug=slug,
                business_name=args.business_name,
                owner_name=args.owner_name,
                language_preference=args.language,
                timezone=args.timezone,
            )
            path = write_client_profile(profile)
            ares_home = args.ares_home or str(get_ares_home())
            print(_setup_success_message(profile.client_slug, path, ares_home, sample=args.sample))
            return 0
        if action == "list-clients":
            clients_root = get_ares_home() / "clients"
            clients = sorted(p.name for p in clients_root.glob("*") if (p / "profile.yaml").exists()) if clients_root.exists() else []
            print("\n".join(clients) if clients else "No Ares clients found. Run: hermes ares onboard-client --client demo --business-name Demo --owner-name Owner")
            return 0
        if action == "show-client":
            print(load_client_profile(args.client).model_dump_json(indent=2))
            return 0
        if action == "list-workflows":
            print("\n".join(sorted(WORKFLOW_ALIASES)))
            return 0
        if action == "approval-center":
            setattr(args, "workflow", "approval-center")
            setattr(args, "outstanding_csv", "")
            setattr(args, "stock_csv", "")
            setattr(args, "json", False)
            print(_run_workflow(args)["message"])
            return 0
        if action == "operator-shell":
            profile = load_client_profile(args.client)
            repo = create_repository_for_profile(profile)
            approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
            shell = build_operator_shell(profile=profile, repository=repo, approvals=approvals)
            print(json.dumps(shell, indent=2, default=str) if getattr(args, "json", False) else render_operator_shell(shell))
            return 0
        if action == "owner-reply":
            profile = load_client_profile(args.client)
            repo = create_repository_for_profile(profile)
            approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
            result = handle_owner_reply(
                args.reply,
                approvals=approvals,
                executor=ActionExecutor(repo),
                approval_id=args.approval_id,
                decided_by=args.decided_by,
            )
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _owner_reply_message(result))
            return 0
        if action == "autonomous-cycle":
            result = run_autonomous_cycle(args.client)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else result["owner_message"])
            return 0
        if action == "validate-inputs":
            result = validate_local_inputs(client_id=args.client)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _render_validation_summary(result))
            return 1 if result["blocking_errors"] else 0
        if action == "morning-run":
            result = run_morning_run(args.client)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _render_morning_run_summary(result))
            return 0
        if action == "mobile-approvals":
            profile = load_client_profile(args.client)
            repo = create_repository_for_profile(profile)
            approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
            print(MobileApprovalAdapter(repo, approvals).render_pending_prompt())
            return 0
        if action == "mobile-reply":
            profile = load_client_profile(args.client)
            repo = create_repository_for_profile(profile)
            approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
            result = MobileApprovalAdapter(repo, approvals).handle_reply(args.reply, decided_by=args.decided_by)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _owner_reply_message(result))
            return 0
        if action == "sync-drive-manifest":
            profile = load_client_profile(args.client)
            repo = create_repository_for_profile(profile)
            result = sync_drive_manifest(client_id=profile.client_slug, manifest_path=Path(args.manifest), repository=repo)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else f"Synced {result['files_synced']} files. Imported {result['ingestion']['exports_imported']} exports and captured {result['ingestion']['orders_captured']} orders.")
            return 0
        if action == "print-cron-prompts":
            profile = load_client_profile(args.client)
            print("\n---\n".join(build_cron_prompts(profile)))
            return 0
        if action == "print-cron-specs":
            profile = load_client_profile(args.client)
            print(json.dumps([spec.model_dump() for spec in build_cron_job_specs(profile)], indent=2))
            return 0
        if action == "schedules":
            schedule_path = Path(__file__).resolve().parents[1] / "config" / "workflow_schedules.yaml"
            print(schedule_path.read_text(encoding="utf-8"))
            return 0
        if action == "integration-preflight":
            result = build_integration_prerequisite_preflight(
                safe_test_environment_confirmations=set(getattr(args, "confirm_safe_sandbox", []) or [])
            )
            print(
                json.dumps(result, indent=2, default=str)
                if getattr(args, "json", False)
                else _render_integration_preflight(result)
            )
            return 0 if result["status"] in {"ready", "partial_ready"} else 1
        if action == "benchmark-audit":
            result = build_benchmark_completion_audit(latest_local_test_result=args.latest_local_test_result)
            print(json.dumps(result, indent=2, default=str) if getattr(args, "json", False) else _render_benchmark_audit(result))
            return 0 if result["ship_ready"] else 1
    except FileNotFoundError as exc:
        print(
            f"Ares error: {exc}\n"
            f"Create it with: hermes ares onboard-client --client {getattr(args, 'client', '<slug>')} --business-name '<Business>' --owner-name '<Owner>'"
        )
        return 1
    except Exception as exc:
        print(f"Ares error: {exc}")
        return 1
    print("Usage: hermes ares {chat|setup|run-workflow|prepare-gstr1|onboard-client|list-clients|show-client|list-workflows|approval-center|operator-shell|owner-reply|autonomous-cycle|validate-inputs|morning-run|mobile-approvals|mobile-reply|sync-drive-manifest|print-cron-prompts|print-cron-specs|schedules|integration-preflight|benchmark-audit}")
    return 2


@dataclass(frozen=True)
class ChatLaunch:
    command: list[str]
    cwd: Path
    env: dict[str, str]


def build_chat_context(profile: ClientProfile) -> Path:
    """Write an AGENTS.md file that turns Hermes chat into an Ares company brain."""
    client_root = get_ares_home() / "clients" / profile.client_slug
    chat_dir = client_root / "chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    context_path = chat_dir / "AGENTS.md"
    repo_root = Path(__file__).resolve().parents[3]
    ares_home = get_ares_home()
    context_path.write_text(
        f"""# Ares Company Brain Session

You are Ares, the company brain for {profile.business_name}.

Client details:
- Client slug: {profile.client_slug}
- Business name: {profile.business_name}
- Owner name: {profile.owner_name}
- Language preference: {profile.language_preference}
- Timezone: {profile.timezone}
- Ares home: {ares_home}
- Ares repo: {repo_root}

Operating rules:
- Be concise, practical, and use simple Indian English.
- Treat Ares as an approval-first business brain for an Indian wholesaler/distributor.
- Never claim a workflow ran unless you actually run the relevant command and inspect the result.
- For money, ledger-impacting actions, external customer/supplier messages, credit holds, or dispatch decisions: draft first, ask owner approval, then execute only after approval.
- Prefer owner-friendly summaries: payment radar, pending orders, low stock, supplier issues, and next actions.

Useful Ares commands:
- ares autonomous-cycle --client {profile.client_slug}
- ares mobile-approvals --client {profile.client_slug}
- ares approval-center --client {profile.client_slug}
- ares run-workflow --client {profile.client_slug} --workflow daily-brief
- ares run-workflow --client {profile.client_slug} --workflow payment-radar
- ares run-workflow --client {profile.client_slug} --workflow stock-radar
- ares mobile-reply --client {profile.client_slug} --reply \"haan appr_xxx\"
- ares print-cron-specs --client {profile.client_slug}

If the `ares` wrapper is not on PATH inside a tool shell, run from the repo instead:
cd {repo_root} && ARES_HOME={ares_home} uv run hermes ares <command> --client {profile.client_slug}

When the owner asks broad questions like "what happened today?" or "what should I do now?", run the autonomous cycle or daily brief first, then summarize the result.
""",
        encoding="utf-8",
    )
    return context_path


def build_chat_launch(
    profile: ClientProfile,
    context_path: Path,
    *,
    query: str = "",
    model: str = "",
    provider: str = "",
    toolsets: str = "",
    tui: bool = False,
    yolo: bool = False,
) -> ChatLaunch:
    """Build the Hermes chat command for an Ares client without executing it."""
    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["ARES_CLIENT"] = profile.client_slug
    env["ARES_BUSINESS_NAME"] = profile.business_name
    env["ARES_HOME"] = str(get_ares_home())
    env["ARES_CHAT_CONTEXT"] = str(context_path)
    env["PYTHONPATH"] = _prepend_path(env.get("PYTHONPATH", ""), str(repo_root))

    bin_dir = get_ares_home() / "bin"
    if bin_dir.exists():
        env["PATH"] = _prepend_path(env.get("PATH", ""), str(bin_dir))

    command = [sys.executable, "-m", "hermes_cli.main", "chat"]
    if query:
        command.extend(["--query", query])
    if tui:
        command.append("--tui")
    if yolo:
        command.append("--yolo")
    if model:
        command.extend(["--model", model])
    if provider:
        command.extend(["--provider", provider])
    if toolsets:
        command.extend(["--toolsets", toolsets])
    return ChatLaunch(command=command, cwd=context_path.parent, env=env)


def run_chat_launch(launch: ChatLaunch) -> int:
    """Run Ares chat. Interactive mode replaces the process; query mode returns."""
    if "--query" not in launch.command:
        os.execvpe(launch.command[0], launch.command, launch.env)
    completed = subprocess.run(launch.command, cwd=launch.cwd, env=launch.env, check=False)
    return int(completed.returncode)


def _prepend_path(existing: str, new_path: str) -> str:
    if not existing:
        return new_path
    parts = existing.split(os.pathsep)
    if new_path in parts:
        return existing
    return os.pathsep.join([new_path, existing])


def _run_workflow(args: argparse.Namespace) -> dict:
    profile = load_client_profile(args.client)
    repo = create_repository_for_profile(profile)
    if args.outstanding_csv:
        for invoice in parse_outstanding_report(Path(args.outstanding_csv)):
            repo.upsert_invoice(invoice)
    if args.stock_csv:
        for record in parse_stock_report(Path(args.stock_csv)):
            repo.upsert_stock_record(record)
    approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
    router = AresRouter(repo, approvals, client_id=profile.client_slug, language=profile.language_preference)
    return router.run_workflow(args.workflow)


def _prepare_gstr1(args: argparse.Namespace) -> dict:
    profile = load_client_profile(args.client)
    repo = create_repository_for_profile(profile)
    approvals = ApprovalService(repo, required_actions=set(profile.approval_preferences.required_actions) or None)
    return prepare_gstr1_return(
        repository=repo,
        approvals=approvals,
        client_id=profile.client_slug,
        period=args.period,
        seller_gstin=args.seller_gstin,
        requested_by=args.requested_by,
    )


def _owner_reply_message(result: dict) -> str:
    decision = result.get("decision", "unknown")
    if decision == "approved":
        execution = result.get("execution", {})
        return f"Approved and executed. Status: {execution.get('status', 'unknown')}"
    if decision == "rejected":
        return "Rejected. No action executed."
    if decision == "edited":
        return "Edited. Approval marked for review; no action executed."
    return str(result.get("message", "Approval kept pending."))


def _render_gstr1_summary(result: dict) -> str:
    summary = result["summary"]
    lines = [
        f"GSTR-1 draft prepared for {result['period']}",
        f"Status: {result['status']}",
        f"Pending approval: {result['approval_id']}",
        f"B2B invoices: {summary['b2b_invoices']}",
        f"B2CL invoices: {summary['b2cl_invoices']}",
        f"B2CS groups: {summary['b2cs_groups']}",
        f"HSN rows: {summary['hsn_rows']}",
        f"Taxable value: INR {summary['taxable_value']:.2f}",
        f"Tax amount: INR {summary['tax_amount']:.2f}",
        f"Validation errors: {summary['validation_errors']}",
        result["audit"]["limitation"],
    ]
    return "\n".join(lines)


def _render_morning_run_summary(result: dict) -> str:
    metrics = result["metrics"]
    return "\n".join(
        [
            f"Ares morning run for {result['client_id']}",
            f"Files ingested: {metrics['files_ingested']}",
            f"Overdue invoices: {metrics['overdue_invoices']}",
            f"Low-stock items: {metrics['low_stock_items']}",
            f"Approvals created: {metrics['approvals_created']}",
            "",
            "Operator brief:",
            result["daily_brief_text"],
            "",
            "Owner message:",
            result["owner_message"],
        ]
    )


def _render_validation_summary(result: dict) -> str:
    lines = [
        f"Ares input validation for {result['client_id']}",
        f"Parseable exports: {result['parseable_exports']}",
        f"Unparseable exports: {result['unparseable_exports']}",
        f"Inbox messages: {result['inbox_messages']}",
        f"Blocking issues: {len(result['blocking_errors'])}",
    ]
    if result["exports_found"] == 0:
        lines.append("No export files found")
    if result["inbox_messages"] == 0:
        lines.append("No inbox messages found")
    if result["blocking_errors"]:
        lines.append("Issues:")
        lines.extend(f"- {error}" for error in result["blocking_errors"])
    else:
        lines.append("Inputs look ready for processing.")
    return "\n".join(lines)


def _render_integration_preflight(result: dict) -> str:
    lines = [
        "Ares external integration preflight",
        f"Status: {result['status']}",
        f"Ready providers: {result['ready_provider_count']}",
        f"Blocked providers: {result['blocked_provider_count']}",
        "",
        "Providers:",
    ]
    for provider, status in result["providers"].items():
        missing = ", ".join(status["missing_env_names"]) if status["missing_env_names"] else "none"
        lines.extend(
            [
                f"- {provider}: {status['status']}",
                f"  missing env names: {missing}",
                f"  safe sandbox confirmed: {status['safe_test_environment_confirmed']}",
            ]
        )
    lines.extend(["", result["audit"]["limitation"]])
    return "\n".join(lines)


def _render_benchmark_audit(result: dict) -> str:
    lines = [
        "Ares benchmark audit",
        f"Feature rows covered locally/contract-only: {result['local_or_contract_rows_covered']}/{result['feature_rows_total']}",
        f"Latest local test result: {result['latest_local_test_result']}",
        f"Benchmark parity: {result['benchmark_parity']}",
        f"Ship ready: {result['ship_ready']}",
        "",
        "Production blockers:",
    ]
    lines.extend(f"- {blocker}" for blocker in result["production_blockers"])
    lines.extend(["", "Done-state gates:"])
    lines.extend(f"- {gate['gate']}: {gate['status']}" for gate in result["done_state_gates"])
    lines.extend(["", result["audit"]["limitation"]])
    return "\n".join(lines)


def _setup_success_message(client: str, profile_path: Path, ares_home: str, *, sample: bool = False) -> str:
    label = "sample" if sample else "client"
    root = profile_path.parent
    exports_dir = root / "exports"
    inbox_dir = root / "inbox"
    reports_dir = root / "reports"
    return f"""Ares setup complete for {label}: {client}

Profile:
  {profile_path}

Ares home:
  {ares_home}

Drop exports into:
  {exports_dir}

Drop forwarded messages into:
  {inbox_dir}

Reports folder:
  {reports_dir}

Next steps:
  1. ares validate-inputs --client {client}
  2. ares morning-run --client {client}
  3. ares mobile-approvals --client {client}

Wrapper commands:
  ares chat --client {client}
  ares validate-inputs --client {client}
  ares morning-run --client {client}
  ares autonomous-cycle --client {client}
  ares mobile-approvals --client {client}
  ares mobile-reply --client {client} --reply "haan appr_xxx"
  ares print-cron-specs --client {client}

From the repo without wrappers, use:
  ARES_HOME={ares_home} uv run hermes ares validate-inputs --client {client}
  ARES_HOME={ares_home} uv run hermes ares morning-run --client {client}
  ARES_HOME={ares_home} uv run hermes ares mobile-approvals --client {client}

Gateway:
  ares-hermes gateway setup
  ares-hermes gateway run
""".strip()


def main() -> int:
    parser = argparse.ArgumentParser(prog="ares")
    register_cli(parser)
    return ares_command(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
