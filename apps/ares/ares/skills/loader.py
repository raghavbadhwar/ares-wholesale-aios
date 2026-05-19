"""Load Ares skill markdown for verticals and workflows."""

from __future__ import annotations

from pathlib import Path

from apps.ares.ares.paths import client_root

SKILL_DIR = Path(__file__).resolve().parent / "wholesale_india"

VERTICAL_SKILLS = {
    "wholesale_india": [
        "payment_collection",
        "order_management",
        "inventory_radar",
        "customer_memory",
        "daily_briefing",
    ]
}

WORKFLOW_SKILLS = {
    "payment-radar": ["payment_collection", "customer_memory"],
    "daily-brief": ["daily_briefing", "payment_collection", "inventory_radar", "customer_memory"],
    "order-capture": ["order_management", "customer_memory"],
    "stock-radar": ["inventory_radar"],
    "weekly-war-room": ["daily_briefing", "payment_collection", "inventory_radar"],
}


def _read_skill(name: str) -> str:
    path = SKILL_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Ares skill not found: {path}")
    return path.read_text(encoding="utf-8")


def load_vertical_skill_pack(vertical: str) -> dict[str, str]:
    names = VERTICAL_SKILLS.get(vertical)
    if not names:
        raise KeyError(f"Unknown Ares vertical: {vertical}")
    return {name: _read_skill(name) for name in names}


def load_workflow_skills(workflow_name: str) -> dict[str, str]:
    names = WORKFLOW_SKILLS.get(workflow_name)
    if not names:
        raise KeyError(f"Unknown Ares workflow: {workflow_name}")
    return {name: _read_skill(name) for name in names}


def load_client_custom_skills(client_slug: str) -> dict[str, str]:
    skills_dir = client_root(client_slug) / "skills"
    if not skills_dir.exists():
        return {}
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(skills_dir.glob("*.md"))}

