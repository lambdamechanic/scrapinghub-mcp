from __future__ import annotations

from pathlib import Path


def _read_readme() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (repo_root / "README.md").read_text(encoding="utf-8")


def test_readme_covers_setup_and_config_locations() -> None:
    readme = _read_readme().replace("\n", " ")

    assert "scrapinghub-mcp.toml" in readme
    assert "current working directory" in readme
    assert "package root" in readme
    assert "repository root" in readme
    assert "auth" in readme
    assert "env_file" in readme


def test_readme_covers_safety_and_allowlist() -> None:
    readme = _read_readme()

    assert "--allow-mutate" in readme
    assert "scrapinghub-mcp.allowlist.yaml" in readme
    assert "non-mutating" in readme


def test_readme_covers_hooks_and_ci_expectations() -> None:
    readme = _read_readme()

    assert "core.hooksPath" in readme
    assert "ruff format --check" in readme
    assert "ruff check" in readme
    assert "ty" in readme
    assert "pytest" in readme
