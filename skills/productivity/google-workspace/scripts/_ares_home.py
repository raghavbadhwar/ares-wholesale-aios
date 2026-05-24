"""Resolve ARES_HOME for standalone skill scripts.

Skill scripts may run outside the Ares process (e.g. system Python,
nix env, CI) where ``ares_constants`` is not importable.  This module
provides the same ``get_ares_home()`` and ``display_ares_home()``
contracts as ``ares_constants`` without requiring it on ``sys.path``.

When ``ares_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``ares_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``ARES_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from ares_constants import display_ares_home as display_ares_home
    from ares_constants import get_ares_home as get_ares_home
except (ModuleNotFoundError, ImportError):

    def get_ares_home() -> Path:
        """Return the Ares home directory (default: ~/.ares).

        Mirrors ``ares_constants.get_ares_home()``."""
        val = os.environ.get("ARES_HOME", "").strip()
        return Path(val) if val else Path.home() / ".ares"

    def display_ares_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``ares_constants.display_ares_home()``."""
        home = get_ares_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
