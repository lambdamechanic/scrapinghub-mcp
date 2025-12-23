from __future__ import annotations

import typing
from importlib import resources
from pathlib import Path
from typing import Any, Callable

import scrapinghub_mcp.server as server


class DummyMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tool_registry: dict[str, Callable[..., Any]] = {}

    def tool(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            func_name = getattr(func, "__name__", "tool")
            self.tool_registry[name or func_name] = func
            return func

        return decorator


class DummyProjects:
    def list(self) -> "typing.List[str]":
        return []

    def summary(self) -> dict[str, str]:
        return {}

    def delete(self) -> None:
        return None

    def edit(self) -> None:
        return None


class DummyJobs:
    def delete(self) -> None:
        return None

    def stop(self) -> None:
        return None


class DummyClient:
    def __init__(self) -> None:
        self.projects = DummyProjects()
        self.jobs = DummyJobs()


def make_repo(
    tmp_path: Path,
    name: str,
    *,
    allowlist: str | None = None,
    config: str | None = None,
    add_git: bool = True,
    add_pyproject: bool = False,
) -> Path:
    repo_root = tmp_path / name
    repo_root.mkdir()
    if add_git:
        (repo_root / ".git").mkdir()
    if add_pyproject:
        (repo_root / "pyproject.toml").write_text(
            '[project]\nname = "dummy"\n', encoding="utf-8"
        )
    if allowlist is not None:
        (repo_root / "scrapinghub-mcp.allowlist.yaml").write_text(
            allowlist, encoding="utf-8"
        )
    if config is not None:
        (repo_root / "scrapinghub-mcp.toml").write_text(config, encoding="utf-8")
    return repo_root


def test_build_server_registers_tool(monkeypatch: Any) -> None:
    monkeypatch.setattr(server, "resolve_api_key", lambda: "test-key")
    built_server = server.build_server(mcp_cls=DummyMCP)

    assert isinstance(built_server, DummyMCP)
    assert "list_projects" in built_server.tool_registry
    assert "project_summary" in built_server.tool_registry


def test_register_scrapinghub_tools_blocks_mutating_by_default() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=False,
        non_mutating_operations={"projects.list"},
    )

    assert "list_projects" in mcp.tool_registry
    assert "project_summary" not in mcp.tool_registry
    assert "delete_project" not in mcp.tool_registry
    assert "edit_project" not in mcp.tool_registry
    assert "delete_job" not in mcp.tool_registry
    assert "stop_job" not in mcp.tool_registry


def test_register_scrapinghub_tools_allows_mutating_with_flag() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=True,
        non_mutating_operations={"projects.list"},
    )

    assert set(mcp.tool_registry.keys()) == set(server.ALLOWED_METHODS.keys())


def test_parse_mutations_accepts_non_mutating_list() -> None:
    content = "non_mutating:\n  - projects.list\n  - projects.summary\n"
    operations = server._parse_allowlist(content)

    assert operations == {"projects.list", "projects.summary"}


def test_parse_mutations_allows_empty_non_mutating_list() -> None:
    content = "non_mutating: []\n"
    operations = server._parse_allowlist(content)

    assert operations == set()


def test_parse_mutations_rejects_missing_non_mutating_list() -> None:
    content = "other: []\n"
    try:
        server._parse_allowlist(content)
    except RuntimeError as exc:
        assert "is invalid" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing non_mutating list.")


def test_parse_mutations_rejects_extra_keys() -> None:
    content = "non_mutating: []\nextra: []\n"
    try:
        server._parse_allowlist(content)
    except RuntimeError as exc:
        assert "is invalid" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for extra allowlist keys.")


def test_parse_mutations_rejects_missing_list() -> None:
    content = "not_mutations: []\n"
    try:
        server._parse_allowlist(content)
    except RuntimeError as exc:
        assert "is invalid" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing non_mutating list.")


def test_parse_mutations_rejects_non_string_items() -> None:
    content = "non_mutating:\n  - projects.list\n  - 123\n"
    try:
        server._parse_allowlist(content)
    except RuntimeError as exc:
        assert "is invalid" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-string allowlist entries.")


def test_parse_mutations_rejects_invalid_yaml() -> None:
    content = "non_mutating: [\n"
    try:
        server._parse_allowlist(content)
    except RuntimeError as exc:
        assert "Failed to parse" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid YAML.")


