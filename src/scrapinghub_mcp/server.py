from __future__ import annotations

import json
import os
import sys
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar, cast

import jsonschema
import structlog
import yaml
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
ALLOWLIST_FILENAME = "scrapinghub-mcp.allowlist.yaml"
ALLOWLIST_SCHEMA_FILENAME = "allowlist-schema.json"
_ALLOWLIST_SCHEMA: dict[str, object] | None = None
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


def _load_allowlist_content() -> tuple[str, str]:
    repo_root = _find_parent(Path.cwd(), lambda root: (root / ".git").is_dir())
    if repo_root is not None:
        override_path = repo_root / ALLOWLIST_FILENAME
        if override_path.is_file():
            return override_path.read_text(encoding="utf-8"), str(override_path)

    try:
        resource = resources.files("scrapinghub_mcp").joinpath(ALLOWLIST_FILENAME)
        return resource.read_text(encoding="utf-8"), f"package:{resource}"
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing {ALLOWLIST_FILENAME}. See {DOCS_URL} for setup.") from exc


def _load_allowlist_schema() -> dict[str, object]:
    global _ALLOWLIST_SCHEMA
    if _ALLOWLIST_SCHEMA is not None:
        return _ALLOWLIST_SCHEMA
    try:
        resource = resources.files("scrapinghub_mcp").joinpath(ALLOWLIST_SCHEMA_FILENAME)
        content = resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing {ALLOWLIST_SCHEMA_FILENAME}.") from exc
    _ALLOWLIST_SCHEMA = json.loads(content)
    return _ALLOWLIST_SCHEMA


def _parse_allowlist(content: str) -> set[str]:
    try:
        payload = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Failed to parse {ALLOWLIST_FILENAME}.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{ALLOWLIST_FILENAME} must define a mapping.")
    try:
        schema = _load_allowlist_schema()
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(f"{ALLOWLIST_FILENAME} is invalid: {exc.message}") from exc

    operations = payload.get("non_mutating") or []
    return set(operations)


def _load_safety_config() -> tuple[set[str], set[str], str | None]:
    try:
        config_path = _resolve_config_path()
    except RuntimeError:
        return set(), set(), None

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    safety = raw.get("safety")
    if safety is None:
        return set(), set(), str(config_path)
    if not isinstance(safety, dict):
        raise RuntimeError("safety section in scrapinghub-mcp.toml must be a table.")

    extra = safety.get("extra_non_mutating")
    if extra is None:
        extra_items: set[str] = set()
    else:
        if not isinstance(extra, list):
            raise RuntimeError("safety.extra_non_mutating must be a list of strings.")
        extra_values = [item for item in extra if isinstance(item, str) and item.strip()]
        if len(extra_values) != len(extra):
            raise RuntimeError("safety.extra_non_mutating must contain only strings.")
        extra_items = set(extra_values)

    block = safety.get("block_non_mutating")
    if block is None:
        block_items: set[str] = set()
    else:
        if not isinstance(block, list):
            raise RuntimeError("safety.block_non_mutating must be a list of strings.")
        block_values = [item for item in block if isinstance(item, str) and item.strip()]
        if len(block_values) != len(block):
            raise RuntimeError("safety.block_non_mutating must contain only strings.")
        block_items = set(block_values)

    return extra_items, block_items, str(config_path)


def load_non_mutating_operations() -> set[str]:
    content, source = _load_allowlist_content()
    operations = _parse_allowlist(content)
    overrides, blocklist, config_path = _load_safety_config()
    merged = (operations | overrides) - blocklist
    logger.info(
        "allowlist.loaded",
        source=source,
        count=len(operations),
        override_count=len(overrides),
        block_count=len(blocklist),
        merged_count=len(merged),
        config_path=config_path,
    )
    return merged


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
    non_mutating_operations: set[str],
) -> None:
    for tool_name, method_name in ALLOWED_METHODS.items():
        if method_name not in non_mutating_operations and not allow_mutate:
            logger.info(
                "tool.skipped",
                tool=tool_name,
                method=method_name,
                reason="mutating-default",
            )
            continue
        method = resolve_method(client, method_name)
        if method is None:
            logger.warning("tool.missing", tool=tool_name, method=method_name)
            continue

        def tool_wrapper(
            *args: Any,
            _method: Callable[..., Any] = method,
            _tool_name: str = tool_name,
            _method_name: str = method_name,
            **kwargs: Any,
        ) -> Any:
            try:
                result = _method(*args, **kwargs)
            except Exception as exc:
                logger.exception("tool.failed", tool=_tool_name, method=_method_name)
                raise RuntimeError(f"Scrapinghub tool '{_tool_name}' failed.") from exc
            if isinstance(result, (str, bytes, dict)):
                return result
            if hasattr(result, "__iter__"):
                return list(result)
            return result

        mcp.tool(name=tool_name)(tool_wrapper)
        logger.info("tool.registered", tool=tool_name, method=method_name)


def build_server(*, allow_mutate: bool = False, mcp_cls: type[MCPType] | None = None) -> MCPType:
    api_key = resolve_api_key()
    cls = cast(type[MCPType], FastMCP) if mcp_cls is None else mcp_cls
    mcp = cls("scrapinghub-mcp")
    client = cast(Any, ScrapinghubClient(api_key))
    non_mutating_operations = load_non_mutating_operations()
    register_scrapinghub_tools(
        mcp,
        client,
        allow_mutate=allow_mutate,
        non_mutating_operations=non_mutating_operations,
    )
    return mcp
