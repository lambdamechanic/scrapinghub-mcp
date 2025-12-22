from __future__ import annotations

import os
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
CONFIG_NAME = "scrapinghub-mcp.toml"
DOCS_URL = "https://github.com/lambdamechanic/scrapinghub-mcp"
ALLOWED_METHODS: dict[str, str] = {
    "list_projects": "projects.list",
    "project_summary": "projects.summary",
}
logger = structlog.get_logger(__name__)


def _find_parent_with_file(start: Path, filename: str) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / filename).is_file():
            return parent
    return None


def _find_parent_with_dir(start: Path, dirname: str) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / dirname).is_dir():
            return parent
    return None


def _resolve_config_path(start_path: Path | None = None) -> Path:
    search_root = start_path or Path(__file__).resolve()
    if search_root.is_file():
        search_root = search_root.parent

    package_root = _find_parent_with_file(search_root, "pyproject.toml")
    if package_root is not None:
        config_path = package_root / CONFIG_NAME
        if config_path.is_file():
            return config_path

    repo_root = _find_parent_with_dir(search_root, ".git")
    if repo_root is not None:
        config_path = repo_root / CONFIG_NAME
        if config_path.is_file():
            return config_path

    raise RuntimeError(f"Missing {CONFIG_NAME}. See {DOCS_URL} for setup.")


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


def resolve_api_key(start_path: Path | None = None) -> str:
    config_path = _resolve_config_path(start_path)
    api_key, env_file = _load_auth_config(config_path)

    if env_file:
        env_path = (config_path.parent / env_file).resolve()
        load_dotenv(env_path)

    if api_key:
        return api_key

    api_key = os.environ.get(API_KEY_ENV) if env_file else None
    if not api_key:
        raise RuntimeError(f"Missing API key in {CONFIG_NAME}. See {DOCS_URL} for setup.")
    return api_key


def resolve_method(client: Any, path: str) -> Callable[..., Any] | None:
    current: Any = client
    for attr in path.split("."):
        current = getattr(current, attr, None)
        if current is None:
            return None
    return current if callable(current) else None


def register_scrapinghub_tools(mcp: MCPType, client: Any) -> None:
    for tool_name, method_name in ALLOWED_METHODS.items():
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


def build_server(mcp_cls: type[MCPType] | None = None) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")
    client = cast(Any, ScrapinghubClient(api_key))
    register_scrapinghub_tools(mcp, client)
    return mcp
