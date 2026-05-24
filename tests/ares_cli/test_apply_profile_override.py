"""Regression tests for _apply_profile_override ARES_HOME guard (issue #22502).

When ARES_HOME is set to the ares root (e.g. systemd hardcodes
ARES_HOME=/root/.ares), _apply_profile_override must still read
active_profile and update ARES_HOME to the profile directory.

When ARES_HOME is already a profile directory (.../profiles/<name>),
_apply_profile_override must trust it and return without re-reading
active_profile (child-process inheritance contract).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def _run_apply_profile_override(
    tmp_path, monkeypatch, *, ares_home: str | None, active_profile: str | None,
    argv: list[str] | None = None,
):
    """Run _apply_profile_override in isolation.

    Returns the value of os.environ["ARES_HOME"] after the call,
    or None if unset.
    """
    ares_root = tmp_path / ".ares"
    ares_root.mkdir(parents=True, exist_ok=True)

    if active_profile is not None:
        (ares_root / "active_profile").write_text(active_profile)

    if active_profile and active_profile != "default":
        (ares_root / "profiles" / active_profile).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    if ares_home is not None:
        monkeypatch.setenv("ARES_HOME", ares_home)
    else:
        monkeypatch.delenv("ARES_HOME", raising=False)

    monkeypatch.setattr(sys, "argv", argv or ["ares", "gateway", "start"])

    from ares_cli.main import _apply_profile_override
    _apply_profile_override()

    return os.environ.get("ARES_HOME")


class TestApplyProfileOverrideAresHomeGuard:
    """Regression guard for issue #22502.

    Verifies that ARES_HOME pointing to the ares root does NOT suppress
    the active_profile check, while ARES_HOME already pointing to a
    profile directory IS trusted as-is.
    """

    def test_ares_home_at_root_with_active_profile_is_redirected(
        self, tmp_path, monkeypatch
    ):
        """ARES_HOME=/root/.ares + active_profile=coder must redirect
        ARES_HOME to .../profiles/coder.

        Bug scenario from #22502: systemd sets ARES_HOME to the ares root
        and the user switches to a profile via `ares profile use`.
        Before the fix, the guard returned early and active_profile was ignored.
        """
        ares_root = tmp_path / ".ares"
        ares_root.mkdir(parents=True, exist_ok=True)

        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            ares_home=str(ares_root),
            active_profile="coder",
        )

        assert result is not None, "ARES_HOME must be set after profile redirect"
        assert "profiles" in result, (
            f"Expected ARES_HOME to point into profiles/ dir, got: {result!r}"
        )
        assert result.endswith("coder"), (
            f"Expected ARES_HOME to end with 'coder', got: {result!r}"
        )

    def test_ares_home_already_profile_dir_is_trusted(self, tmp_path, monkeypatch):
        """ARES_HOME=.../profiles/coder must not be overridden even when
        active_profile says something different.

        Preserves the child-process inheritance contract: a subprocess spawned
        with ARES_HOME already set to a specific profile must stay in that
        profile.
        """
        ares_root = tmp_path / ".ares"
        profile_dir = ares_root / "profiles" / "coder"
        profile_dir.mkdir(parents=True, exist_ok=True)

        (ares_root / "active_profile").write_text("other")

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("ARES_HOME", str(profile_dir))
        monkeypatch.setattr(sys, "argv", ["ares", "gateway", "start"])

        from ares_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("ARES_HOME") == str(profile_dir), (
            "ARES_HOME must remain unchanged when already pointing to a profile dir"
        )

    def test_ares_home_unset_reads_active_profile(self, tmp_path, monkeypatch):
        """Classic case: ARES_HOME unset + active_profile=coder must set
        ARES_HOME to the profile directory (existing behaviour must not regress).
        """
        result = _run_apply_profile_override(
            tmp_path,
            monkeypatch,
            ares_home=None,
            active_profile="coder",
        )

        assert result is not None
        assert "coder" in result

    def test_ares_home_unset_default_profile_no_redirect(self, tmp_path, monkeypatch):
        """active_profile=default must not redirect ARES_HOME."""
        ares_root = tmp_path / ".ares"
        ares_root.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("ARES_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", ["ares", "gateway", "start"])
        (ares_root / "active_profile").write_text("default")

        from ares_cli.main import _apply_profile_override
        _apply_profile_override()

        assert os.environ.get("ARES_HOME") is None
