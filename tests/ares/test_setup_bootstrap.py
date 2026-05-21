from __future__ import annotations

from pathlib import Path

import pytest

from apps.ares.ares.cli import main


@pytest.mark.parametrize("use_sample_flag", [False, True])
def test_setup_bootstrap_creates_full_pilot_scaffold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    use_sample_flag: bool,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    argv = [
        "ares",
        "setup",
        "--client",
        "pilot-demo",
        "--business-name",
        "Pilot Demo Wholesale",
        "--owner-name",
        "Raghav",
    ]
    if use_sample_flag:
        argv.append("--sample")
    monkeypatch.setattr("sys.argv", argv)

    assert main() == 0

    output = capsys.readouterr().out
    root = tmp_path / ".ares" / "clients" / "pilot-demo"

    assert (root / "profile.yaml").exists()
    for folder in ["memory", "data", "exports", "inbox", "reports", "approvals", "logs", "workflows", "skills"]:
        assert (root / folder).is_dir(), folder

    assert (root / "exports" / "README.md").exists()
    assert (root / "inbox" / "README.md").exists()
    assert (root / "reports" / "README.md").exists()

    assert "Next steps:" in output
    assert "Drop exports into:" in output
    assert str(root / "exports") in output
    assert str(root / "inbox") in output
    assert "ares validate-inputs --client pilot-demo" in output
    assert "ares morning-run --client pilot-demo" in output
    assert "ares mobile-approvals --client pilot-demo" in output


def test_setup_respects_custom_ares_home_in_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "setup",
            "--client",
            "guided-demo",
            "--business-name",
            "Guided Demo",
            "--owner-name",
            "Owner",
            "--ares-home",
            "/tmp/custom-ares-home",
        ],
    )

    assert main() == 0

    output = capsys.readouterr().out
    assert "/tmp/custom-ares-home" in output
    assert "uv run hermes ares validate-inputs --client guided-demo" in output
    assert "uv run hermes ares morning-run --client guided-demo" in output
