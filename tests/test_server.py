from __future__ import annotations

import typing
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from requests import HTTPError, Response

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


class DummyJobMeta:
    def __init__(self, data: dict[str, int | str]) -> None:
        self._data = data

    def list(self) -> typing.List[typing.Tuple[str, int | str]]:
        return list(self._data.items())


class DummyJob:
    def __init__(self, job_key: str) -> None:
        self.key = job_key
        self.project_id = int(job_key.split("/")[0])
        self.metadata = DummyJobMeta({"state": "finished"})


class DummyProject:
    def __init__(self, project_id: int) -> None:
        self.key = str(project_id)


class DummyClient:
    def __init__(self) -> None:
        self.projects = DummyProjects()
        self.jobs = DummyJobs()

    def get_job(self, job_key: str) -> DummyJob:
        return DummyJob(job_key)

    def get_project(self, project_id: int) -> DummyProject:
        return DummyProject(project_id)

    def close(self) -> None:
        return None


def load_packaged_allowlist() -> set[str]:
    resource = resources.files("scrapinghub_mcp").joinpath(server.ALLOWLIST_FILENAME)
    content = resource.read_text(encoding="utf-8")
    return server._parse_allowlist(content)


class DummyAuthFailureProjects:
    def list(self) -> None:
        response = Response()
        response.status_code = 401
        response.url = "https://storage.scrapinghub.com"
        raise HTTPError(response=response)


class DummySummaryProjects:
    def list(self) -> typing.List[int]:
        return [1, 2]

    def summary(self) -> typing.List[dict[str, int]]:
        return [{"project": 1, "running": 0, "pending": 0, "finished": 0, "has_capacity": True}]


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
        (repo_root / "pyproject.toml").write_text('[project]\nname = "dummy"\n', encoding="utf-8")
    if allowlist is not None:
        (repo_root / "scrapinghub-mcp.allowlist.yaml").write_text(allowlist, encoding="utf-8")
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
    assert "project_jobs_run" not in mcp.tool_registry
    assert "project_jobs_cancel" not in mcp.tool_registry
    assert "project_activity_add" not in mcp.tool_registry
    assert "project_frontiers_flush" not in mcp.tool_registry
    assert "project_settings_set" not in mcp.tool_registry


def test_register_scrapinghub_tools_allows_mutating_with_flag() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=True,
        non_mutating_operations={"projects.list"},
    )

    assert set(mcp.tool_registry.keys()) == set(server.TOOL_SPECS.keys())


def test_tool_wrapper_returns_auth_error_message() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()
    client.projects = DummyAuthFailureProjects()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=False,
        non_mutating_operations={"projects.list"},
    )

    tool = mcp.tool_registry["list_projects"]
    try:
        tool()
    except RuntimeError as exc:
        message = str(exc)
        assert "Authentication failed" in message
        assert server.API_KEY_ENV in message
    else:
        raise AssertionError("Expected RuntimeError for auth failure.")


def test_tool_wrapper_wraps_list_of_dicts() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()
    client.projects = DummySummaryProjects()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=False,
        non_mutating_operations={"projects.list", "projects.summary"},
    )

    tool = mcp.tool_registry["project_summary"]
    result = tool()

    assert result.model_dump() == {
        "items": [
            {
                "project": 1,
                "running": 0,
                "pending": 0,
                "finished": 0,
                "has_capacity": True,
            }
        ]
    }


def test_get_job_returns_metadata() -> None:
    mcp = DummyMCP("scrapinghub-mcp")
    client = DummyClient()

    server.register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=False,
        non_mutating_operations={"get_job"},
    )

    tool = mcp.tool_registry["get_job"]
    result = tool({"job_key": "1/2/3"})

    assert result.model_dump() == {
        "job_key": "1/2/3",
        "project_id": 1,
        "metadata": {"state": "finished"},
    }


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


def test_load_non_mutating_operations_without_repo_root(tmp_path: Path, monkeypatch: Any) -> None:
    no_git_root = tmp_path / "nogit"
    no_git_root.mkdir()
    monkeypatch.chdir(no_git_root)

    operations = server.load_non_mutating_operations()

    assert operations == load_packaged_allowlist()


def test_load_non_mutating_operations_uses_package_resource(monkeypatch: Any) -> None:
    monkeypatch.chdir(Path.cwd())
    operations = server.load_non_mutating_operations()

    assert operations == load_packaged_allowlist()


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
