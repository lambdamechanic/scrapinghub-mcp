from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scrapinghub_mcp.server import resolve_api_key


def _write_config(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_resolve_api_key_prefers_package_root(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(
        package_root / "scrapinghub-mcp.toml",
        "[auth]\napi_key = 'package-key'\n",
    )
    _write_config(
        repo_root / "scrapinghub-mcp.toml",
        "[auth]\napi_key = 'repo-key'\n",
    )

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "package-key"


def test_resolve_api_key_falls_back_to_repo_root(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(
        repo_root / "scrapinghub-mcp.toml",
        "[auth]\napi_key = 'repo-key'\n",
    )

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "repo-key"


def test_resolve_api_key_loads_env_file(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(
        package_root / "scrapinghub-mcp.toml",
        "[auth]\nenv_file = 'secrets.env'\n",
    )
    _write_config(
        package_root / "secrets.env",
        "SCRAPINGHUB_API_KEY=env-key\n",
    )

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "env-key"


def test_resolve_api_key_uses_env_when_env_file_missing(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(
        package_root / "scrapinghub-mcp.toml",
        "[auth]\nenv_file = 'missing.env'\n",
    )

    monkeypatch.setenv("SCRAPINGHUB_API_KEY", "env-key")
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "env-key"


def test_resolve_api_key_prefers_config_over_env_file(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(
        package_root / "scrapinghub-mcp.toml",
        "[auth]\napi_key = 'config-key'\nenv_file = 'secrets.env'\n",
    )
    _write_config(
        package_root / "secrets.env",
        "SCRAPINGHUB_API_KEY=env-key\n",
    )

    monkeypatch.setenv("SCRAPINGHUB_API_KEY", "env-key")
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "config-key"


def test_resolve_api_key_errors_when_config_missing(tmp_path: Path, monkeypatch: Any) -> None:
    start_path = tmp_path / "install" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(start_path)

    with pytest.raises(RuntimeError) as excinfo:
        resolve_api_key()

    assert "https://github.com/lambdamechanic/scrapinghub-mcp" in str(excinfo.value)


def test_missing_api_key_error_includes_docs_link(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = tmp_path / "repo"
    package_root = repo_root / "package"
    start_path = package_root / "src" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)
    (repo_root / ".git").mkdir(parents=True)
    _write_config(package_root / "pyproject.toml", "[project]\nname = 'pkg'\n")
    _write_config(package_root / "scrapinghub-mcp.toml", "[auth]\napi_key = ''\n")

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(start_path)

    with pytest.raises(RuntimeError) as excinfo:
        resolve_api_key()

    assert "https://github.com/lambdamechanic/scrapinghub-mcp" in str(excinfo.value)


def test_resolve_api_key_env_only_without_config(tmp_path: Path, monkeypatch: Any) -> None:
    start_path = tmp_path / "install" / "scrapinghub_mcp"
    start_path.mkdir(parents=True)

    monkeypatch.setenv("SCRAPINGHUB_API_KEY", "env-key")
    monkeypatch.chdir(start_path)

    assert resolve_api_key() == "env-key"


def test_resolve_api_key_uses_cwd_config(tmp_path: Path, monkeypatch: Any) -> None:
    config_root = tmp_path / "config"
    config_root.mkdir()
    _write_config(
        config_root / "scrapinghub-mcp.toml",
        "[auth]\napi_key = 'cwd-key'\n",
    )

    monkeypatch.delenv("SCRAPINGHUB_API_KEY", raising=False)
    monkeypatch.chdir(config_root)

    assert resolve_api_key() == "cwd-key"
