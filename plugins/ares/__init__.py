"""Ares Wholesale AIOS Hermes plugin.

This plugin makes the Ares app feel native to Hermes by registering:
- `hermes ares ...` as a top-level CLI command
- `/ares ...` as a gateway/CLI slash command for owner-facing mobile flows
"""

from __future__ import annotations

import argparse
import io
import shlex
from contextlib import redirect_stdout
from typing import Any

from apps.ares.ares.cli import ares_command, register_cli


def register(ctx: Any) -> None:
    """Register Ares CLI and slash-command entry points."""
    ctx.register_cli_command(
        name="ares",
        help="Ares Wholesale AIOS workflows and setup",
        description=(
            "Run Ares wholesaler workflows: onboarding, autonomous cycle, "
            "mobile approvals, Drive manifest sync, and cron prompt generation."
        ),
        setup_fn=register_cli,
        handler_fn=ares_command,
    )
    ctx.register_command(
        name="ares",
        handler=_slash_ares,
        description="Run Ares mobile approval and workflow commands from gateway chat",
        args_hint="<client> <approvals|cycle|reply ...>",
    )


def _slash_ares(raw_args: str) -> str:
    """Handle `/ares` gateway commands without routing through the LLM.

    Supported forms:
      /ares <client> approvals
      /ares <client> cycle
      /ares <client> reply approve appr_123
      /ares <client> reply haan appr_123
    """
    try:
        parts = shlex.split(raw_args or "")
    except ValueError as exc:
        return f"Ares error: could not parse command: {exc}"

    if len(parts) < 2 or parts[0] in {"-h", "--help", "help"}:
        return _slash_usage()

    client = parts[0]
    action = parts[1].lower()

    if action in {"approvals", "approval", "pending"}:
        argv = ["mobile-approvals", "--client", client]
    elif action in {"cycle", "run", "autonomous", "brief"}:
        argv = ["autonomous-cycle", "--client", client]
    elif action in {"reply", "respond"}:
        reply = " ".join(parts[2:]).strip()
        if not reply:
            return "Ares error: missing reply text. Example: /ares demo reply approve appr_123"
        argv = ["mobile-reply", "--client", client, "--reply", reply]
    else:
        # Treat the rest as a mobile approval reply for WhatsApp-like usage.
        reply = " ".join(parts[1:]).strip()
        argv = ["mobile-reply", "--client", client, "--reply", reply]

    parser = argparse.ArgumentParser(prog="/ares", add_help=False)
    register_cli(parser)
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return _slash_usage()

    # Reuse the CLI execution path and capture the text it would print in a
    # terminal so the gateway can send the same result back to the owner.
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = ares_command(args)
    text = output.getvalue().strip()
    if text:
        return text
    if exit_code == 0:
        return "Ares command completed."
    return f"Ares command failed with exit code {exit_code}."


def _slash_usage() -> str:
    return (
        "Usage:\n"
        "  /ares <client> approvals\n"
        "  /ares <client> cycle\n"
        "  /ares <client> reply approve appr_123\n"
        "  /ares <client> reply haan appr_123"
    )
