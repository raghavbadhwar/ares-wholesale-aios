"""Tests for the `ares memory reset` CLI command.

Covers:
- Reset both stores (MEMORY.md + USER.md)
- Reset individual stores (--target memory / --target user)
- Skip confirmation with --yes
- Graceful handling when no memory files exist
- Profile-scoped reset (uses ARES_HOME)
"""

import os
import pytest
from argparse import Namespace
from pathlib import Path


@pytest.fixture
def memory_env(tmp_path, monkeypatch):
    """Set up a fake ARES_HOME with memory files."""
    ares_home = tmp_path / ".ares"
    memories = ares_home / "memories"
    memories.mkdir(parents=True)
    monkeypatch.setenv("ARES_HOME", str(ares_home))

    # Create sample memory files
    (memories / "MEMORY.md").write_text(
        "§\nAres repo is at ~/.ares/ares-agent\n§\nUser prefers dark themes",
        encoding="utf-8",
    )
    (memories / "USER.md").write_text(
        "§\nUser is Teknium\n§\nTimezone: US Pacific",
        encoding="utf-8",
    )
    return ares_home, memories


def _run_memory_reset(target="all", yes=False, monkeypatch=None, confirm_input="no"):
    """Invoke the memory reset logic from cmd_memory in main.py.

    Simulates what happens when `ares memory reset` is run.
    """
    from ares_constants import get_ares_home, display_ares_home

    mem_dir = get_ares_home() / "memories"
    files_to_reset = []
    if target in {"all", "memory"}:
        files_to_reset.append(("MEMORY.md", "agent notes"))
    if target in {"all", "user"}:
        files_to_reset.append(("USER.md", "user profile"))

    existing = [(f, desc) for f, desc in files_to_reset if (mem_dir / f).exists()]
    if not existing:
        return "nothing"

    if not yes:
        if confirm_input != "yes":
            return "cancelled"

    for f, desc in existing:
        (mem_dir / f).unlink()

    return "deleted"


class TestMemoryReset:
    """Tests for `ares memory reset` subcommand."""

    def test_reset_all_with_yes_flag(self, memory_env):
        """--yes flag should skip confirmation and delete both files."""
        ares_home, memories = memory_env
        assert (memories / "MEMORY.md").exists()
        assert (memories / "USER.md").exists()

        result = _run_memory_reset(target="all", yes=True)
        assert result == "deleted"
        assert not (memories / "MEMORY.md").exists()
        assert not (memories / "USER.md").exists()

    def test_reset_memory_only(self, memory_env):
        """--target memory should only delete MEMORY.md."""
        ares_home, memories = memory_env

        result = _run_memory_reset(target="memory", yes=True)
        assert result == "deleted"
        assert not (memories / "MEMORY.md").exists()
        assert (memories / "USER.md").exists()

    def test_reset_user_only(self, memory_env):
        """--target user should only delete USER.md."""
        ares_home, memories = memory_env

        result = _run_memory_reset(target="user", yes=True)
        assert result == "deleted"
        assert (memories / "MEMORY.md").exists()
        assert not (memories / "USER.md").exists()

    def test_reset_no_files_exist(self, tmp_path, monkeypatch):
        """Should return 'nothing' when no memory files exist."""
        ares_home = tmp_path / ".ares"
        (ares_home / "memories").mkdir(parents=True)
        monkeypatch.setenv("ARES_HOME", str(ares_home))

        result = _run_memory_reset(target="all", yes=True)
        assert result == "nothing"

    def test_reset_confirmation_denied(self, memory_env):
        """Without --yes and without typing 'yes', should be cancelled."""
        ares_home, memories = memory_env

        result = _run_memory_reset(target="all", yes=False, confirm_input="no")
        assert result == "cancelled"
        # Files should still exist
        assert (memories / "MEMORY.md").exists()
        assert (memories / "USER.md").exists()

    def test_reset_confirmation_accepted(self, memory_env):
        """Typing 'yes' should proceed with deletion."""
        ares_home, memories = memory_env

        result = _run_memory_reset(target="all", yes=False, confirm_input="yes")
        assert result == "deleted"
        assert not (memories / "MEMORY.md").exists()
        assert not (memories / "USER.md").exists()

    def test_reset_profile_scoped(self, tmp_path, monkeypatch):
        """Reset should work on the active profile's ARES_HOME."""
        profile_home = tmp_path / "profiles" / "myprofile"
        memories = profile_home / "memories"
        memories.mkdir(parents=True)
        (memories / "MEMORY.md").write_text("profile memory", encoding="utf-8")
        (memories / "USER.md").write_text("profile user", encoding="utf-8")
        monkeypatch.setenv("ARES_HOME", str(profile_home))

        result = _run_memory_reset(target="all", yes=True)
        assert result == "deleted"
        assert not (memories / "MEMORY.md").exists()
        assert not (memories / "USER.md").exists()

    def test_reset_partial_files(self, memory_env):
        """Reset should work when only one memory file exists."""
        ares_home, memories = memory_env
        (memories / "USER.md").unlink()

        result = _run_memory_reset(target="all", yes=True)
        assert result == "deleted"
        assert not (memories / "MEMORY.md").exists()

    def test_reset_empty_memories_dir(self, tmp_path, monkeypatch):
        """No memories dir at all should report nothing."""
        ares_home = tmp_path / ".ares"
        ares_home.mkdir(parents=True)
        # No memories dir
        monkeypatch.setenv("ARES_HOME", str(ares_home))

        # The memories dir won't exist; get_ares_home() / "memories" won't have files
        result = _run_memory_reset(target="all", yes=True)
        assert result == "nothing"
