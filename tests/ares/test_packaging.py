from __future__ import annotations

from pathlib import Path
import tomllib


def test_ares_package_data_uses_literal_package_names() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]

    assert "apps.ares" in package_data
    assert "plugins.ares" in package_data
    assert "apps" not in package_data
    assert "plugins" not in package_data
