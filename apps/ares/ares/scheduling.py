"""Hermes cron prompt generation for Ares workflows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from apps.ares.ares.profiles import ClientProfile


class CronJobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    schedule: str
    workflow: str
    prompt: str


def _prompt(profile: ClientProfile, workflow: str) -> str:
    return (
        f"Run Ares workflow {workflow!r} for client {profile.client_slug!r}. "
        f"Use: hermes ares run-workflow --client {profile.client_slug} --workflow {workflow}. "
        "Return the owner-facing result only. Never send customer messages, modify ledgers, "
        "place supplier orders, or change credit terms unless a separate owner approval exists."
    )


def build_cron_job_specs(profile: ClientProfile) -> list[CronJobSpec]:
    """Create concrete autonomous schedule specs for Hermes cron."""
    return [
        CronJobSpec(name=f"ares-{profile.client_slug}-daily-brief", schedule="0 9 * * *", workflow="daily-brief", prompt=_prompt(profile, "daily-brief")),
        CronJobSpec(name=f"ares-{profile.client_slug}-payment-radar", schedule="0 14 * * *", workflow="payment-radar", prompt=_prompt(profile, "payment-radar")),
        CronJobSpec(name=f"ares-{profile.client_slug}-evening-cycle", schedule="0 18 * * *", workflow="autonomous-cycle", prompt=(
            f"Run the Ares autonomous cycle for client {profile.client_slug!r}. "
            f"Use: hermes ares autonomous-cycle --client {profile.client_slug}. "
            "Ingest new local exports/messages, update memory, draft approvals, and return the owner-facing approval summary. "
            "Do not execute customer-facing or ledger-impacting actions without owner approval."
        )),
        CronJobSpec(name=f"ares-{profile.client_slug}-weekly-war-room", schedule="0 10 * * 1", workflow="weekly-war-room", prompt=_prompt(profile, "weekly-war-room")),
    ]


def build_cron_prompts(profile: ClientProfile) -> list[str]:
    """Create self-contained prompts suitable for Hermes cron jobs."""
    return [spec.prompt for spec in build_cron_job_specs(profile)]
