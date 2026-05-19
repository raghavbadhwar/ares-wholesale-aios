from __future__ import annotations

from pathlib import Path

from apps.ares.ares import cli as ares_cli
from apps.ares.ares.cli import build_chat_context, build_chat_launch
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_build_chat_context_writes_company_brain_instructions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile = ClientProfile(
        client_slug="demo-wholesaler",
        business_name="Demo Wholesale",
        owner_name="Raghav",
        language_preference="english_hinglish",
    )
    write_client_profile(profile)

    context_path = build_chat_context(profile)

    assert context_path.name == "AGENTS.md"
    assert context_path.parent == tmp_path / ".ares" / "clients" / "demo-wholesaler" / "chat"
    text = context_path.read_text(encoding="utf-8")
    assert "You are Ares, the company brain for Demo Wholesale" in text
    assert "Client slug: demo-wholesaler" in text
    assert "ares autonomous-cycle --client demo-wholesaler" in text
    assert "approval-first" in text.lower()


def test_build_chat_launch_uses_client_context_directory_and_query(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    profile = ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner")
    context_path = build_chat_context(profile)

    launch = build_chat_launch(
        profile,
        context_path,
        query="what happened today?",
        model="openai/gpt-5.5",
        provider="openai-codex",
        toolsets="terminal,file",
    )

    assert launch.cwd == context_path.parent
    assert launch.command[:3] == [launch.command[0], "-m", "hermes_cli.main"]
    assert launch.command[3:5] == ["chat", "--query"]
    assert "what happened today?" in launch.command
    assert launch.command[-6:] == ["--model", "openai/gpt-5.5", "--provider", "openai-codex", "--toolsets", "terminal,file"]
    assert launch.env["ARES_CLIENT"] == "demo"
    assert launch.env["ARES_BUSINESS_NAME"] == "Demo"
    assert launch.env["ARES_HOME"] == str(tmp_path / ".ares")
    assert launch.env["ARES_CHAT_CONTEXT"] == str(context_path)
    assert launch.env["HERMES_SKIN"] == "ares"
    assert str(Path(ares_cli.__file__).resolve().parents[3]) in launch.env["PYTHONPATH"]
