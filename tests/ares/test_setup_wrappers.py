from __future__ import annotations

from pathlib import Path


def test_setup_script_generates_ares_wrapper_through_hermes_vertical_command() -> None:
    script = Path("scripts/setup_ares.sh").read_text(encoding="utf-8")

    assert 'exec "$UV_BIN" run hermes ares "\\$@"' in script
    assert 'exec "$UV_BIN" run ares "$@"' not in script