def test_load_non_mutating_operations_uses_repo_override(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
    )
    monkeypatch.chdir(repo_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list"}


def test_load_non_mutating_operations_merges_config_allowlist(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nextra_non_mutating = ["projects.summary"]\n',
    )
    monkeypatch.chdir(repo_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list", "projects.summary"}


def test_load_non_mutating_operations_rejects_invalid_config(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nextra_non_mutating = "projects.summary"\n',
    )
    monkeypatch.chdir(repo_root)

    try:
        server.load_non_mutating_operations()
    except RuntimeError as exc:
        assert "extra_non_mutating" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid safety config.")


def test_load_non_mutating_operations_rejects_invalid_blocklist(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nblock_non_mutating = "projects.summary"\n',
    )
    monkeypatch.chdir(repo_root)

    try:
        server.load_non_mutating_operations()
    except RuntimeError as exc:
        assert "block_non_mutating" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid blocklist config.")


def test_load_non_mutating_operations_rejects_invalid_safety_table(
    tmp_path: Path, monkeypatch: Any
) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
        config='safety = "oops"\n',
    )
    monkeypatch.chdir(repo_root)

    try:
        server.load_non_mutating_operations()
    except RuntimeError as exc:
        assert "safety section" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid safety table.")


def test_load_non_mutating_operations_blocks_entries(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n  - projects.summary\n",
        config='[safety]\nblock_non_mutating = ["projects.summary"]\n',
    )
    monkeypatch.chdir(repo_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list"}


def test_load_non_mutating_operations_blocks_overrides(tmp_path: Path, monkeypatch: Any) -> None:
    repo_root = make_repo(
        tmp_path,
        "repo",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nextra_non_mutating = ["projects.summary"]\n'
        'block_non_mutating = ["projects.summary"]\n',
    )
    monkeypatch.chdir(repo_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list"}


def test_load_non_mutating_operations_from_cwd_config(tmp_path: Path, monkeypatch: Any) -> None:
    cwd_root = make_repo(
        tmp_path,
        "cwd",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nextra_non_mutating = ["projects.summary"]\n',
    )
    monkeypatch.chdir(cwd_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list", "projects.summary"}


def test_load_non_mutating_operations_from_cwd_blocklist(tmp_path: Path, monkeypatch: Any) -> None:
    cwd_root = make_repo(
        tmp_path,
        "cwd",
        allowlist="non_mutating:\n  - projects.list\n  - projects.summary\n",
        config='[safety]\nblock_non_mutating = ["projects.summary"]\n',
    )
    monkeypatch.chdir(cwd_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list"}


def test_load_non_mutating_operations_from_package_root(tmp_path: Path, monkeypatch: Any) -> None:
    pkg_root = make_repo(
        tmp_path,
        "pkg",
        allowlist="non_mutating:\n  - projects.list\n",
        config='[safety]\nextra_non_mutating = ["projects.summary"]\n',
        add_pyproject=True,
    )
    nested = pkg_root / "subdir"
    nested.mkdir()
    monkeypatch.chdir(nested)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list", "projects.summary"}


def test_load_non_mutating_operations_without_repo_root(
    tmp_path: Path, monkeypatch: Any
) -> None:
    no_git_root = tmp_path / "nogit"
    no_git_root.mkdir()
    monkeypatch.chdir(no_git_root)

    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list", "projects.summary"}


def test_load_non_mutating_operations_uses_package_resource(monkeypatch: Any) -> None:
    monkeypatch.chdir(Path.cwd())
    operations = server.load_non_mutating_operations()

    assert operations == {"projects.list", "projects.summary"}


def test_load_non_mutating_operations_missing_file(monkeypatch: Any) -> None:
    monkeypatch.setattr(server, "ALLOWLIST_FILENAME", "missing-allowlist.yaml")
    try:
        server.load_non_mutating_operations()
    except RuntimeError as exc:
        assert "missing-allowlist.yaml" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing allowlist file.")


def test_packaged_allowlist_exists() -> None:
    resource = resources.files("scrapinghub_mcp").joinpath(server.ALLOWLIST_FILENAME)
    assert resource.is_file()


def test_packaged_schema_exists() -> None:
    resource = resources.files("scrapinghub_mcp").joinpath(server.ALLOWLIST_SCHEMA_FILENAME)
    assert resource.is_file()
