from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar, cast

import structlog
from dotenv import load_dotenv
from fastmcp import FastMCP
from scrapinghub import ScrapinghubClient


class MCPProtocol(Protocol):
    def __init__(self, name: str) -> None: ...

    def tool(
        self, name: str | None = None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


MCPType = TypeVar("MCPType", bound=MCPProtocol)


API_KEY_ENV = "SCRAPINGHUB_API_KEY"
DOCS_URL = "https://github.com/lambdamechanic/scrapinghub-mcp"
MUTATIONS_FILENAME = "scrapinghub-mcp.mutations.yaml"
ALLOWED_METHODS: dict[str, str] = {
    "list_projects": "projects.list",
    "project_summary": "projects.summary",
    "delete_project": "projects.delete",
    "edit_project": "projects.edit",
    "delete_job": "jobs.delete",
    "stop_job": "jobs.stop",
}
logger = structlog.get_logger(__name__)


def _find_parent(start: Path, predicate: Callable[[Path], bool]) -> Path | None:
    for parent in (start, *start.parents):
        if predicate(parent):
            return parent
    return None


def _resolve_config_path() -> Path:
    search_root = Path.cwd()
    direct_path = search_root / "scrapinghub-mcp.toml"
    if direct_path.is_file():
        return direct_path

    package_root = _find_parent(search_root, lambda root: (root / "pyproject.toml").is_file())
    if package_root is not None:
        config_path = package_root / "scrapinghub-mcp.toml"
        if config_path.is_file():
            return config_path

    repo_root = _find_parent(search_root, lambda root: (root / ".git").is_dir())
    if repo_root is not None:
        config_path = repo_root / "scrapinghub-mcp.toml"
        if config_path.is_file():
            return config_path

    raise RuntimeError(f"Missing scrapinghub-mcp.toml. See {DOCS_URL} for setup.")


def _load_auth_config(config_path: Path) -> tuple[str | None, str | None]:
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    auth = raw.get("auth")
    if not isinstance(auth, dict):
        return None, None
    api_key = auth.get("api_key")
    env_file = auth.get("env_file")
    api_key_value = api_key.strip() if isinstance(api_key, str) else None
    env_file_value = env_file.strip() if isinstance(env_file, str) else None
    return (api_key_value or None, env_file_value or None)


def _resolve_mutations_path() -> Path:
    search_root = Path.cwd()
    package_root = _find_parent(search_root, lambda root: (root / "pyproject.toml").is_file())
    if package_root is not None:
        mutations_path = package_root / MUTATIONS_FILENAME
        if mutations_path.is_file():
            return mutations_path

    repo_root = _find_parent(search_root, lambda root: (root / ".git").is_dir())
    if repo_root is not None:
        mutations_path = repo_root / MUTATIONS_FILENAME
        if mutations_path.is_file():
            return mutations_path

    raise RuntimeError(f"Missing {MUTATIONS_FILENAME}. See {DOCS_URL} for setup.")


def _parse_mutations(content: str) -> set[str]:
    operations: list[str] = []
    in_operations = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not in_operations:
            if stripped == "operations:":
                in_operations = True
            continue
        if line.lstrip().startswith("- "):
            operation = line.lstrip()[2:].strip()
            if operation:
                operations.append(operation)
            continue
        if line[:1].isspace():
            continue
        break

    if not in_operations:
        raise RuntimeError(f"{MUTATIONS_FILENAME} must define an operations list.")
    if not operations:
        raise RuntimeError(f"{MUTATIONS_FILENAME} must include at least one operation.")
    return set(operations)


def load_mutating_operations() -> set[str]:
    mutations_path = _resolve_mutations_path()
    content = mutations_path.read_text(encoding="utf-8")
    operations = _parse_mutations(content)
    logger.info("mutations.loaded", path=str(mutations_path), count=len(operations))
    return operations


def resolve_api_key() -> str:
    print(f"scrapinghub-mcp: using working directory {Path.cwd()}", file=sys.stderr)
    try:
        config_path = _resolve_config_path()
    except RuntimeError:
        api_key = os.environ.get(API_KEY_ENV)
        if api_key:
            return api_key
        raise RuntimeError(
            f"Missing scrapinghub-mcp.toml and {API_KEY_ENV}. "
            f"Create scrapinghub-mcp.toml or set {API_KEY_ENV}. See {DOCS_URL} for setup."
        ) from None

    api_key, env_file = _load_auth_config(config_path)

    if env_file:
        env_path = (config_path.parent / env_file).resolve()
        logger.info("auth.env_file.load", path=str(env_path))
        load_dotenv(env_path)

    if api_key:
        return api_key

    logger.info("auth.api_key.fallback", source="env")
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"Missing API key in scrapinghub-mcp.toml and {API_KEY_ENV}. "
            f"Set auth.api_key or {API_KEY_ENV}. See {DOCS_URL} for setup."
        )
    return api_key


def resolve_method(client: Any, path: str) -> Callable[..., Any] | None:
    current: Any = client
    for attr in path.split("."):
        current = getattr(current, attr, None)
        if current is None:
            return None
    return current if callable(current) else None


def register_scrapinghub_tools(
    mcp: MCPType,
    client: Any,
    *,
    allow_mutate: bool,
    mutating_operations: set[str],
) -> None:
    for tool_name, method_name in ALLOWED_METHODS.items():
        if method_name in mutating_operations and not allow_mutate:
            logger.info("tool.skipped", tool=tool_name, method=method_name, reason="mutating")
            continue
        method = resolve_method(client, method_name)
        if method is None:
            logger.warning("tool.missing", tool=tool_name, method=method_name)
            continue

        def tool_wrapper(*args: Any, _method: Callable[..., Any] = method, **kwargs: Any) -> Any:
            try:
                result = _method(*args, **kwargs)
            except Exception as exc:
                logger.exception("tool.failed", tool=tool_name, method=method_name)
                raise RuntimeError(f"Scrapinghub tool '{tool_name}' failed.") from exc
            if isinstance(result, (str, bytes, dict)):
                return result
            if hasattr(result, "__iter__"):
                return list(result)
            return result

        mcp.tool(name=tool_name)(tool_wrapper)
        logger.info("tool.registered", tool=tool_name, method=method_name)


def build_server(
    *, allow_mutate: bool = False, mcp_cls: type[MCPType] | None = None
) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")
    client = cast(Any, ScrapinghubClient(api_key))
    mutating_operations = load_mutating_operations()
    register_scrapinghub_tools(
        mcp, client, allow_mutate=allow_mutate, mutating_operations=mutating_operations
    )
    return mcp
